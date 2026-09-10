import pandas as pd
import pytest

from football_analysis.analytics import elo_history, shot_coverage, team_shot_efficiency


def matches():
    return pd.DataFrame([
        {"league": "E0", "season": 2024, "match_date": "2024-08-01", "home_team": "A", "away_team": "B", "home_goals": 2, "away_goals": 0, "home_shots": 10, "away_shots": 5, "home_sot": 5, "away_sot": 2},
        {"league": "E0", "season": 2024, "match_date": "2024-08-02", "home_team": "B", "away_team": "A", "home_goals": 1, "away_goals": 1, "home_shots": None, "away_shots": 8, "home_sot": None, "away_sot": 3},
    ])


def test_elo_uses_only_prior_matches_and_is_zero_sum():
    history = elo_history(matches())
    first = history[history.match_date == pd.Timestamp("2024-08-01")]
    assert set(first.pre_elo) == {1500.0}
    assert first.elo_change.sum() == pytest.approx(0)
    second_a = history[(history.match_date == pd.Timestamp("2024-08-02")) & (history.team == "A")].iloc[0]
    first_a = first[first.team == "A"].iloc[0]
    assert second_a.pre_elo == pytest.approx(first_a.post_elo)


def test_same_day_order_does_not_change_pre_match_ratings():
    frame = pd.concat([matches().iloc[:1], pd.DataFrame([{
        "league": "E0", "season": 2024, "match_date": "2024-08-01", "home_team": "C", "away_team": "A",
        "home_goals": 0, "away_goals": 1, "home_shots": 7, "away_shots": 9, "home_sot": 1, "away_sot": 4,
    }])], ignore_index=True)
    history = elo_history(frame)
    assert set(history.pre_elo) == {1500.0}


def test_shot_coverage_and_gate():
    frame = matches()
    coverage = shot_coverage(frame).iloc[0]
    assert coverage.coverage_pct == 50
    team_matches = pd.DataFrame([
        {"league": "E0", "season": 2024, "team": "A", "shots": 10, "shots_on_target": 5, "gf": 2},
        {"league": "E0", "season": 2024, "team": "A", "shots": None, "shots_on_target": None, "gf": 1},
    ])
    assert team_shot_efficiency(team_matches).empty
    result = team_shot_efficiency(team_matches, minimum_coverage=0.5).iloc[0]
    assert result.shot_accuracy_pct == 50
    assert result.goals_per_shot_pct == 20
