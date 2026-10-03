
    
    

with all_values as (

    select
        result as value_field,
        count(*) as n_records

    from "football"."marts"."fct_match"
    group by result

)

select *
from all_values
where value_field not in (
    'H','D','A'
)


