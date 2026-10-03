
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select match_date
from "football"."marts"."fct_match"
where match_date is null



  
  
      
    ) dbt_internal_test