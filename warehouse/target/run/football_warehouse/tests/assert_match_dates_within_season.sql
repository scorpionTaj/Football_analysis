
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- European seasons run July..June (covid-delayed 2019/20 finished by August 2020).
select * from "football"."marts"."fct_match"
where match_date < make_date(season, 7, 1) or match_date > make_date(season + 1, 8, 31)
  
  
      
    ) dbt_internal_test