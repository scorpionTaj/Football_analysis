
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select home_goals
from "football"."marts"."fct_match"
where home_goals is null



  
  
      
    ) dbt_internal_test