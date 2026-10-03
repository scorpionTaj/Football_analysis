
    
    

with all_values as (

    select
        venue as value_field,
        count(*) as n_records

    from "football"."intermediate"."int_team_matches"
    group by venue

)

select *
from all_values
where value_field not in (
    'Home','Away'
)


