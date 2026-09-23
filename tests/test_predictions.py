import numpy as np
import pandas as pd

from football_analysis.predictions import (
    FEATURES, build_match_features, fit_softmax, future_features, train_time_split,
)


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


def test_holdout_baseline_uses_training_prevalence():
    features = build_match_features(sample_matches())
    _, _, train, validation, _, metrics = train_time_split(features)
    training_rates = train.actual_result.value_counts(normalize=True)
    expected = -np.log(validation.actual_result.map(training_rates)).mean()
    assert np.isclose(metrics["baseline_log_loss"], expected)
