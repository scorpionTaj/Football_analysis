from datetime import date, timedelta

import pandas as pd

from football_analysis.ingest import connect
from football_analysis.transfers import sync_transfers


def test_transfer_sync_uses_csvs_and_excludes_future_rows(tmp_path):
    pd.DataFrame([
        {"club_id": 11, "name": "Arsenal", "domestic_competition_id": "GB1"},
        {"club_id": 22, "name": "Valencia", "domestic_competition_id": "ES1"},
    ]).to_csv(tmp_path / "clubs.csv.gz", index=False)
    pd.DataFrame([{"player_id": 7, "image_url": "https://example.test/7.jpg"}]).to_csv(
        tmp_path / "players.csv.gz", index=False,
    )
    pd.DataFrame([
        {"player_id": 7, "player_name": "Example", "transfer_date": "2026-09-03",
         "transfer_season": "26/27", "from_club_id": 22, "to_club_id": 11,
         "from_club_name": "Old", "to_club_name": "Old", "transfer_fee": 100,
         "market_value_in_eur": 200},
        {"player_id": 7, "player_name": "Future", "transfer_date": str(date.today() + timedelta(days=1)),
         "transfer_season": "26/27", "from_club_id": 22, "to_club_id": 11,
         "from_club_name": "Old", "to_club_name": "Old", "transfer_fee": 100,
         "market_value_in_eur": 200},
    ]).to_csv(tmp_path / "transfers.csv.gz", index=False)

    db = tmp_path / "transfers.duckdb"
    assert sync_transfers(db=db, directory=tmp_path) == 1
    assert sync_transfers(db=db, directory=tmp_path) == 1
    with connect(db) as con:
        rows = con.execute(
            "SELECT player_name, season, from_competition, to_competition, "
            "from_club_name, to_club_name, image_url FROM transfers",
        ).fetchall()
    assert rows == [("Example", 2026, "SP1", "E0", "Valencia", "Arsenal", "https://example.test/7.jpg")]
