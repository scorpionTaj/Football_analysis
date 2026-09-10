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
        record = con.sql("SELECT played,wins,draws,losses,goals_for,goals_against,points,clean_sheets FROM team_seasons WHERE team='Arsenal'").fetchone()
        assert record == (38,19,0,19,38,38,57,19)
        assert con.sql('SELECT count(*) FROM matches WHERE home_shots IS NULL').fetchone()[0] == 380
    path.write_bytes(raw(fixture().iloc[:-1]))
    assert ingest(adapter, db, [2024], ['E0'])[0]['status'] == 'failed'
    with connect(db) as con:
        assert con.sql('SELECT count(*) FROM matches').fetchone()[0] == 380
        assert con.sql("SELECT count(*) FROM ingestion_runs WHERE status='failed'").fetchone()[0] == 1
