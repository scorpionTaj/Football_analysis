CREATE TABLE IF NOT EXISTS matches (
 league VARCHAR NOT NULL, season INTEGER NOT NULL, match_date DATE NOT NULL,
 home_team VARCHAR NOT NULL, away_team VARCHAR NOT NULL,
 home_goals INTEGER NOT NULL CHECK(home_goals >= 0), away_goals INTEGER NOT NULL CHECK(away_goals >= 0),
 home_shots INTEGER, away_shots INTEGER, home_sot INTEGER, away_sot INTEGER,
 half_time_home_goals INTEGER, half_time_away_goals INTEGER,
 home_corners INTEGER, away_corners INTEGER, home_fouls INTEGER, away_fouls INTEGER,
 home_yellows INTEGER, away_yellows INTEGER, home_reds INTEGER, away_reds INTEGER,
 referee VARCHAR,
 PRIMARY KEY(league, season, home_team, away_team), CHECK(home_team <> away_team),
 CHECK(home_sot IS NULL OR home_shots IS NULL OR home_sot <= home_shots),
 CHECK(away_sot IS NULL OR away_shots IS NULL OR away_sot <= away_shots)
);
ALTER TABLE matches ADD COLUMN IF NOT EXISTS half_time_home_goals INTEGER;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS half_time_away_goals INTEGER;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_corners INTEGER;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_corners INTEGER;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_fouls INTEGER;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_fouls INTEGER;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_yellows INTEGER;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_yellows INTEGER;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS home_reds INTEGER;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS away_reds INTEGER;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS referee VARCHAR;
CREATE TABLE IF NOT EXISTS ingestion_runs (
 run_id VARCHAR PRIMARY KEY, league VARCHAR, season INTEGER, source_url VARCHAR,
 sha256 VARCHAR, row_count INTEGER, status VARCHAR, detail VARCHAR,
 fetched_at TIMESTAMP DEFAULT current_timestamp
);
CREATE TABLE IF NOT EXISTS reference_standings (
 source VARCHAR NOT NULL, league VARCHAR NOT NULL, season INTEGER NOT NULL,
 rank INTEGER NOT NULL, team VARCHAR NOT NULL, played INTEGER, points INTEGER,
 goal_difference INTEGER, form VARCHAR, description VARCHAR,
 source_updated_at TIMESTAMP, fetched_at TIMESTAMP,
 PRIMARY KEY(source, league, season, rank)
);
CREATE TABLE IF NOT EXISTS elo_ratings (
 league VARCHAR NOT NULL, season INTEGER NOT NULL, match_date DATE NOT NULL,
 team VARCHAR NOT NULL, opponent VARCHAR NOT NULL, venue VARCHAR NOT NULL,
 pre_elo DOUBLE NOT NULL, post_elo DOUBLE NOT NULL, elo_change DOUBLE NOT NULL,
 PRIMARY KEY(league, season, match_date, team, opponent, venue)
);
CREATE TABLE IF NOT EXISTS shot_efficiency_cache (
 league VARCHAR NOT NULL, season INTEGER NOT NULL, team VARCHAR NOT NULL,
 matches INTEGER NOT NULL, coverage_pct DOUBLE NOT NULL,
 shots_per_match DOUBLE, shot_accuracy_pct DOUBLE,
 goals_per_shot_pct DOUBLE, goals_per_sot_pct DOUBLE,
 PRIMARY KEY(league, season, team)
);
CREATE TABLE IF NOT EXISTS analytics_metadata (
 cache_key VARCHAR PRIMARY KEY, refreshed_at TIMESTAMP NOT NULL,
 match_rows INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS recent_matches (
 league VARCHAR NOT NULL, season INTEGER NOT NULL, match_date DATE NOT NULL,
 home_team VARCHAR NOT NULL, away_team VARCHAR NOT NULL,
 home_goals INTEGER NOT NULL, away_goals INTEGER NOT NULL,
 home_shots INTEGER, away_shots INTEGER, home_sot INTEGER, away_sot INTEGER,
 half_time_home_goals INTEGER, half_time_away_goals INTEGER,
 home_corners INTEGER, away_corners INTEGER, home_fouls INTEGER, away_fouls INTEGER,
 home_yellows INTEGER, away_yellows INTEGER, home_reds INTEGER, away_reds INTEGER,
 referee VARCHAR,
 source VARCHAR NOT NULL, fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(league, season, home_team, away_team), CHECK(home_team <> away_team)
);
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS half_time_home_goals INTEGER;
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS half_time_away_goals INTEGER;
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS home_corners INTEGER;
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS away_corners INTEGER;
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS home_fouls INTEGER;
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS away_fouls INTEGER;
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS home_yellows INTEGER;
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS away_yellows INTEGER;
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS home_reds INTEGER;
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS away_reds INTEGER;
ALTER TABLE recent_matches ADD COLUMN IF NOT EXISTS referee VARCHAR;
CREATE TABLE IF NOT EXISTS recent_events (
 event_id VARCHAR PRIMARY KEY, league VARCHAR NOT NULL, season INTEGER NOT NULL,
 match_date DATE NOT NULL, home_team VARCHAR NOT NULL, away_team VARCHAR NOT NULL,
 home_goals INTEGER, away_goals INTEGER, status VARCHAR, event_kind VARCHAR NOT NULL,
 source VARCHAR NOT NULL, fetched_at TIMESTAMP NOT NULL,
 kickoff_time VARCHAR, venue VARCHAR, home_coach VARCHAR, away_coach VARCHAR,
 home_formation VARCHAR, away_formation VARCHAR, referee VARCHAR, attendance INTEGER
);
ALTER TABLE recent_events ADD COLUMN IF NOT EXISTS kickoff_time VARCHAR;
ALTER TABLE recent_events ADD COLUMN IF NOT EXISTS venue VARCHAR;
ALTER TABLE recent_events ADD COLUMN IF NOT EXISTS home_coach VARCHAR;
ALTER TABLE recent_events ADD COLUMN IF NOT EXISTS away_coach VARCHAR;
ALTER TABLE recent_events ADD COLUMN IF NOT EXISTS home_formation VARCHAR;
ALTER TABLE recent_events ADD COLUMN IF NOT EXISTS away_formation VARCHAR;
ALTER TABLE recent_events ADD COLUMN IF NOT EXISTS referee VARCHAR;
ALTER TABLE recent_events ADD COLUMN IF NOT EXISTS attendance INTEGER;
CREATE TABLE IF NOT EXISTS tournament_matches (
 competition VARCHAR NOT NULL, season INTEGER NOT NULL, stage VARCHAR NOT NULL,
 group_name VARCHAR, match_date DATE NOT NULL,
 home_team VARCHAR NOT NULL, away_team VARCHAR NOT NULL,
 home_goals INTEGER NOT NULL CHECK(home_goals >= 0),
 away_goals INTEGER NOT NULL CHECK(away_goals >= 0),
 home_penalties INTEGER, away_penalties INTEGER, venue VARCHAR,
 neutral BOOLEAN NOT NULL, status VARCHAR NOT NULL,
 source VARCHAR NOT NULL, source_url VARCHAR NOT NULL,
 fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(competition, season, match_date, home_team, away_team),
 CHECK(home_team <> away_team)
);
CREATE TABLE IF NOT EXISTS tournament_goals (
 competition VARCHAR NOT NULL, season INTEGER NOT NULL, match_date DATE NOT NULL,
 team VARCHAR NOT NULL, player VARCHAR NOT NULL, minute VARCHAR,
 penalty BOOLEAN NOT NULL, own_goal BOOLEAN NOT NULL,
 source VARCHAR NOT NULL, source_url VARCHAR NOT NULL, fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(competition, season, match_date, team, player, minute)
);
CREATE TABLE IF NOT EXISTS event_statistics (
 source VARCHAR NOT NULL, event_id VARCHAR NOT NULL, statistic VARCHAR NOT NULL,
 home_value DOUBLE, away_value DOUBLE, fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(source, event_id, statistic)
);
CREATE TABLE IF NOT EXISTS event_timeline (
 source VARCHAR NOT NULL, timeline_id VARCHAR NOT NULL, event_id VARCHAR NOT NULL,
 minute VARCHAR, event_type VARCHAR, detail VARCHAR, team VARCHAR, player_id VARCHAR,
 player VARCHAR, assist VARCHAR, is_home BOOLEAN, comment VARCHAR, fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(source, timeline_id)
);
CREATE TABLE IF NOT EXISTS event_lineups (
 source VARCHAR NOT NULL, lineup_id VARCHAR NOT NULL, event_id VARCHAR NOT NULL,
 team VARCHAR, player_id VARCHAR, player VARCHAR, position VARCHAR,
 is_home BOOLEAN, is_substitute BOOLEAN, shirt_number VARCHAR, cutout_url VARCHAR,
 fetched_at TIMESTAMP NOT NULL, PRIMARY KEY(source, lineup_id)
);
CREATE TABLE IF NOT EXISTS match_contexts (
 source VARCHAR NOT NULL, match_id VARCHAR NOT NULL, competition_id VARCHAR,
 season INTEGER, match_date DATE NOT NULL, home_team VARCHAR NOT NULL, away_team VARCHAR NOT NULL,
 home_coach VARCHAR, away_coach VARCHAR, home_formation VARCHAR, away_formation VARCHAR,
 stadium VARCHAR, attendance INTEGER, referee VARCHAR, source_url VARCHAR,
 fetched_at TIMESTAMP NOT NULL, PRIMARY KEY(source, match_id)
);
CREATE TABLE IF NOT EXISTS prediction_models (
 model_id VARCHAR PRIMARY KEY, model_name VARCHAR NOT NULL, trained_at TIMESTAMP NOT NULL,
 validation_cutoff DATE NOT NULL, train_matches INTEGER NOT NULL, validation_matches INTEGER NOT NULL,
 feature_names VARCHAR NOT NULL, parameters VARCHAR NOT NULL, metrics VARCHAR NOT NULL
);
CREATE TABLE IF NOT EXISTS match_predictions (
 model_id VARCHAR NOT NULL, prediction_kind VARCHAR NOT NULL, league VARCHAR NOT NULL,
 season INTEGER NOT NULL, match_date DATE NOT NULL, home_team VARCHAR NOT NULL,
 away_team VARCHAR NOT NULL, actual_result VARCHAR, predicted_result VARCHAR NOT NULL,
 home_probability DOUBLE NOT NULL, draw_probability DOUBLE NOT NULL,
 away_probability DOUBLE NOT NULL,
 PRIMARY KEY(model_id, prediction_kind, league, match_date, home_team, away_team)
);
CREATE TABLE IF NOT EXISTS players (
 source VARCHAR NOT NULL, player_id VARCHAR NOT NULL, team_id VARCHAR NOT NULL,
 team VARCHAR NOT NULL, player VARCHAR NOT NULL, position VARCHAR,
 nationality VARCHAR, date_born DATE, shirt_number VARCHAR, status VARCHAR,
 height VARCHAR, weight VARCHAR, thumb_url VARCHAR, cutout_url VARCHAR,
 fetched_at TIMESTAMP NOT NULL, PRIMARY KEY(source, player_id)
);
CREATE TABLE IF NOT EXISTS player_stats (
 source VARCHAR NOT NULL, player_id VARCHAR NOT NULL, team_id VARCHAR,
 team VARCHAR, league VARCHAR, season VARCHAR, statistic VARCHAR NOT NULL,
 value DOUBLE, fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(source, player_id, league, season, statistic)
);
CREATE TABLE IF NOT EXISTS open_players (
 source VARCHAR NOT NULL, player_id VARCHAR NOT NULL, team_id VARCHAR NOT NULL,
 team VARCHAR NOT NULL, player VARCHAR NOT NULL, position VARCHAR,
 sub_position VARCHAR, nationality VARCHAR, date_born DATE, foot VARCHAR,
 height_cm INTEGER, market_value_eur BIGINT, highest_market_value_eur BIGINT,
 image_url VARCHAR, profile_url VARCHAR, last_season INTEGER NOT NULL,
 data_as_of DATE NOT NULL, fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(source, player_id)
);
CREATE TABLE IF NOT EXISTS open_player_stats (
 source VARCHAR NOT NULL, player_id VARCHAR NOT NULL, team VARCHAR NOT NULL,
 season INTEGER NOT NULL, competition_id VARCHAR NOT NULL,
 competition VARCHAR NOT NULL, competition_type VARCHAR,
 appearances INTEGER NOT NULL, goals INTEGER NOT NULL, assists INTEGER NOT NULL,
 minutes_played INTEGER NOT NULL, yellow_cards INTEGER NOT NULL,
 red_cards INTEGER NOT NULL, data_as_of DATE NOT NULL,
 fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(source, player_id, season, competition_id)
);
CREATE TABLE IF NOT EXISTS external_source_metadata (
 source VARCHAR PRIMARY KEY, dataset_url VARCHAR NOT NULL,
 licence VARCHAR, snapshot_season INTEGER, data_as_of DATE,
 player_rows INTEGER, statistic_rows INTEGER, fetched_at TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS team_media (
 source VARCHAR NOT NULL, team_id VARCHAR NOT NULL, team VARCHAR NOT NULL,
 badge_url VARCHAR, logo_url VARCHAR, banner_url VARCHAR, fanart_url VARCHAR,
 stadium_url VARCHAR, fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(source, team)
);
CREATE TABLE IF NOT EXISTS competition_media (
 source VARCHAR NOT NULL, league_code VARCHAR NOT NULL, league_id VARCHAR NOT NULL,
 league VARCHAR NOT NULL, badge_url VARCHAR, logo_url VARCHAR, banner_url VARCHAR,
 trophy_url VARCHAR, fanart_url VARCHAR, fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(source, league_code)
);
CREATE OR REPLACE VIEW team_matches AS
 SELECT league, season, match_date, home_team AS team, away_team AS opponent, 'Home' AS venue,
 home_goals AS gf, away_goals AS ga, home_shots AS shots, home_sot AS shots_on_target,
 CASE WHEN home_goals > away_goals THEN 3 WHEN home_goals = away_goals THEN 1 ELSE 0 END AS points
 FROM matches
 UNION ALL
 SELECT league, season, match_date, away_team, home_team, 'Away', away_goals, home_goals, away_shots, away_sot,
 CASE WHEN away_goals > home_goals THEN 3 WHEN away_goals = home_goals THEN 1 ELSE 0 END FROM matches;
CREATE OR REPLACE VIEW team_seasons AS
 SELECT league, season, team, count(*) AS played, sum(points) AS points,
 sum(CASE WHEN points=3 THEN 1 ELSE 0 END) AS wins,
 sum(CASE WHEN points=1 THEN 1 ELSE 0 END) AS draws,
 sum(CASE WHEN points=0 THEN 1 ELSE 0 END) AS losses,
 sum(gf) AS goals_for, sum(ga) AS goals_against, sum(gf-ga) AS goal_difference,
 avg(points) AS points_per_game, avg(gf) AS goals_per_game,
 avg(ga) AS conceded_per_game,
 100.0*avg(CASE WHEN points=3 THEN 1 ELSE 0 END) AS win_rate,
 sum(CASE WHEN ga=0 THEN 1 ELSE 0 END) AS clean_sheets
 FROM team_matches GROUP BY league, season, team;
