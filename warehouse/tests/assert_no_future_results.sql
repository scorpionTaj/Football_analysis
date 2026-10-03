select * from {{ ref('fct_match') }} where match_date > current_date
