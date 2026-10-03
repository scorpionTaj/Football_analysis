select league, season, team, count(*) as played, sum(points) as points,
       count(*) filter (where points = 3) as wins,
       count(*) filter (where points = 1) as draws,
       count(*) filter (where points = 0) as losses,
       sum(gf) as goals_for, sum(ga) as goals_against, sum(gf - ga) as goal_difference,
       avg(points) as points_per_game, avg(gf) as goals_per_game, avg(ga) as conceded_per_game,
       100.0 * avg(case when points = 3 then 1 else 0 end) as win_rate,
       count(*) filter (where ga = 0) as clean_sheets
from {{ ref('mart_dashboard_team_match') }}
group by league, season, team
