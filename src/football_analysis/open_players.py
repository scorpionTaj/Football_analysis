"""Complete featured-club player snapshots from the CC0 Transfermarkt dataset."""

import argparse
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .sync_state import mark_fresh
from .config import (
    DATA,
    DB,
    TRANSFERMARKT_COMPETITIONS,
    TRANSFERMARKT_TOURNAMENT_CODES,
)
from .ingest import connect


SOURCE = "Transfermarkt Open Dataset"
DATASET_URL = "https://github.com/dcaribou/transfermarkt-datasets"
DOWNLOAD_BASE = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data"
FILES = ("players", "games", "appearances", "competitions", "game_events", "game_lineups", "transfers")
CLUB_MAP = {
    418: "Real Madrid", 131: "Barcelona", 13: "Ath Madrid",
    281: "Man City", 31: "Liverpool", 11: "Arsenal",
    27: "Bayern Munich", 16: "Dortmund", 583: "Paris SG",
    46: "Inter", 5: "Milan", 506: "Juventus",
}


def _session():
    session = requests.Session()
    session.headers["User-Agent"] = "football-analysis/0.5 (personal analytics)"
    retry = Retry(
        total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504],
        respect_retry_after_header=True,
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def download_snapshot(directory, refresh=False):
    """Download the published CSVs required by the player and transfer importers."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    session = _session()
    paths = {}
    for name in FILES:
        path = directory / f"{name}.csv.gz"
        # The dataset republishes weekly; re-download a snapshot older than that.
        if refresh or not path.exists() or time.time() - path.stat().st_mtime > 7 * 86400:
            response = session.get(
                f"{DOWNLOAD_BASE}/{name}.csv.gz", timeout=(10, 180), stream=True,
            )
            response.raise_for_status()
            temporary = path.with_suffix(path.suffix + ".part")
            with temporary.open("wb") as handle:
                for chunk in response.iter_content(1024 * 1024):
                    handle.write(chunk)
            temporary.replace(path)
        paths[name] = path.resolve()
    return paths


def _snapshot_fingerprint(paths, first_season):
    """Identify an unchanged local snapshot and importer without scanning CSV rows."""
    inputs = [
        (name, path.stat().st_size, path.stat().st_mtime_ns)
        for name, path in sorted(paths.items()) if name != "transfers"
    ]
    implementation = Path(__file__).stat()
    inputs.append(("importer", implementation.st_size, implementation.st_mtime_ns))
    inputs.append(("first_season", first_season))
    return hashlib.sha256(json.dumps(inputs).encode()).hexdigest()


def build_frames(paths, first_season=2021, last_season=None):
    """Return current featured-club profiles and five-season appearance totals."""
    players = pd.read_csv(paths["players"])
    last_season = last_season if last_season is not None else int(players.last_season.max())
    featured = players[
        players.current_club_id.isin(CLUB_MAP) & players.last_season.eq(last_season)
    ].copy()
    featured["team"] = featured.current_club_id.map(CLUB_MAP)
    games = pd.read_csv(paths["games"], usecols=["game_id", "season"])
    games = games[games.season.between(first_season, last_season)]
    seasons_by_game = games.set_index("game_id").season
    teams_by_player = featured.set_index("player_id").team
    competitions = pd.read_csv(paths["competitions"]).set_index("competition_id")
    appearances = []
    latest_match = None
    columns = ["game_id", "player_id", "competition_id", "date", "goals", "assists",
               "minutes_played", "yellow_cards", "red_cards"]
    for chunk in pd.read_csv(paths["appearances"], usecols=columns, chunksize=100_000):
        chunk = chunk[chunk.game_id.isin(seasons_by_game.index)].copy()
        if chunk.empty:
            continue
        candidate = pd.to_datetime(chunk.date, errors="coerce").max()
        if pd.notna(candidate) and (latest_match is None or candidate > latest_match):
            latest_match = candidate
        chunk = chunk[chunk.player_id.isin(teams_by_player.index)].copy()
        if chunk.empty:
            continue
        chunk["team"] = chunk.player_id.map(teams_by_player)
        chunk["season"] = chunk.game_id.map(seasons_by_game)
        appearances.append(chunk)
    data_as_of = latest_match.date() if latest_match is not None else None
    now = datetime.now()
    featured["source"] = SOURCE
    featured["player_id"] = featured.player_id.astype(str)
    featured["team_id"] = featured.current_club_id.astype(str)
    featured["date_born"] = pd.to_datetime(featured.date_of_birth, errors="coerce").dt.date
    featured["data_as_of"] = data_as_of
    featured["fetched_at"] = now
    profiles = featured.rename(columns={
        "name": "player", "country_of_citizenship": "nationality", "height_in_cm": "height_cm",
        "market_value_in_eur": "market_value_eur", "highest_market_value_in_eur": "highest_market_value_eur",
        "url": "profile_url",
    })[["source", "player_id", "team_id", "team", "player", "position", "sub_position",
        "nationality", "date_born", "foot", "height_cm", "market_value_eur",
        "highest_market_value_eur", "image_url", "profile_url", "last_season",
        "data_as_of", "fetched_at"]].fillna({
            "position": "", "sub_position": "", "nationality": "", "foot": "",
            "image_url": "", "profile_url": "",
        }).sort_values(["team", "position", "player"]).reset_index(drop=True)
    stats_columns = ["source", "player_id", "team", "season", "competition_id", "competition",
                     "competition_type", "appearances", "goals", "assists", "minutes_played",
                     "yellow_cards", "red_cards", "data_as_of", "fetched_at"]
    if not appearances:
        return profiles, pd.DataFrame(columns=stats_columns), data_as_of, last_season
    stats = pd.concat(appearances, ignore_index=True)
    stats["competition"] = stats.competition_id.map(competitions.name).fillna(stats.competition_id).str.replace("-", " ")
    stats["competition_type"] = stats.competition_id.map(competitions.type).fillna("")
    metrics = ["goals", "assists", "minutes_played", "yellow_cards", "red_cards"]
    for column in metrics:
        stats[column] = pd.to_numeric(stats[column], errors="coerce").fillna(0).astype(int)
    stats = stats.groupby(["player_id", "team", "season", "competition_id", "competition",
                           "competition_type"], as_index=False).agg(
        appearances=("game_id", "size"), **{column: (column, "sum") for column in metrics},
    )
    stats["source"] = SOURCE
    stats["player_id"] = stats.player_id.astype(str)
    stats["data_as_of"] = data_as_of
    stats["fetched_at"] = now
    return profiles, stats[stats_columns].sort_values(
        ["team", "player_id", "season", "competition_id"],
    ).reset_index(drop=True), data_as_of, last_season


def build_match_context_frame(games_path):
    """Normalize the published real-match manager, formation and venue context."""
    games = pd.read_csv(games_path, dtype=str).fillna("")
    games["match_date"] = pd.to_datetime(games["date"], errors="coerce").dt.date
    games = games[
        games.match_date.notna() & games.home_club_name.ne("") & games.away_club_name.ne("")
    ].copy()
    games["season"] = pd.to_numeric(games.season, errors="coerce").astype("Int64")
    games["attendance"] = pd.to_numeric(games.attendance, errors="coerce").astype("Int64")
    games["source"] = SOURCE
    games["fetched_at"] = datetime.now()
    return games.rename(columns={
        "game_id": "match_id", "home_club_name": "home_team", "away_club_name": "away_team",
        "home_club_manager_name": "home_coach", "away_club_manager_name": "away_coach",
        "home_club_formation": "home_formation", "away_club_formation": "away_formation",
        "stadium": "stadium", "referee": "referee", "url": "source_url",
    })[[
        "source", "match_id", "competition_id", "season", "match_date", "home_team", "away_team",
        "home_coach", "away_coach", "home_formation", "away_formation", "stadium",
        "attendance", "referee", "source_url", "fetched_at",
    ]].sort_values(["match_date", "match_id"], ascending=[False, True]).reset_index(drop=True)


def _detail_inputs(paths, first_season):
    games = pd.read_csv(paths["games"], dtype=str).fillna("")
    games["season"] = pd.to_numeric(games.season, errors="coerce")
    games = games[
        games.competition_id.isin(TRANSFERMARKT_COMPETITIONS) & games.season.ge(first_season)
    ].copy()
    game_ids = set(games.game_id)
    players = pd.read_csv(paths["players"], usecols=["player_id", "name", "image_url"], dtype=str)
    players = players.fillna("").drop_duplicates("player_id").set_index("player_id")
    lineup_names = {}
    lineups = []
    for chunk in pd.read_csv(paths["game_lineups"], dtype=str, chunksize=100_000):
        named = chunk[["player_id", "player_name"]].dropna().drop_duplicates("player_id")
        lineup_names.update({key: value for key, value in zip(named.player_id, named.player_name)
                             if key not in lineup_names and value})
        scoped = chunk[chunk.game_id.isin(game_ids)]
        if not scoped.empty:
            lineups.append(scoped)
    events = []
    for chunk in pd.read_csv(paths["game_events"], dtype=str, chunksize=100_000):
        scoped = chunk[chunk.game_id.isin(game_ids)]
        if not scoped.empty:
            events.append(scoped)
    lineup_columns = ["game_lineups_id", "game_id", "player_id", "club_id", "player_name",
                      "type", "position", "number"]
    event_columns = ["game_event_id", "game_id", "minute", "type", "club_id", "club_name",
                     "player_id", "description", "player_in_id", "player_assist_id"]
    return (games, players, lineup_names,
            pd.concat(lineups, ignore_index=True) if lineups else pd.DataFrame(columns=lineup_columns),
            pd.concat(events, ignore_index=True) if events else pd.DataFrame(columns=event_columns))


def build_match_detail_frames(paths, first_season=2021):
    """Build verified event and lineup rows for every covered app competition."""
    games, players, lineup_names, raw_lineups, raw_events = _detail_inputs(paths, first_season)
    now = datetime.now()
    games = games.set_index("game_id")
    events = raw_events.fillna("").join(
        games[["home_club_id", "away_club_id", "home_club_name", "away_club_name"]], on="game_id", how="inner",
    )
    # game_events.csv spells clubs differently from games.csv (e.g. "AS Roma" vs "Associazione
    # Sportiva Roma"); name the side by club id so events, lineups and matches agree.
    event_team = events.home_club_name.where(
        events.club_id.eq(events.home_club_id),
        events.away_club_name.where(events.club_id.eq(events.away_club_id), events.club_name),
    )
    description = events.description.str.lower()
    kind = events.type.replace("", "Match event")
    kind.loc[events.type.eq("Goals")] = "Goal"
    cards = events.type.eq("Cards")
    kind.loc[cards] = "Yellow card"
    kind.loc[cards & description.str.contains("red card", regex=False)] = "Red card"
    kind.loc[cards & description.str.contains("second yellow", regex=False)] = "Second yellow card"
    shootout = events.type.eq("Shootout")
    kind.loc[shootout] = "Penalty shootout goal"
    kind.loc[shootout & description.str.contains("missed", regex=False)] = "Missed penalty"
    kind.loc[events.type.eq("Substitutions")] = "Substitution"
    assists = events.player_assist_id.where(events.type.ne("Substitutions"), events.player_in_id)
    timeline = pd.DataFrame({
        "source": SOURCE, "timeline_id": events.game_event_id, "event_id": events.game_id,
        "minute": events.minute, "event_type": kind, "detail": events.description,
        "team": event_team, "player_id": events.player_id,
        "player": events.player_id.map(players.name).replace("", pd.NA).fillna(
            events.player_id.map(lineup_names)).fillna(""),
        "assist": assists.map(players.name).replace("", pd.NA).fillna(
            assists.map(lineup_names)).fillna(""),
        "is_home": events.club_id.eq(events.home_club_id), "comment": "", "fetched_at": now,
    })
    timeline["_minute"] = pd.to_numeric(timeline.minute, errors="coerce")
    timeline = timeline.sort_values(["event_id", "_minute", "timeline_id"]).drop(
        columns="_minute",
    ).reset_index(drop=True)
    lineups = raw_lineups.fillna("").join(
        games[["home_club_id", "away_club_id", "home_club_name", "away_club_name"]],
        on="game_id", how="inner",
    )
    is_home = lineups.club_id.eq(lineups.home_club_id)
    lineups_frame = pd.DataFrame({
        "source": SOURCE, "lineup_id": lineups.game_lineups_id, "event_id": lineups.game_id,
        "team": lineups.home_club_name.where(is_home, lineups.away_club_name.where(
            lineups.club_id.eq(lineups.away_club_id), "")),
        "player_id": lineups.player_id,
        "player": lineups.player_name.fillna(lineups.player_id.map(players.name)).fillna(""),
        "position": lineups.position, "is_home": is_home,
        "is_substitute": lineups.type.str.lower().ne("starting_lineup"),
        "shirt_number": lineups.number, "cutout_url": lineups.player_id.map(players.image_url).fillna(""),
        "fetched_at": now,
    })
    lineups_frame = lineups_frame.sort_values(
        ["event_id", "is_home", "is_substitute", "position", "player"],
        ascending=[True, False, True, True, True],
    ).reset_index(drop=True)
    return timeline, lineups_frame


def build_transfermarkt_tournament_frames(paths, first_season=2021, timeline=None):
    """Normalize completed domestic, continental and national cup matches."""
    now = datetime.now()
    games = pd.read_csv(paths["games"], dtype=str).fillna("")
    games["competition"] = games.competition_id.map(TRANSFERMARKT_COMPETITIONS)
    games["season"] = pd.to_numeric(games.season, errors="coerce").astype("Int64")
    games["match_date"] = pd.to_datetime(games.date, errors="coerce").dt.date
    games["home_goals"] = pd.to_numeric(games.home_club_goals, errors="coerce").astype("Int64")
    games["away_goals"] = pd.to_numeric(games.away_club_goals, errors="coerce").astype("Int64")
    cups = games[
        games.competition.isin(TRANSFERMARKT_TOURNAMENT_CODES - {"UCL", "WC"})
        & games.season.ge(first_season) & games.match_date.notna()
    ].copy()
    finished = cups[
        cups.home_goals.notna() & cups.away_goals.notna()
        & cups.home_club_name.ne(cups.away_club_name)
    ].sort_values("game_id", ascending=False)
    finished = finished.drop_duplicates(
        ["competition", "season", "match_date", "home_club_name", "away_club_name"],
    )
    matches = pd.DataFrame({
        "competition": finished.competition, "season": finished.season,
        "stage": finished["round"].replace("", "Unknown"), "group_name": "",
        "match_date": finished.match_date, "home_team": finished.home_club_name,
        "away_team": finished.away_club_name, "home_goals": finished.home_goals,
        "away_goals": finished.away_goals, "home_penalties": None, "away_penalties": None,
        "venue": finished.stadium, "neutral": False, "status": "FINISHED", "source": SOURCE,
        "source_url": finished.url, "fetched_at": now,
    }).reset_index(drop=True)
    if timeline is None:
        timeline, _ = build_match_detail_frames(paths, first_season=first_season)
    scored = timeline[timeline.event_type.eq("Goal")].merge(
        cups[["game_id", "competition", "season", "match_date", "url"]],
        left_on="event_id", right_on="game_id", how="inner",
    )
    scored["player"] = scored.player.replace("", "Unknown")
    scored = scored.sort_values("timeline_id").drop_duplicates(
        ["competition", "season", "match_date", "team", "player", "minute"],
    )
    description = scored.detail.str.lower()
    goals = pd.DataFrame({
        "competition": scored.competition, "season": scored.season,
        "match_date": scored.match_date, "team": scored.team, "player": scored.player,
        "minute": scored.minute, "penalty": description.str.contains("penalty", regex=False),
        "own_goal": description.str.contains("own-goal", regex=False),
        "source": SOURCE, "source_url": scored.url, "fetched_at": now,
    }).reset_index(drop=True)
    return matches, goals


def sync_open_players(db=DB, directory=None, refresh=False, first_season=2021):
    directory = Path(directory or DATA / "external" / "transfermarkt")
    paths = download_snapshot(directory, refresh=refresh)
    fingerprint = _snapshot_fingerprint(paths, first_season)
    if not refresh:
        with connect(db) as con:
            cached = con.execute(
                "SELECT fingerprint FROM source_sync_cache WHERE source=?", [SOURCE]
            ).fetchall()
            if cached and cached[0][0] == fingerprint:
                counts = con.execute(
                    "SELECT "
                    "(SELECT count(*) FROM open_players WHERE source=?), "
                    "(SELECT count(*) FROM event_timeline WHERE source=?), "
                    "(SELECT count(*) FROM event_lineups WHERE source=?), "
                    "(SELECT count(*) FROM tournament_matches WHERE source=?)",
                    [SOURCE] * 4,
                ).fetchall()[0]
                if all(counts):
                    report = {
                        "source": SOURCE, "status": "cached", "players": counts[0],
                        "timeline_events": counts[1], "lineup_rows": counts[2],
                        "tournament_matches": counts[3],
                    }
                    print(report, flush=True)
                    return report
    profiles, stats, data_as_of, snapshot_season = build_frames(
        paths, first_season=first_season,
    )
    contexts = build_match_context_frame(paths["games"])
    timeline, lineups = build_match_detail_frames(paths, first_season=first_season)
    tournament_matches, tournament_goals = build_transfermarkt_tournament_frames(
        paths, first_season=first_season, timeline=timeline,
    )
    with connect(db) as con:
        con.register("incoming_open_players", profiles)
        con.register("incoming_open_stats", stats)
        con.register("incoming_match_contexts", contexts)
        con.register("incoming_event_timeline", timeline)
        con.register("incoming_event_lineups", lineups)
        con.register("incoming_tournament_matches", tournament_matches)
        con.register("incoming_tournament_goals", tournament_goals)
        con.execute("BEGIN")
        try:
            con.execute("DELETE FROM open_player_stats WHERE source=?", [SOURCE])
            con.execute("DELETE FROM open_players WHERE source=?", [SOURCE])
            con.execute("INSERT INTO open_players SELECT * FROM incoming_open_players")
            con.execute("INSERT INTO open_player_stats SELECT * FROM incoming_open_stats")
            con.execute("DELETE FROM match_contexts WHERE source=?", [SOURCE])
            con.execute("INSERT INTO match_contexts SELECT * FROM incoming_match_contexts")
            con.execute("DELETE FROM event_timeline WHERE source=?", [SOURCE])
            con.execute("INSERT INTO event_timeline SELECT * FROM incoming_event_timeline")
            con.execute("DELETE FROM event_lineups WHERE source=?", [SOURCE])
            con.execute("INSERT INTO event_lineups SELECT * FROM incoming_event_lineups")
            con.execute("DELETE FROM tournament_goals WHERE source=?", [SOURCE])
            con.execute("INSERT INTO tournament_goals SELECT * FROM incoming_tournament_goals")
            con.execute("DELETE FROM tournament_matches WHERE source=?", [SOURCE])
            con.execute("INSERT INTO tournament_matches SELECT * FROM incoming_tournament_matches")
            con.execute("DELETE FROM external_source_metadata WHERE source=?", [SOURCE])
            con.execute(
                "INSERT INTO external_source_metadata VALUES (?, ?, 'CC0-1.0', ?, ?, ?, ?, current_timestamp)",
                [SOURCE, DATASET_URL, snapshot_season, data_as_of, len(profiles), len(stats)],
            )
            mark_fresh(con, SOURCE, fingerprint)  # local naive time, like every other source
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.unregister("incoming_open_players")
            con.unregister("incoming_open_stats")
            con.unregister("incoming_match_contexts")
            con.unregister("incoming_event_timeline")
            con.unregister("incoming_event_lineups")
            con.unregister("incoming_tournament_matches")
            con.unregister("incoming_tournament_goals")
    report = {
        "source": SOURCE, "players": len(profiles), "stat_rows": len(stats),
        "clubs": profiles.team.nunique(), "first_season": first_season,
        "last_season": snapshot_season, "data_as_of": str(data_as_of),
        "match_contexts": len(contexts),
        "timeline_events": len(timeline), "lineup_rows": len(lineups),
        "tournament_matches": len(tournament_matches),
    }
    print(report, flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description="Sync complete featured-club player snapshots")
    parser.add_argument("--refresh", action="store_true", help="Redownload the published snapshot")
    parser.add_argument("--directory", type=Path)
    parser.add_argument("--first-season", type=int, default=2021)
    args = parser.parse_args()
    sync_open_players(directory=args.directory, refresh=args.refresh, first_season=args.first_season)


if __name__ == "__main__":
    main()
