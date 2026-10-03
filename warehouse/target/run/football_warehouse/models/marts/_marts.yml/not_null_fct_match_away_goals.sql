
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select away_goals
from "football"."marts"."fct_match"
where away_goals is null



  
  
      
    ) dbt_internal_test