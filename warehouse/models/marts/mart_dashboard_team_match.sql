-- Two rows per dashboard match, one from each team's perspective.
select league, season, match_date, home_team as team, away_team as opponent, 'Home' as venue,
       home_goals as gf, away_goals as ga, home_shots as shots, home_sot as shots_on_target,
       case when home_goals > away_goals then 3 when home_goals = away_goals then 1 else 0 end as points
from {{ ref('mart_dashboard_match') }}
union all
select league, season, match_date, away_team, home_team, 'Away', away_goals, home_goals, away_shots, away_sot,
       case when away_goals > home_goals then 3 when away_goals = home_goals then 1 else 0 end
from {{ ref('mart_dashboard_match') }}
