-- A team playing twice on one date would let same-day results leak into features.
with appearances as (
    select match_date, home_team as team from {{ ref('ml_match_features') }}
    union all
    select match_date, away_team from {{ ref('ml_match_features') }}
)
select match_date, team, count(*) from appearances group by all having count(*) > 1
