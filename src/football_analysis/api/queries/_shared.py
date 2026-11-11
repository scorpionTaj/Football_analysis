"""Helpers shared by every query module: coercion, search scoring, sources, team refs."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any

import numpy as np
import pandas as pd

from football_analysis.api.contracts import (
    Match,
    SourceMeta,
    TeamRef,
    canonical_team_id,
)
from football_analysis.api.db import PostgresReadOnlyStore, ReadOnlyStore, SQLiteReadOnlyStore
from football_analysis.teams import display_team


def _as_date(value) -> date | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def _as_datetime(value) -> datetime | None:
    if value is None or pd.isna(value):
        return None
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime().replace(microsecond=0)


def _mean(series: pd.Series) -> float | None:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.dropna().empty:
        return None
    return float(numeric.mean())


def _search_text(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode()
    return " ".join(re.findall(r"[a-z0-9]+", text.casefold()))


def _fuzzy_score(query: str, value) -> float:
    """Prefer exact words and prefixes; tolerate typos only in longer queries."""
    needle, candidate = _search_text(query), _search_text(value)
    if not needle or not candidate:
        return 0.0
    if needle == candidate:
        return 1.0
    words = candidate.split()
    if needle in words:
        return 0.98
    if any(word.startswith(needle) for word in words):
        return 0.94
    if len(needle) >= 3 and needle in candidate:
        return 0.88
    if len(needle) < 4:
        return 0.0
    close_lengths = (
        part for part in (candidate, *words)
        if abs(len(part) - len(needle)) <= max(2, len(needle) // 3)
    )
    return max((SequenceMatcher(None, needle, part).ratio() for part in close_lengths), default=0.0)


def _has(store: ReadOnlyStore, name: str) -> bool:
    return name in store.tables()


def _source(name: str, coverage: str, freshness=None) -> SourceMeta:
    return SourceMeta(source=name, coverage=coverage, freshness=_as_datetime(freshness))


def _store_source(store: ReadOnlyStore | PostgresReadOnlyStore) -> str:
    if isinstance(store, PostgresReadOnlyStore):
        return "postgresql"
    return "sqlite" if isinstance(store, SQLiteReadOnlyStore) else "duckdb"


def _competition_media_map(store: ReadOnlyStore) -> dict[str, Any]:
    if not _has(store, "competition_media"):
        return {}
    df = store.query("SELECT league_code, badge_url, logo_url, banner_url, trophy_url, fanart_url FROM competition_media")
    return {row.league_code: row for row in df.itertuples(index=False)}


def _team_media_map(store: ReadOnlyStore) -> dict[str, Any]:
    if not _has(store, "team_media"):
        return {}
    df = store.query("SELECT team, badge_url, logo_url FROM team_media")
    return {canonical_team_id(row.team): row for row in df.itertuples(index=False)}


def _build_team_ref(name: str | None, media_map: dict[str, Any] | None = None) -> TeamRef:
    raw = name or ""
    tid = canonical_team_id(raw)
    badge = None
    logo = None
    if media_map and tid in media_map:
        badge = getattr(media_map[tid], "badge_url", None) or None
        logo = getattr(media_map[tid], "logo_url", None) or None
    return TeamRef(
        team_id=tid,
        name=display_team(raw) or raw,
        badge_url=badge,
        logo_url=logo,
    )


def _match_from_row(row, competition_field="league", media_map: dict[str, Any] | None = None) -> Match:
    _sentinel = object()
    competition = getattr(row, competition_field, _sentinel)
    if competition is _sentinel:
        competition = getattr(row, "competition", getattr(row, "league", None))
    return Match(
        competition=competition,
        season=int(row.season),
        match_date=_as_date(row.match_date) or date.min,
        kickoff_time=None if pd.isna(getattr(row, "kickoff_time", None)) else str(row.kickoff_time),
        home=_build_team_ref(row.home_team, media_map),
        away=_build_team_ref(row.away_team, media_map),
        home_goals=None if pd.isna(getattr(row, "home_goals", None)) else int(row.home_goals),
        away_goals=None if pd.isna(getattr(row, "away_goals", None)) else int(row.away_goals),
        venue=getattr(row, "venue", None),
        stage=getattr(row, "stage", None),
        referee=None if pd.isna(getattr(row, "referee", None)) else getattr(row, "referee", None),
        home_shots=None if pd.isna(getattr(row, "home_shots", None)) else int(row.home_shots),
        away_shots=None if pd.isna(getattr(row, "away_shots", None)) else int(row.away_shots),
        home_shots_on_target=None if pd.isna(getattr(row, "home_sot", None)) else int(row.home_sot),
        away_shots_on_target=None if pd.isna(getattr(row, "away_sot", None)) else int(row.away_sot),
        half_time_home_goals=None if pd.isna(getattr(row, "half_time_home_goals", None)) else int(row.half_time_home_goals),
        half_time_away_goals=None if pd.isna(getattr(row, "half_time_away_goals", None)) else int(row.half_time_away_goals),
        home_corners=None if pd.isna(getattr(row, "home_corners", None)) else int(row.home_corners),
        away_corners=None if pd.isna(getattr(row, "away_corners", None)) else int(row.away_corners),
        home_fouls=None if pd.isna(getattr(row, "home_fouls", None)) else int(row.home_fouls),
        away_fouls=None if pd.isna(getattr(row, "away_fouls", None)) else int(row.away_fouls),
        home_yellows=None if pd.isna(getattr(row, "home_yellows", None)) else int(row.home_yellows),
        away_yellows=None if pd.isna(getattr(row, "away_yellows", None)) else int(row.away_yellows),
        home_reds=None if pd.isna(getattr(row, "home_reds", None)) else int(row.home_reds),
        away_reds=None if pd.isna(getattr(row, "away_reds", None)) else int(row.away_reds),
        source=getattr(row, "source", None),
    )


def _present(value) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None
