-- fct_match nulls closing prices whose margin is outside 0.98..1.25, so testing fct_match itself
-- can never fail. Test the source instead: quarantine must stay rare (2 of ~75k rows today);
-- a jump means a feed or column-mapping change, not a few bad prices.
with priced as (
    select 1 / odds_close_home + 1 / odds_close_draw + 1 / odds_close_away as overround
    from {{ ref('stg_fd__results') }}
    where odds_close_home > 1 and odds_close_draw > 1 and odds_close_away > 1
)
select count(*) filter (where overround < 0.98 or overround > 1.25) as quarantined, count(*) as priced
from priced
having count(*) filter (where overround < 0.98 or overround > 1.25) > 0.01 * count(*)
