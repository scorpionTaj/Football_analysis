-- Scores OpenFootball published before Football-Data's CSV (no statistics, no odds).
-- fct_match uses them only for matches the CSV does not have yet.
select league, season, match_date, home_team, away_team, home_goals, away_goals
from {{ source('app', 'recent_matches') }}
where source = 'OpenFootball results (CC0, provisional)'
