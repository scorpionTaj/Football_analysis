import numpy as np
import pandas as pd
import duckdb

from football_analysis.predictions import (
    FEATURES, _confidence_backtest, _outcome_backtest, build_match_features, fit_softmax,
    future_features, sync_predictions, train_time_split, walk_forward_backtest,
)
from football_analysis.ingest import connect
from football_analysis.config import current_season
from datetime import date, timedelta


def sample_matches(count=150):
    teams = ["Arsenal", "Liverpool", "Chelsea", "Man City"]
    rows = []
    for index in range(count):
        home = teams[index % 4]
        away = teams[(index + 1 + (index // 4) % 2) % 4]
        if home == away:
            away = teams[(index + 2) % 4]
        rows.append({
            "league": "E0", "season": 2024 + (index >= 100),
            "match_date": pd.Timestamp("2024-08-01") + pd.to_timedelta(index, unit="D"),
            "home_team": home, "away_team": away,
            "home_goals": (index * 3) % 4, "away_goals": (index * 5 + 1) % 3,
        })
    return pd.DataFrame(rows)


def test_softmax_probabilities_are_normalized():
    rng = np.random.default_rng(4)
    features = rng.normal(size=(90, len(FEATURES)))
    labels = np.tile([0, 1, 2], 30)
    model = fit_softmax(features, labels, iterations=100)
    probabilities = model.predict_proba(features[:8])
    assert np.allclose(probabilities.sum(axis=1), 1)
    assert (probabilities >= 0).all()


def test_time_split_is_chronological_and_reports_baseline():
    features = build_match_features(sample_matches())
    _, cutoff, train, validation, probabilities, metrics = train_time_split(features)
    assert train.match_date.max() <= cutoff < validation.match_date.min()
    assert len(probabilities) == len(validation)
    assert 0 <= metrics["accuracy"] <= 1
    assert metrics["baseline_log_loss"] > 0
    assert 0.6 <= metrics["temperature"] <= 1.8
    assert metrics["calibration_matches"] > 0
    assert metrics["high_confidence_threshold"] == 0.75
    assert sum(row["matches"] for row in metrics["league_backtest"]) == len(validation)
    assert sum(row["matches"] for row in metrics["outcome_backtest"]) == len(validation)


def test_future_features_do_not_require_or_invent_an_outcome():
    matches = sample_matches(20)
    fixtures = pd.DataFrame([{
        "league": "E0", "season": 2024, "match_date": pd.Timestamp("2025-04-01"),
        "home_team": "Arsenal", "away_team": "Chelsea",
    }])
    future = future_features(matches, fixtures)
    assert len(future) == 1
    assert future[list(FEATURES)].notna().all(axis=None)


def test_shot_form_uses_only_prior_match_days():
    matches = pd.DataFrame([
        {"league": "E0", "season": 2024, "match_date": "2024-08-01",
         "home_team": "Arsenal", "away_team": "Liverpool", "home_goals": 2,
         "away_goals": 0, "home_sot": 10, "away_sot": 1},
        {"league": "E0", "season": 2024, "match_date": "2024-08-01",
         "home_team": "Arsenal", "away_team": "Chelsea", "home_goals": 1,
         "away_goals": 1, "home_sot": 9, "away_sot": 2},
        {"league": "E0", "season": 2024, "match_date": "2024-08-08",
         "home_team": "Arsenal", "away_team": "Man City", "home_goals": 0,
         "away_goals": 1, "home_sot": 3, "away_sot": 5},
    ])
    features = build_match_features(matches)
    assert features.iloc[0].home_sot_for == 4.4
    assert features.iloc[1].home_sot_for == 4.4
    assert features.iloc[2].home_sot_for == 9.5


def test_opening_form_carries_five_matches_from_previous_season_only():
    matches = pd.DataFrame([
        {"league": "E0", "season": 2024, "match_date": date(2024, 8, 1) + timedelta(days=day),
         "home_team": "Arsenal", "away_team": "Liverpool", "home_goals": 2, "away_goals": 0}
        for day in range(6)
    ] + [
        {"league": "E0", "season": season, "match_date": date(season, 8, 1),
         "home_team": "Arsenal", "away_team": "Liverpool", "home_goals": 1, "away_goals": 0}
        for season in (2025, 2027)
    ])
    features = build_match_features(matches)
    assert features.loc[features.season == 2025, "home_form_ppg"].iloc[0] == 1.0
    assert features.loc[features.season == 2025, "away_form_ppg"].iloc[0] == 0.0
    assert features.loc[features.season == 2027, "home_form_ppg"].iloc[0] == 1 / 3


def test_holdout_baseline_uses_training_prevalence():
    features = build_match_features(sample_matches())
    _, _, train, validation, _, metrics = train_time_split(features)
    training_rates = train.actual_result.value_counts(normalize=True)
    expected = -np.log(validation.actual_result.map(training_rates)).mean()
    assert np.isclose(metrics["baseline_log_loss"], expected)


def test_confidence_backtest_reports_coverage_and_uncertainty():
    probabilities = np.array([
        [0.8, 0.1, 0.1], [0.1, 0.1, 0.8], [0.4, 0.3, 0.3],
    ])
    metrics = _confidence_backtest(probabilities, [0, 0, 1])
    assert metrics["high_confidence_matches"] == 2
    assert np.isclose(metrics["high_confidence_coverage"], 2 / 3)
    assert metrics["high_confidence_accuracy"] == 0.5
    assert metrics["high_confidence_low95"] < 0.5 < metrics["high_confidence_high95"]


def test_outcome_backtest_exposes_missed_draws():
    probabilities = np.array([[0.8, 0.1, 0.1], [0.6, 0.3, 0.1], [0.1, 0.1, 0.8]])
    rows = _outcome_backtest(probabilities, [0, 1, 2])
    draw = next(row for row in rows if row["outcome"] == "Draw")
    assert draw["matches"] == 1
    assert draw["predicted"] == 0
    assert draw["recall"] == 0
    assert draw["precision"] is None


def test_walk_forward_uses_only_earlier_seasons():
    features = build_match_features(sample_matches())
    rows = walk_forward_backtest(features)
    assert len(rows) == 1
    assert rows[0]["season"] == 2025
    assert rows[0]["matches"] == 50


def test_published_forecast_survives_retraining_and_is_resolved(tmp_path):
    db = tmp_path / "predictions.duckdb"
    matches = sample_matches()
    matches["match_date"] = matches.match_date.dt.date
    matches["home_team"] = [f"Home {index}" for index in range(len(matches))]
    matches["away_team"] = [f"Away {index}" for index in range(len(matches))]
    fixture_date = date.today() + timedelta(days=7)
    season = current_season()
    with connect(db) as con:
        con.register("sample_matches", matches)
        con.execute(
            "INSERT INTO matches (league, season, match_date, home_team, away_team, home_goals, away_goals) "
            "SELECT league, season, match_date, home_team, away_team, home_goals, away_goals FROM sample_matches"
        )
        con.execute(
            "INSERT INTO recent_events (event_id, league, season, match_date, home_team, away_team, "
            "event_kind, source, fetched_at) VALUES "
            "('fixture-1', 'E0', ?, ?, 'Arsenal', 'Liverpool', 'fixture', 'test', current_timestamp)",
            [season, fixture_date],
        )
    sync_predictions(db)
    with connect(db) as con:
        assert con.execute("SELECT count(*) FROM forecast_history").fetchone()[0] == 1
        con.execute(
            "INSERT INTO recent_matches (league, season, match_date, home_team, away_team, "
            "home_goals, away_goals, source, fetched_at) VALUES "
            "('E0', ?, ?, 'Arsenal', 'Liverpool', 2, 0, 'test', current_timestamp)",
            [season, fixture_date],
        )
    sync_predictions(db)
    with connect(db) as con:
        issued, actual = con.execute(
            "SELECT count(*), max(actual_result) FROM forecast_history"
        ).fetchone()
        assert issued == 1
        assert actual == "Home"


def test_forecast_history_schema_expands_without_erasing_existing_models(tmp_path):
    db = tmp_path / "legacy.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute(
            "CREATE TABLE prediction_models (model_id VARCHAR PRIMARY KEY, model_name VARCHAR, "
            "trained_at TIMESTAMP, validation_cutoff DATE, train_matches INTEGER, validation_matches INTEGER, "
            "feature_names VARCHAR, parameters VARCHAR, metrics VARCHAR)"
        )
        con.execute(
            "INSERT INTO prediction_models VALUES ('legacy', 'old model', current_timestamp, "
            "'2025-01-01', 100, 20, '[]', '{}', '{}')"
        )
    with connect(db) as con:
        assert con.execute("SELECT model_id FROM prediction_models").fetchone()[0] == "legacy"
        assert con.execute("SELECT count(*) FROM forecast_history").fetchone()[0] == 0
