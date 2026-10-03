select source, lineup_id, event_id, team, player_id, player, position, is_home, is_substitute,
       shirt_number, cutout_url, fetched_at
from {{ source('app', 'event_lineups') }}
