{{ config(severity='warn') }}
-- Goal events whose club spelling matches neither side of the stored match (provider name variants).
-- Warn only: the Match Centre falls back to the match's own sides.
select g.*
from {{ ref('fct_tournament_goal') }} g
anti join {{ ref('fct_tournament_match') }} m
    on m.competition = g.competition and m.season = g.season and m.match_date = g.match_date
   and g.team in (m.home_team, m.away_team)
