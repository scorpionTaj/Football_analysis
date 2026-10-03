
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  select * from "football"."marts"."fct_match"
where home_sot > home_shots or away_sot > away_shots
  
  
      
    ) dbt_internal_test