
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  select * from "football"."marts"."fct_match" where match_date > current_date
  
  
      
    ) dbt_internal_test