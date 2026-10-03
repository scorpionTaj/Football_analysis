-- Per-team, per-match Elo from the same engine the model uses (football_analysis.ml.features):
-- pre-match ratings come from ml_match_features; the post-match update is the engine's formula.
-- assert_elo_post_equals_next_pre proves this SQL and the Python engine agree.
with played as (
    select league, season, match_date::date as match_date, home_team, away_team,
           home_elo * 400 as home_pre, away_elo * 400 as away_pre, home_goals, away_goals
    from {{ ref('ml_match_features') }}
    where outcome >= 0
),

updated as (
    select
        *,
        {{ var('elo_k') }}
            * case when abs(home_goals - away_goals) <= 1 then 1.0
                   else log10(abs(home_goals - away_goals) + 1) * 2.2 end
            * (case when home_goals > away_goals then 1.0 when home_goals < away_goals then 0.0 else 0.5 end
               - 1 / (1 + power(10, (away_pre - home_pre - {{ var('elo_home') }}) / 400))) as change
    from played
)

select league, season, match_date, home_team as team, away_team as opponent, 'Home' as venue,
       home_pre as pre_elo, home_pre + change as post_elo, change as elo_change
from updated
union all
select league, season, match_date, away_team, home_team, 'Away',
       away_pre, away_pre - change, -change
from updated
