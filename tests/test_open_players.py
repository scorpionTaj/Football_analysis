import pandas as pd

from football_analysis.open_players import (
    build_frames,
    build_match_context_frame,
    build_match_detail_frames,
    build_transfermarkt_tournament_frames,
)


def _write(frame, path):
    frame.to_csv(path, index=False, compression="gzip")
    return path


def test_open_player_snapshot_and_five_season_aggregation(tmp_path):
    paths = {
        "players": _write(pd.DataFrame([{
            "player_id": 7, "current_club_id": 418, "name": "Example Player",
            "position": "Attack", "sub_position": "Centre-Forward",
            "country_of_citizenship": "Testland", "date_of_birth": "2000-01-02",
            "foot": "right", "height_in_cm": 184, "market_value_in_eur": 10_000_000,
            "highest_market_value_in_eur": 15_000_000, "image_url": "https://example.test/p.jpg",
            "url": "https://example.test/player", "last_season": 2025,
        }]), tmp_path / "players.csv.gz"),
        "games": _write(pd.DataFrame([
            {"game_id": 1, "season": 2021, "competition_id": "CL"},
            {"game_id": 2, "season": 2025, "competition_id": "ES1"},
            {"game_id": 3, "season": 2020, "competition_id": "ES1"},
        ]), tmp_path / "games.csv.gz"),
        "appearances": _write(pd.DataFrame([
            {"game_id": 1, "player_id": 7, "competition_id": "CL", "date": "2021-09-01", "goals": 1, "assists": 2, "minutes_played": 90, "yellow_cards": 1, "red_cards": 0},
            {"game_id": 2, "player_id": 7, "competition_id": "ES1", "date": "2026-05-20", "goals": 2, "assists": 0, "minutes_played": 80, "yellow_cards": 0, "red_cards": 0},
            {"game_id": 3, "player_id": 7, "competition_id": "ES1", "date": "2021-05-20", "goals": 9, "assists": 9, "minutes_played": 90, "yellow_cards": 0, "red_cards": 0},
        ]), tmp_path / "appearances.csv.gz"),
        "competitions": _write(pd.DataFrame([
            {"competition_id": "CL", "name": "uefa-champions-league", "type": "international_cup"},
            {"competition_id": "ES1", "name": "laliga", "type": "domestic_league"},
        ]), tmp_path / "competitions.csv.gz"),
    }

    profiles, stats, data_as_of, snapshot = build_frames(paths)

    assert snapshot == 2025
    assert data_as_of.isoformat() == "2026-05-20"
    assert profiles.loc[0, "team"] == "Real Madrid"
    assert len(stats) == 2
    assert stats.goals.sum() == 3
    assert stats.assists.sum() == 2
    assert stats.minutes_played.sum() == 170


def test_match_context_normalizes_real_formation_and_coach_data(tmp_path):
    games = _write(pd.DataFrame([{
        "game_id": 42, "competition_id": "GB1", "season": 2025,
        "date": "2026-04-11", "home_club_name": "Arsenal FC",
        "away_club_name": "Liverpool FC", "home_club_manager_name": "Mikel Arteta",
        "away_club_manager_name": "Arne Slot", "home_club_formation": "4-3-3",
        "away_club_formation": "4-2-3-1", "stadium": "Emirates Stadium",
        "attendance": 60200, "referee": "Example Referee", "url": "https://example.test/game/42",
    }]), tmp_path / "games-context.csv.gz")

    context = build_match_context_frame(games)

    assert context.loc[0, "match_id"] == "42"
    assert context.loc[0, "home_formation"] == "4-3-3"
    assert context.loc[0, "away_coach"] == "Arne Slot"
    assert context.loc[0, "attendance"] == 60200


def test_match_detail_and_cup_frames_keep_players_cards_misses_and_images(tmp_path):
    paths = {
        "games": _write(pd.DataFrame([{
            "game_id": 42, "competition_id": "FAC", "season": 2025,
            "round": "Final", "date": "2026-05-16", "home_club_id": 11,
            "away_club_id": 31, "home_club_name": "Arsenal FC",
            "away_club_name": "Liverpool FC", "home_club_goals": 2,
            "away_club_goals": 1, "stadium": "Wembley", "url": "memory",
        }]), tmp_path / "games.csv.gz"),
        "players": _write(pd.DataFrame([
            {"player_id": 7, "name": "Home Player", "image_url": "https://example.test/home.jpg"},
            {"player_id": 8, "name": "Away Player", "image_url": "https://example.test/away.jpg"},
        ]), tmp_path / "players.csv.gz"),
        "game_events": _write(pd.DataFrame([
            {"game_event_id": "goal", "game_id": 42, "minute": 12, "type": "Goals", "club_id": 11, "club_name": "Arsenal FC", "player_id": 7, "description": "Right-footed shot", "player_in_id": None, "player_assist_id": None},
            {"game_event_id": "red", "game_id": 42, "minute": 72, "type": "Cards", "club_id": 31, "club_name": "Liverpool FC", "player_id": 8, "description": "Red card, Serious foul", "player_in_id": None, "player_assist_id": None},
            {"game_event_id": "miss", "game_id": 42, "minute": 120, "type": "Shootout", "club_id": 31, "club_name": "Liverpool FC", "player_id": 8, "description": ", Missed", "player_in_id": None, "player_assist_id": None},
            {"game_event_id": "fallback", "game_id": 42, "minute": 88, "type": "Goals", "club_id": 11, "club_name": "Arsenal", "player_id": 9, "description": "Header", "player_in_id": None, "player_assist_id": None},
        ]), tmp_path / "game_events.csv.gz"),
        "game_lineups": _write(pd.DataFrame([
            {"game_lineups_id": "lineup", "game_id": 42, "player_id": 7,
             "club_id": 11, "player_name": "Home Player", "type": "starting_lineup",
             "position": "Centre-Forward", "number": 9},
            {"game_lineups_id": "fallback-lineup", "game_id": 42, "player_id": 9,
             "club_id": 11, "player_name": "Lineup-only Scorer", "type": "substitutes",
             "position": "Centre-Forward", "number": 19},
        ]), tmp_path / "game_lineups.csv.gz"),
    }

    timeline, lineups = build_match_detail_frames(paths)
    matches, goals = build_transfermarkt_tournament_frames(paths)

    assert set(timeline.event_type) == {"Goal", "Red card", "Missed penalty"}
    assert lineups.loc[0, "cutout_url"] == "https://example.test/home.jpg"
    assert lineups.loc[0, "position"] == "Centre-Forward"
    assert matches.loc[0, "competition"] == "FAC"
    assert set(goals.player) == {"Home Player", "Lineup-only Scorer"}
    assert timeline.loc[timeline.player_id == "9", "player"].iloc[0] == "Lineup-only Scorer"
    # game_events spells the club "Arsenal" while games.csv says "Arsenal FC": goals must use the match's side.
    assert set(goals.team) <= {matches.loc[0, "home_team"], matches.loc[0, "away_team"]}


def test_match_detail_accepts_source_without_events_or_lineups(tmp_path):
    paths = {
        "games": _write(pd.DataFrame([{"game_id": 1, "competition_id": "FAC", "season": 2025,
                                       "date": "2026-05-01", "home_club_id": 11,
                                       "away_club_id": 31, "home_club_name": "Arsenal",
                                       "away_club_name": "Liverpool"}]), tmp_path / "games.csv.gz"),
        "players": _write(pd.DataFrame(columns=["player_id", "name", "image_url"]), tmp_path / "players.csv.gz"),
        "game_events": _write(pd.DataFrame(columns=["game_event_id", "game_id", "minute", "type", "club_id",
                                                     "club_name", "player_id", "description", "player_in_id",
                                                     "player_assist_id"]), tmp_path / "game_events.csv.gz"),
        "game_lineups": _write(pd.DataFrame(columns=["game_lineups_id", "game_id", "player_id", "club_id",
                                                     "player_name", "type", "position", "number"]),
                               tmp_path / "game_lineups.csv.gz"),
    }
    timeline, lineups = build_match_detail_frames(paths)
    assert timeline.empty and lineups.empty
