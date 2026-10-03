
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select league
from "football"."marts"."fct_match"
where league is null



  
  
      
    ) dbt_internal_test