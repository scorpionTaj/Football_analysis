
    
    

with child as (
    select league as from_field
    from "football"."marts"."fct_match"
    where league is not null
),

parent as (
    select league as to_field
    from "football"."reference"."leagues"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


