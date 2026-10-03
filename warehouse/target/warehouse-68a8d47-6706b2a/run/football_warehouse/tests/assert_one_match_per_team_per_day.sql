
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- A team playing twice on one date would let same-day results leak into features.
with appearances as (
    select match_date, home_team as team from "football"."ml"."ml_match_features"
    union all
    select match_date, away_team from "football"."ml"."ml_match_features"
)
select match_date, team, count(*) from appearances group by all having count(*) > 1
  
  
      
    ) dbt_internal_test