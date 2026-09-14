"""Transfer market sync and queries from Transfermarkt dataset."""

from datetime import datetime
from pathlib import Path
import duckdb
from .config import DATA, DB

COMP_MAP = {
    'GB1': 'E0',
    'ES1': 'SP1',
    'L1': 'D1',
    'IT1': 'I1',
    'FR1': 'F1',
    'NL1': 'N1',
    'PO1': 'P1',
    'BE1': 'B1',
    'TR1': 'T1',
    'GR1': 'G1',
}


def sync_transfers(db=DB, directory=None):
    directory = Path(directory or DATA / "external" / "transfermarkt")
    transfers_path = str((directory / "transfers.csv.gz").resolve()).replace("'", "''")
    clubs_path = str((directory / "clubs.csv.gz").resolve()).replace("'", "''")
    players_path = str((directory / "players.csv.gz").resolve()).replace("'", "''")

    with duckdb.connect(str(db)) as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS transfers (
            transfer_id VARCHAR,
            player_id VARCHAR,
            player_name VARCHAR,
            transfer_date DATE,
            transfer_season VARCHAR,
            season INTEGER,
            from_club_id VARCHAR,
            from_club_name VARCHAR,
            to_club_id VARCHAR,
            to_club_name VARCHAR,
            transfer_fee DOUBLE,
            market_value_eur BIGINT,
            from_competition VARCHAR,
            to_competition VARCHAR,
            image_url VARCHAR
        );
        """)
        con.execute("DELETE FROM transfers;")
        con.execute(f"""
        INSERT INTO transfers
        SELECT 
            md5(concat(t.player_id::VARCHAR, t.transfer_date::VARCHAR, coalesce(t.from_club_id::VARCHAR, '0'), coalesce(t.to_club_id::VARCHAR, '0'))) AS transfer_id,
            t.player_id::VARCHAR AS player_id,
            t.player_name,
            try_cast(t.transfer_date AS DATE) AS transfer_date,
            t.transfer_season,
            CASE 
                WHEN t.transfer_season = '21/22' THEN 2021
                WHEN t.transfer_season = '22/23' THEN 2022
                WHEN t.transfer_season = '23/24' THEN 2023
                WHEN t.transfer_season = '24/25' THEN 2024
                WHEN t.transfer_season = '25/26' THEN 2025
                WHEN t.transfer_season = '26/27' THEN 2026
                ELSE try_cast(substr(t.transfer_season, 1, 2) AS INTEGER) + 2000
            END AS season,
            t.from_club_id::VARCHAR AS from_club_id,
            coalesce(c_from.name, t.from_club_name) AS from_club_name,
            t.to_club_id::VARCHAR AS to_club_id,
            coalesce(c_to.name, t.to_club_name) AS to_club_name,
            try_cast(t.transfer_fee AS DOUBLE) AS transfer_fee,
            try_cast(t.market_value_in_eur AS BIGINT) AS market_value_eur,
            coalesce(c_from.domestic_competition_id, '') AS from_competition,
            coalesce(c_to.domestic_competition_id, '') AS to_competition,
            p.image_url
        FROM read_csv_auto('{transfers_path}') t
        LEFT JOIN read_csv_auto('{clubs_path}') c_to ON t.to_club_id = c_to.club_id
        LEFT JOIN read_csv_auto('{clubs_path}') c_from ON t.from_club_id = c_from.club_id
        LEFT JOIN read_csv_auto('{players_path}') p ON t.player_id = p.player_id
        WHERE t.transfer_date >= '2021-01-01' AND t.transfer_date <= '2026-09-01'
          AND (c_to.domestic_competition_id IN ('GB1', 'ES1', 'L1', 'IT1', 'FR1', 'NL1', 'PO1', 'BE1', 'TR1', 'GR1')
               OR c_from.domestic_competition_id IN ('GB1', 'ES1', 'L1', 'IT1', 'FR1', 'NL1', 'PO1', 'BE1', 'TR1', 'GR1'))
        ORDER BY transfer_date DESC;
        """)

        for tm_code, our_code in COMP_MAP.items():
            con.execute("UPDATE transfers SET from_competition = ? WHERE from_competition = ?", [our_code, tm_code])
            con.execute("UPDATE transfers SET to_competition = ? WHERE to_competition = ?", [our_code, tm_code])

        count = con.execute("SELECT count(*) FROM transfers").fetchone()[0]
        return count
