
    
    

with all_values as (

    select
        outcome as value_field,
        count(*) as n_records

    from "football"."ml"."ml_match_features"
    group by outcome

)

select *
from all_values
where value_field not in (
    -1,0,1,2
)


