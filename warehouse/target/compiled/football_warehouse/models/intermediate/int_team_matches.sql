-- Two rows per match: the team's perspective.
select match_id, league, season, match_date, home_team as team, away_team as opponent, 'Home' as venue,
       home_goals as gf, away_goals as ga, home_shots as shots, home_sot as shots_on_target,
       case result when 'H' then 3 when 'D' then 1 else 0 end as points
from "football"."marts"."fct_match"
union all
select match_id, league, season, match_date, away_team, home_team, 'Away',
       away_goals, home_goals, away_shots, away_sot,
       case result when 'A' then 3 when 'D' then 1 else 0 end
from "football"."marts"."fct_match"