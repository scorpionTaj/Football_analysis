CREATE TABLE IF NOT EXISTS matches (
 league VARCHAR NOT NULL, season INTEGER NOT NULL, match_date DATE NOT NULL,
 home_team VARCHAR NOT NULL, away_team VARCHAR NOT NULL,
 home_goals INTEGER NOT NULL CHECK(home_goals >= 0), away_goals INTEGER NOT NULL CHECK(away_goals >= 0),
 home_shots INTEGER, away_shots INTEGER, home_sot INTEGER, away_sot INTEGER,
 PRIMARY KEY(league, season, home_team, away_team), CHECK(home_team <> away_team),
 CHECK(home_sot IS NULL OR home_shots IS NULL OR home_sot <= home_shots),
 CHECK(away_sot IS NULL OR away_shots IS NULL OR away_sot <= away_shots)
);
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
 source VARCHAR NOT NULL, fetched_at TIMESTAMP NOT NULL,
 PRIMARY KEY(league, season, home_team, away_team), CHECK(home_team <> away_team)
);
CREATE TABLE IF NOT EXISTS recent_events (
 event_id VARCHAR PRIMARY KEY, league VARCHAR NOT NULL, season INTEGER NOT NULL,
 match_date DATE NOT NULL, home_team VARCHAR NOT NULL, away_team VARCHAR NOT NULL,
 home_goals INTEGER, away_goals INTEGER, status VARCHAR, event_kind VARCHAR NOT NULL,
 source VARCHAR NOT NULL, fetched_at TIMESTAMP NOT NULL
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
