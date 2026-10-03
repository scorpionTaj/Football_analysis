select competition, season, match_date, team, player, minute,
       penalty, own_goal, source, source_url, fetched_at
from {{ source('app', 'tournament_goals') }}
