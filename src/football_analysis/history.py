"""Land long-run Football-Data CSVs untouched for the warehouse and model training.

The dashboard keeps its validated five-season `matches` table. This command only
fills the raw landing zone (`data/raw/<yyYY>/<league>.csv`) that dbt reads directly,
including second divisions and closing odds, so models can learn from ~20 seasons.
"""

from __future__ import annotations

import argparse
import json
import time

from .adapters import FootballDataCSV
from .config import DATA, RECENT_LEAGUES, current_season

SECOND_DIVISIONS = {"E1": "Championship", "SP2": "La Liga 2", "D2": "2. Bundesliga", "I2": "Serie B", "F2": "Ligue 2"}
HISTORY_LEAGUES = [*RECENT_LEAGUES, *SECOND_DIVISIONS]
FIRST_TRAINING_SEASON = 2005


def to_utf8(content: bytes) -> bytes:
    """A few old files are Latin-1; the warehouse reads UTF-8 only. Content is unchanged."""
    try:
        content.decode("utf-8")
        return content
    except UnicodeDecodeError:
        return content.decode("latin-1").encode("utf-8")


def season_code(year: int) -> str:
    return f"{year % 100:02d}{(year + 1) % 100:02d}"


def fetch_history(leagues=None, years=None, raw_dir=DATA / "raw", refresh=False):
    """Download missing season files; completed seasons are immutable once landed."""
    current = current_season()
    years = years or range(FIRST_TRAINING_SEASON, current + 1)
    session = FootballDataCSV(raw_dir).session
    report = []
    for year in years:
        for league in leagues or HISTORY_LEAGUES:
            code = season_code(year)
            path = raw_dir / code / f"{league}.csv"
            if path.exists() and not refresh and year < current:
                report.append({"league": league, "season": year, "status": "cached"})
                continue
            url = f"https://www.football-data.co.uk/mmz4281/{code}/{league}.csv"
            try:
                response = session.get(url, timeout=(10, 60))
                response.raise_for_status()
                if not response.content.strip() or b"Div" not in response.content[:200]:
                    raise ValueError("Not a Football-Data CSV")
                path.parent.mkdir(parents=True, exist_ok=True)
                tmp = path.with_suffix(".tmp")
                tmp.write_bytes(to_utf8(response.content))
                tmp.replace(path)
                report.append({"league": league, "season": year, "status": "success", "bytes": len(response.content)})
                time.sleep(1)  # courtesy interval
            except Exception as exc:
                report.append({"league": league, "season": year, "status": "failed", "detail": str(exc)[:200]})
            print(json.dumps(report[-1]), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description="Land long-run Football-Data CSVs for training")
    parser.add_argument("--leagues", nargs="+", default=None)
    parser.add_argument("--from-season", type=int, default=FIRST_TRAINING_SEASON)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    report = fetch_history(args.leagues, range(args.from_season, current_season() + 1), refresh=args.refresh)
    print(json.dumps({s: sum(r["status"] == s for r in report) for s in ("success", "cached", "failed")}))


if __name__ == "__main__":
    main()
