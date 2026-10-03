-- Within a season, a team's post-match Elo must be its next pre-match Elo. Fails if the SQL
-- update in ml_elo_ratings ever drifts from the Python engine in ml/features.py.
with ordered as (
    select team, league, season, match_date, post_elo,
           lead(pre_elo) over (partition by league, season, team order by match_date) as next_pre
    from {{ ref('ml_elo_ratings') }}
)
select * from ordered where next_pre is not null and abs(post_elo - next_pre) > 1e-6
