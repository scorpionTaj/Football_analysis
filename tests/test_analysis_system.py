import pandas as pd
import pytest

from football_analysis.analysis_system import AnalysisRequest, AnalysisSystem, tournament_team_matches


def match_rows():
    return pd.DataFrame([
        ["E0", 2025, "2025-08-01", "Arsenal", "Liverpool", "Home", 2, 0, 10, 5, 3],
        ["E0", 2025, "2025-08-08", "Arsenal", "Chelsea", "Away", 1, 1, 8, 3, 1],
        ["E0", 2025, "2025-08-15", "Arsenal", "Man City", "Home", 0, 1, 7, 2, 0],
    ], columns=[
        "league", "season", "match_date", "team", "opponent", "venue",
        "gf", "ga", "shots", "shots_on_target", "points",
    ])


def test_analysis_report_filters_and_calculates_rankings_and_form():
    report = AnalysisSystem(match_rows()).build_report(AnalysisRequest(
        competitions=("E0",), seasons=(2025,), teams=("Arsenal",), form_window=2,
    ))
    row = report.rankings.iloc[0]
    assert row.played == 3
    assert row.points_per_game == pytest.approx(4 / 3)
    assert row.form == "D L"
    assert "points_per_game" in report.correlations.columns


def test_analysis_report_can_slice_venue():
    report = AnalysisSystem(match_rows()).build_report(AnalysisRequest(venue="Home"))
    assert len(report.matches) == 2


def test_tournament_matches_expand_to_both_teams():
    source = pd.DataFrame([{
        "competition": "WC", "season": 2026, "match_date": "2026-07-10",
        "home_team": "Morocco", "away_team": "Brazil", "home_goals": 2,
        "away_goals": 1,
    }])
    expanded = tournament_team_matches(source)
    assert len(expanded) == 2
    assert set(expanded.points) == {0, 3}
    assert set(expanded.venue) == {"Neutral"}
