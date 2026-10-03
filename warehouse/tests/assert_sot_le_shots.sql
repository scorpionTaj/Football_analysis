select * from {{ ref('fct_match') }}
where home_sot > home_shots or away_sot > away_shots
