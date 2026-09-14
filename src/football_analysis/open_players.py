"""Complete featured-club player snapshots from the CC0 Transfermarkt dataset."""

import argparse
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import DATA, DB
from .ingest import connect


SOURCE = "Transfermarkt Open Dataset"
DATASET_URL = "https://github.com/dcaribou/transfermarkt-datasets"
DOWNLOAD_BASE = "https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data"
FILES = ("players", "games", "appearances", "competitions")
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
    """Download the four published CSVs required by the player importer."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    session = _session()
    paths = {}
    for name in FILES:
        path = directory / f"{name}.csv.gz"
        if refresh or not path.exists():
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


def _sql_path(path):
    return str(Path(path).resolve()).replace("'", "''")


def build_frames(paths, first_season=2021, last_season=None):
    """Return current featured-club profiles and five-season appearance totals."""
    last_season = last_season if last_season is not None else max(
        pd.read_csv(paths["players"], usecols=["last_season"])["last_season"]
    )
    club_map = pd.DataFrame(
        [{"club_id": club_id, "team": team} for club_id, team in CLUB_MAP.items()]
    )
    now = datetime.now()
    with duckdb.connect() as con:
        con.register("club_map", club_map)
        players_path = _sql_path(paths["players"])
        games_path = _sql_path(paths["games"])
        appearances_path = _sql_path(paths["appearances"])
        competitions_path = _sql_path(paths["competitions"])
        latest_match = con.execute(
            f"SELECT max(a.date)::DATE FROM read_csv_auto('{appearances_path}') a "
            f"JOIN read_csv_auto('{games_path}') g USING(game_id) "
            "WHERE g.season BETWEEN ? AND ?",
            [first_season, last_season],
        ).fetchone()[0]
        profiles = con.execute(
            f"""
            SELECT '{SOURCE}' AS source, p.player_id::VARCHAR AS player_id,
                   p.current_club_id::VARCHAR AS team_id, m.team,
                   p.name AS player, coalesce(p.position, '') AS position,
                   coalesce(p.sub_position, '') AS sub_position,
                   coalesce(p.country_of_citizenship, '') AS nationality,
                   try_cast(p.date_of_birth AS DATE) AS date_born,
                   coalesce(p.foot, '') AS foot,
                   try_cast(p.height_in_cm AS INTEGER) AS height_cm,
                   try_cast(p.market_value_in_eur AS BIGINT) AS market_value_eur,
                   try_cast(p.highest_market_value_in_eur AS BIGINT) AS highest_market_value_eur,
                   coalesce(p.image_url, '') AS image_url,
                   coalesce(p.url, '') AS profile_url,
                   p.last_season::INTEGER AS last_season,
                   ?::DATE AS data_as_of, ?::TIMESTAMP AS fetched_at
            FROM read_csv_auto('{players_path}') p
            JOIN club_map m ON p.current_club_id = m.club_id
            WHERE p.last_season = ?
            ORDER BY m.team, p.position, p.name
            """,
            [latest_match, now, last_season],
        ).df()
        con.register("featured_players", profiles[["player_id", "team"]])
        stats = con.execute(
            f"""
            SELECT '{SOURCE}' AS source, a.player_id::VARCHAR AS player_id,
                   fp.team, g.season::INTEGER AS season,
                   a.competition_id::VARCHAR AS competition_id,
                   replace(coalesce(c.name, a.competition_id), '-', ' ') AS competition,
                   coalesce(c.type, '') AS competition_type,
                   count(*)::INTEGER AS appearances,
                   sum(coalesce(a.goals, 0))::INTEGER AS goals,
                   sum(coalesce(a.assists, 0))::INTEGER AS assists,
                   sum(coalesce(a.minutes_played, 0))::INTEGER AS minutes_played,
                   sum(coalesce(a.yellow_cards, 0))::INTEGER AS yellow_cards,
                   sum(coalesce(a.red_cards, 0))::INTEGER AS red_cards,
                   ?::DATE AS data_as_of, ?::TIMESTAMP AS fetched_at
            FROM read_csv_auto('{appearances_path}') a
            JOIN featured_players fp ON a.player_id::VARCHAR = fp.player_id
            JOIN read_csv_auto('{games_path}') g USING(game_id)
            LEFT JOIN read_csv_auto('{competitions_path}') c
              ON c.competition_id = a.competition_id
            WHERE g.season BETWEEN ? AND ?
            GROUP BY a.player_id, fp.team, g.season, a.competition_id, c.name, c.type
            ORDER BY fp.team, a.player_id, g.season, a.competition_id
            """,
            [latest_match, now, first_season, last_season],
        ).df()
    return profiles, stats, latest_match, last_season


def build_match_context_frame(games_path):
    """Normalize the published real-match manager, formation and venue context."""
    now = datetime.now()
    path = _sql_path(games_path)
    with duckdb.connect() as con:
        return con.execute(
            f"""
            SELECT '{SOURCE}' AS source, game_id::VARCHAR AS match_id,
                   coalesce(competition_id, '')::VARCHAR AS competition_id,
                   try_cast(season AS INTEGER) AS season, try_cast(date AS DATE) AS match_date,
                   coalesce(home_club_name, '') AS home_team,
                   coalesce(away_club_name, '') AS away_team,
                   coalesce(home_club_manager_name, '') AS home_coach,
                   coalesce(away_club_manager_name, '') AS away_coach,
                   coalesce(home_club_formation, '') AS home_formation,
                   coalesce(away_club_formation, '') AS away_formation,
                   coalesce(stadium, '') AS stadium,
                   try_cast(attendance AS INTEGER) AS attendance,
                   coalesce(referee, '') AS referee,
                   coalesce(url, '') AS source_url,
                   ?::TIMESTAMP AS fetched_at
            FROM read_csv_auto('{path}', all_varchar=true)
            WHERE try_cast(date AS DATE) IS NOT NULL
              AND coalesce(home_club_name, '') <> ''
              AND coalesce(away_club_name, '') <> ''
            ORDER BY match_date DESC, match_id
            """,
            [now],
        ).df()


def sync_open_players(db=DB, directory=None, refresh=False, first_season=2021):
    directory = Path(directory or DATA / "external" / "transfermarkt")
    paths = download_snapshot(directory, refresh=refresh)
    profiles, stats, data_as_of, snapshot_season = build_frames(
        paths, first_season=first_season,
    )
    contexts = build_match_context_frame(paths["games"])
    with connect(db) as con:
        con.register("incoming_open_players", profiles)
        con.register("incoming_open_stats", stats)
        con.register("incoming_match_contexts", contexts)
        con.execute("BEGIN")
        try:
            con.execute("DELETE FROM open_player_stats WHERE source=?", [SOURCE])
            con.execute("DELETE FROM open_players WHERE source=?", [SOURCE])
            con.execute("INSERT INTO open_players SELECT * FROM incoming_open_players")
            con.execute("INSERT INTO open_player_stats SELECT * FROM incoming_open_stats")
            con.execute("DELETE FROM match_contexts WHERE source=?", [SOURCE])
            con.execute("INSERT INTO match_contexts SELECT * FROM incoming_match_contexts")
            con.execute("DELETE FROM external_source_metadata WHERE source=?", [SOURCE])
            con.execute(
                "INSERT INTO external_source_metadata VALUES (?, ?, 'CC0-1.0', ?, ?, ?, ?, current_timestamp)",
                [SOURCE, DATASET_URL, snapshot_season, data_as_of, len(profiles), len(stats)],
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.unregister("incoming_open_players")
            con.unregister("incoming_open_stats")
            con.unregister("incoming_match_contexts")
    report = {
        "source": SOURCE, "players": len(profiles), "stat_rows": len(stats),
        "clubs": profiles.team.nunique(), "first_season": first_season,
        "last_season": snapshot_season, "data_as_of": str(data_as_of),
        "match_contexts": len(contexts),
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
