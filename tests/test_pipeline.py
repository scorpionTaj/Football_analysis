from datetime import date
from io import StringIO
import pandas as pd
import pytest
from football_analysis.adapters import normalize, LocalCSV
from football_analysis.config import seasons
from football_analysis.ingest import ingest, connect


def fixture():
    clubs = ['Arsenal', 'Liverpool'] + [f'Club {i}' for i in range(18)]
    rows = [dict(Div='E0', Date='01/08/2024', HomeTeam=h, AwayTeam=a, FTHG=2, FTAG=0, FTR='H') for h in clubs for a in clubs if h != a]
    return pd.DataFrame(rows)


def raw(df):
    return df.to_csv(index=False).encode()


def test_season_rollover():
    assert seasons(date(2026,9,10)) == [2021,2022,2023,2024,2025]
    assert seasons(date(2026,6,30)) == [2020,2021,2022,2023,2024]
    assert seasons(date(2026,7,1))[-1] == 2025


@pytest.mark.parametrize('fault', ['missing','duplicate','score','result','date','league','team','fraction'])
def test_reject_corrupt_partition(fault):
    df = fixture()
    if fault == 'missing': df = df.iloc[:-1]
    if fault == 'duplicate': df.iloc[-1] = df.iloc[0]
    if fault == 'score': df.loc[0,'FTHG'] = -1
    if fault == 'result': df.loc[0,'FTR'] = 'A'
    if fault == 'date': df.loc[0,'Date'] = '01/08/2023'
    if fault == 'league': df.loc[0,'Div'] = 'SP1'
    if fault == 'team': df.loc[0,'HomeTeam'] = ''
    if fault == 'fraction': df['FTHG'] = 1.5
    with pytest.raises(ValueError): normalize(raw(df), 'E0', 2024, 'test')


def test_replay_idempotency_and_failed_refresh_preserves_data(tmp_path):
    directory = tmp_path/'raw'/'2425'
    directory.mkdir(parents=True)
    path = directory/'E0.csv'
    path.write_bytes(raw(fixture()))
    adapter = LocalCSV(tmp_path/'raw')
    db = tmp_path/'test.duckdb'
    for _ in range(2):
        assert ingest(adapter, db, [2024], ['E0'])[0]['status'] == 'success'
    with connect(db) as con:
        assert con.sql('SELECT count(*) FROM matches').fetchone()[0] == 380
        assert con.sql("SELECT count(*) FROM ingestion_runs WHERE status='success'").fetchone()[0] == 1
        record = con.sql("SELECT played,wins,draws,losses,goals_for,goals_against,points,clean_sheets FROM team_seasons WHERE team='Arsenal'").fetchone()
        assert record == (38,19,0,19,38,38,57,19)
        assert con.sql('SELECT count(*) FROM matches WHERE home_shots IS NULL').fetchone()[0] == 380
    path.write_bytes(raw(fixture().iloc[:-1]))
    assert ingest(adapter, db, [2024], ['E0'])[0]['status'] == 'failed'
    with connect(db) as con:
        assert con.sql('SELECT count(*) FROM matches').fetchone()[0] == 380
        assert con.sql("SELECT count(*) FROM ingestion_runs WHERE status='failed'").fetchone()[0] == 1


def test_impossible_shot_pair_is_quarantined():
    df = fixture()
    df["HS"] = 10
    df["HST"] = 4
    df["AS"] = 8
    df["AST"] = 3
    df.loc[0, "HST"] = 11
    batch = normalize(raw(df), "E0", 2024, "test")
    assert pd.isna(batch.frame.loc[0, "home_shots"])
    assert pd.isna(batch.frame.loc[0, "home_sot"])
    assert batch.frame.loc[1, "home_shots"] == 10


def test_optional_match_context_is_preserved():
    df = fixture()
    df["HTHG"], df["HTAG"], df["HC"], df["AC"] = 1, 0, 7, 4
    df["HF"], df["AF"], df["HY"], df["AY"], df["HR"], df["AR"] = 11, 9, 2, 3, 0, 1
    df["Referee"] = "Example Referee"
    frame = normalize(raw(df), "E0", 2024, "test").frame
    assert frame.loc[0, "half_time_home_goals"] == 1
    assert frame.loc[0, "home_corners"] == 7
    assert frame.loc[0, "away_reds"] == 1
    assert frame.loc[0, "referee"] == "Example Referee"


def test_partial_current_season_keeps_only_completed_matches():
    df = fixture().head(3).copy()
    pending = df.iloc[[0]].copy()
    pending[["FTHG", "FTAG", "FTR"]] = None
    frame = pd.concat([df, pending], ignore_index=True)
    batch = normalize(raw(frame), "E0", 2024, "test", require_complete=False)
    assert len(batch.frame) == 3


def test_ingestion_persists_derived_analytics(tmp_path):
    directory = tmp_path / "raw" / "2425"
    directory.mkdir(parents=True)
    (directory / "E0.csv").write_bytes(raw(fixture()))
    db = tmp_path / "test.duckdb"
    ingest(LocalCSV(tmp_path / "raw"), db, [2024], ["E0"])
    with connect(db) as con:
        assert con.sql("SELECT count(*) FROM elo_ratings").fetchone()[0] == 760
        assert con.sql("SELECT match_rows FROM analytics_metadata").fetchone()[0] == 380
