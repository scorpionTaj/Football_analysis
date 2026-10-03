
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select elo_diff
from "football"."ml"."ml_match_features"
where elo_diff is null



  
  
      
    ) dbt_internal_test