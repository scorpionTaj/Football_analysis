select source, timeline_id, event_id, minute, event_type, detail, team, player_id, player,
       assist, is_home, comment, fetched_at
from {{ source('app', 'event_timeline') }}
