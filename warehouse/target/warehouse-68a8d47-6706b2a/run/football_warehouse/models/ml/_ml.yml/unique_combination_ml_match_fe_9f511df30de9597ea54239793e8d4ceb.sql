
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
select league, season, match_date, home_team, away_team, count(*) as n
from "football"."ml"."ml_match_features"
group by all
having count(*) > 1

  
  
      
    ) dbt_internal_test