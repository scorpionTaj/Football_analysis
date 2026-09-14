from datetime import date, datetime

from football_analysis.api.contracts import (
    AnalysisReportResponse,
    CatalogResponse,
    Competition,
    CorrelationRow,
    Forecast,
    FormRow,
    Match,
    MatchFactorSummary,
    MatchListResponse,
    PageMeta,
    PlayerProfileResponse,
    PlayerSummary,
    PredictionsResponse,
    QualityResponse,
    RankingRow,
    SeasonCoverage,
    SourceMeta,
    TeamRef,
    TournamentResponse,
    canonical_team_id,
)
from football_analysis.api.pagination import decode_cursor, encode_cursor


def source():
    return SourceMeta(source="test", coverage="fixture", freshness=datetime(2026, 9, 14, 12, 0, 0))


def test_canonical_team_ids_are_stable_and_independent_of_display_names():
    assert canonical_team_id("Man City") == canonical_team_id("Manchester City")
    assert canonical_team_id("Paris SG") == "parissaintgermain"
    assert TeamRef.from_name("Ath Madrid").name == "Atlético Madrid"
    assert TeamRef.from_name("Ath Madrid").team_id == canonical_team_id("Atlético Madrid")


def test_catalog_and_match_models_round_trip_json():
    catalog = CatalogResponse(
        competitions=[Competition(
            code="E0", name="Premier League", kind="domestic",
            seasons=[SeasonCoverage(season=2024, label="2024/25", match_count=380, latest_match=date(2025, 5, 25), status="complete")],
            source=source(),
        )],
        current_season=2026,
        generated_at=datetime(2026, 9, 14, 12, 0, 0),
        source=source(),
    )
    restored = CatalogResponse.model_validate(catalog.model_dump(mode="json"))
    assert restored.competitions[0].seasons[0].match_count == 380
    match = Match(
        competition="E0", season=2024, match_date=date(2024, 8, 17),
        home=TeamRef.from_name("Arsenal"), away=TeamRef.from_name("Man City"),
        home_goals=2, away_goals=1, source="football-data.co.uk",
    )
    listed = MatchListResponse(
        matches=[match], page=PageMeta(next_cursor="abc", limit=50, returned=1), source=source(),
    )
    assert MatchListResponse.model_validate(listed.model_dump(mode="json")).matches[0].home.team_id == "arsenal"


def test_analysis_report_json_includes_filters_and_quality_metadata():
    report = AnalysisReportResponse(
        filters={"competitions": ["E0"], "seasons": [2024], "teams": ["arsenal"], "venue": "Home", "form_window": 5},
        match_count=2,
        rankings=[RankingRow(
            competition="E0", season=2024, team=TeamRef.from_name("Arsenal"), rank=1,
            played=2, wins=1, draws=1, losses=0, points=4, goals_for=3, goals_against=1,
            goal_difference=2, points_per_game=2.0, goals_per_game=1.5, conceded_per_game=0.5,
            win_rate=50.0, clean_sheet_rate=50.0, form="W D", form_ppg=2.0,
        )],
        form=[FormRow(
            competition="E0", season=2024, team=TeamRef.from_name("Arsenal"),
            form_matches=2, form_points=4, form_goals_for=3, form_goals_against=1, form="W D", form_ppg=2.0,
        )],
        correlations=[CorrelationRow(metric="points_per_game", points_per_game=1.0)],
        match_factors=MatchFactorSummary(corners_mean=5.5),
        source=source(),
    )
    data = report.model_dump(mode="json")
    assert data["source"]["coverage"] == "fixture"
    assert AnalysisReportResponse.model_validate(data).rankings[0].team.team_id == "arsenal"


def test_player_prediction_tournament_and_quality_contracts_serialize():
    player = PlayerProfileResponse(
        player_id="p1", name="Bukayo Saka", team=TeamRef.from_name("Arsenal"),
        position="Attack", source="transfermarkt", coverage=source(),
    )
    listed = PlayerSummary(
        player_id="p1", name="Bukayo Saka", team=TeamRef.from_name("Arsenal"), source="transfermarkt",
    )
    preds = PredictionsResponse(
        model_id="m1", model_name="softmax", metrics={"accuracy": 0.5},
        forecasts=[Forecast(
            competition="E0", season=2026, match_date=date(2026, 9, 20),
            home=TeamRef.from_name("Arsenal"), away=TeamRef.from_name("Liverpool"),
            predicted_result="Home", home_probability=0.5, draw_probability=0.3, away_probability=0.2,
        )],
        source=source(),
    )
    tourney = TournamentResponse(
        competition="UCL", name="UEFA Champions League", season=2024,
        stages=[], matches=[], scorers=[], source=source(),
    )
    quality = QualityResponse(
        completed_coverage="25/25", live_competitions="10/10", match_records=10,
        impossible_shot_rows=0, source=source(),
    )
    for model in (preds, tourney, quality):
        restored = type(model).model_validate(model.model_dump(mode="json"))
        assert restored.source.source == "test"
    for model in (player, listed):
        restored = type(model).model_validate(model.model_dump(mode="json"))
        assert restored.source == "transfermarkt"
    assert PlayerProfileResponse.model_validate(player.model_dump(mode="json")).coverage.source == "test"


def test_cursor_round_trip():
    token = encode_cursor({"d": "2024-08-17", "c": "E0", "h": "Arsenal", "a": "Liverpool"})
    assert decode_cursor(token)["h"] == "Arsenal"
