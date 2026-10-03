
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
select league, season, team, count(*) as n
from "football"."marts"."mart_team_season"
group by all
having count(*) > 1

  
  
      
    ) dbt_internal_test