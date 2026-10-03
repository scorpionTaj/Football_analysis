-- Every goal event belongs to a stored match of the same competition, season and date.
select g.*
from {{ ref('fct_tournament_goal') }} g
anti join {{ ref('fct_tournament_match') }} m using (competition, season, match_date)
