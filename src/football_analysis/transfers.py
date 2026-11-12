"""Transfer market sync from the published Transfermarkt CSV snapshot."""

from datetime import date
from hashlib import md5, sha256
from pathlib import Path

import pandas as pd

from .config import DATA, DB
from .ingest import connect
from .sync_state import cached_fingerprint, mark_fresh


COMP_MAP = {
    "GB1": "E0", "ES1": "SP1", "L1": "D1", "IT1": "I1", "FR1": "F1",
    "NL1": "N1", "PO1": "P1", "BE1": "B1", "TR1": "T1", "GR1": "G1",
}


def _ids(values):
    return pd.to_numeric(values, errors="coerce").astype("Int64").astype(str).replace("<NA>", "")


def sync_transfers(db=DB, directory=None):
    directory = Path(directory or DATA / "external" / "transfermarkt")
    fingerprint = sha256(b"transfer-import-v2")
    for name in ("transfers", "clubs", "players"):
        fingerprint.update((directory / f"{name}.csv.gz").read_bytes())
    fingerprint.update(date.today().isoformat().encode())
    digest = fingerprint.hexdigest()
    with connect(db) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS transfers (
                transfer_id VARCHAR, player_id VARCHAR, player_name VARCHAR, transfer_date DATE,
                transfer_season VARCHAR, season INTEGER, from_club_id VARCHAR, from_club_name VARCHAR,
                to_club_id VARCHAR, to_club_name VARCHAR, transfer_fee DOUBLE PRECISION,
                market_value_eur BIGINT, from_competition VARCHAR, to_competition VARCHAR, image_url VARCHAR
            )
        """)
        if cached_fingerprint(con, "transfermarkt-transfers") == digest:
            count = con.execute("SELECT count(*) FROM transfers").fetchall()[0][0]
            if count:
                return count
    transfers = pd.read_csv(directory / "transfers.csv.gz")
    clubs = pd.read_csv(
        directory / "clubs.csv.gz", usecols=["club_id", "name", "domestic_competition_id"],
    ).set_index("club_id")
    players = pd.read_csv(
        directory / "players.csv.gz", usecols=["player_id", "image_url"],
    ).set_index("player_id")
    transfers["transfer_date"] = pd.to_datetime(transfers.transfer_date, errors="coerce").dt.date
    transfers = transfers[
        transfers.transfer_date.between(date(2021, 1, 1), date.today())
    ].copy()
    for side in ("from", "to"):
        club = transfers[f"{side}_club_id"].map(clubs.name)
        transfers[f"{side}_club_name"] = club.fillna(transfers[f"{side}_club_name"])
        transfers[f"{side}_competition"] = transfers[f"{side}_club_id"].map(
            clubs.domestic_competition_id,
        )
    transfers = transfers[
        transfers.from_competition.isin(COMP_MAP) | transfers.to_competition.isin(COMP_MAP)
    ].copy()
    for side in ("from", "to"):
        transfers[f"{side}_club_id"] = _ids(transfers[f"{side}_club_id"])
        transfers[f"{side}_competition"] = transfers[f"{side}_competition"].map(COMP_MAP).fillna("")
    transfers["player_id"] = _ids(transfers.player_id)
    transfers["season"] = pd.to_numeric(
        transfers.transfer_season.astype(str).str.slice(0, 2), errors="coerce",
    ).add(2000).astype("Int64")
    transfers["transfer_id"] = transfers.apply(
        lambda row: md5((row.player_id + str(row.transfer_date) +
                         (row.from_club_id or "0") + (row.to_club_id or "0")).encode()).hexdigest(),
        axis=1,
    )
    transfers["image_url"] = pd.to_numeric(transfers.player_id).map(players.image_url).fillna("")
    transfers["market_value_eur"] = pd.to_numeric(transfers.market_value_in_eur, errors="coerce")
    transfers["transfer_fee"] = pd.to_numeric(transfers.transfer_fee, errors="coerce")
    frame = transfers[[
        "transfer_id", "player_id", "player_name", "transfer_date", "transfer_season", "season",
        "from_club_id", "from_club_name", "to_club_id", "to_club_name", "transfer_fee",
        "market_value_eur", "from_competition", "to_competition", "image_url",
    ]].sort_values("transfer_date", ascending=False)
    if frame.empty:
        raise ValueError("Transfer snapshot has no eligible rows; preserving existing transfers")
    with connect(db) as con:
        con.register("incoming_transfers", frame)
        con.execute("BEGIN")
        try:
            con.execute("DELETE FROM transfers")
            con.execute("INSERT INTO transfers SELECT * FROM incoming_transfers")
            mark_fresh(con, "transfermarkt-transfers", digest)
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.unregister("incoming_transfers")
    return len(frame)
