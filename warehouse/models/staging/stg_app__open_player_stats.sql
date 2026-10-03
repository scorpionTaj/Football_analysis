select source, player_id, team, season, competition_id, competition, competition_type,
       appearances, goals, assists, minutes_played, yellow_cards, red_cards,
       data_as_of, fetched_at
from {{ source('app', 'open_player_stats') }}
