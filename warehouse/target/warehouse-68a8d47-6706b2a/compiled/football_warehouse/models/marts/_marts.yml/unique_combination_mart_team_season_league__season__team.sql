
select league, season, team, count(*) as n
from "football"."marts"."mart_team_season"
group by all
having count(*) > 1
