from pathlib import Path
from streamlit.testing.v1 import AppTest
from football_analysis import config
from football_analysis.adapters import LocalCSV
from football_analysis.ingest import ingest
from test_pipeline import fixture, raw


def test_dashboard_filters_and_empty_selection(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB', tmp_path/'test.duckdb')
    path = tmp_path/'raw'/'2425'
    path.mkdir(parents=True)
    (path/'E0.csv').write_bytes(raw(fixture()))
    ingest(LocalCSV(tmp_path/'raw'), config.DB, [2024], ['E0'])
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run(timeout=20)
    assert not app.exception
    assert app.metric[0].value == '2'
    app.sidebar.multiselect[2].set_value(['Arsenal']).run()
    assert not app.exception
    assert app.metric[0].value == '1'
    assert app.metric[1].value == '38'
    app.sidebar.multiselect[2].set_value([]).run()
    assert not app.exception
    assert 'Choose at least' in app.info[0].value


def test_missing_database(tmp_path, monkeypatch):
    monkeypatch.setattr(config, 'DB', tmp_path/'absent.duckdb')
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py')).run()
    assert not app.exception
    assert 'database' in app.info[0].value
