-- One row per played domestic match, 2005+, with margin-free market probabilities.
with results as (
    select r.*, l.league_name, l.country, l.tier, l.in_dashboard
    from {{ ref('stg_fd__results') }} r
    join {{ ref('leagues') }} l using (league)
),

overrounds as (
    select
        *,
        1 / odds_open_home + 1 / odds_open_draw + 1 / odds_open_away as open_overround,
        1 / odds_close_home + 1 / odds_close_draw + 1 / odds_close_away as close_overround
    from results
),

-- Quarantine impossible price sets (bookmaker margin outside 0.98..1.25) instead of
-- letting them distort features or the market benchmark.
priced as (
    select
        * replace (
            case when open_overround between 0.98 and 1.25 then odds_open_home end as odds_open_home,
            case when open_overround between 0.98 and 1.25 then odds_open_draw end as odds_open_draw,
            case when open_overround between 0.98 and 1.25 then odds_open_away end as odds_open_away,
            case when open_overround between 0.98 and 1.25 then open_overround end as open_overround,
            case when close_overround between 0.98 and 1.25 then odds_close_home end as odds_close_home,
            case when close_overround between 0.98 and 1.25 then odds_close_draw end as odds_close_draw,
            case when close_overround between 0.98 and 1.25 then odds_close_away end as odds_close_away,
            case when close_overround between 0.98 and 1.25 then close_overround end as close_overround
        )
    from overrounds
)

select
    {{ dbt_utils_surrogate(['league', 'season', 'match_date', 'home_team', 'away_team']) }} as match_id,
    league, league_name, country, tier, in_dashboard, season, match_date, kickoff_time,
    home_team, away_team, home_goals, away_goals,
    case when home_goals > away_goals then 'H' when home_goals < away_goals then 'A' else 'D' end as result,
    half_time_home_goals, half_time_away_goals,
    home_shots, away_shots, home_sot, away_sot, home_corners, away_corners,
    home_fouls, away_fouls, home_yellows, away_yellows, home_reds, away_reds, referee,
    odds_open_home, odds_open_draw, odds_open_away,
    odds_close_home, odds_close_draw, odds_close_away,
    open_overround, close_overround,
    (1 / odds_close_home) / close_overround as close_p_home,
    (1 / odds_close_draw) / close_overround as close_p_draw,
    (1 / odds_close_away) / close_overround as close_p_away,
    source_file
from priced
