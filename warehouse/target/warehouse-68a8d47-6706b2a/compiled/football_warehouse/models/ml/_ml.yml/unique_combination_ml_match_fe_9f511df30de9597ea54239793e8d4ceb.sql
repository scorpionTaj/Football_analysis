
select league, season, match_date, home_team, away_team, count(*) as n
from "football"."ml"."ml_match_features"
group by all
having count(*) > 1
