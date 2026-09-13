import pandas as pd

from football_analysis.open_players import build_frames


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
