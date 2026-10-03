-- Validated complete-season results the dashboard shows (top five leagues, last five seasons).
-- Football-Data writes an empty referee as ''; kept as-is so API output does not change.
select league, season, match_date, home_team, away_team, home_goals, away_goals,
       home_shots, away_shots, home_sot, away_sot, half_time_home_goals, half_time_away_goals,
       home_corners, away_corners, home_fouls, away_fouls, home_yellows, away_yellows,
       home_reds, away_reds, referee
from {{ source('app', 'matches') }}
