select
    league, season, team,
    count(*) as played,
    sum(points) as points,
    count(*) filter (where points = 3) as wins,
    count(*) filter (where points = 1) as draws,
    count(*) filter (where points = 0) as losses,
    sum(gf) as goals_for,
    sum(ga) as goals_against,
    sum(gf) - sum(ga) as goal_difference,
    round(avg(points), 3) as points_per_game,
    round(avg(gf), 3) as goals_per_game,
    round(avg(ga), 3) as conceded_per_game,
    rank() over (partition by league, season order by sum(points) desc, sum(gf) - sum(ga) desc, sum(gf) desc) as position
from "football"."intermediate"."int_team_matches"
group by league, season, team