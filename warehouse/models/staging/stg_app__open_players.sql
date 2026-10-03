-- Tracked first-team players from the Transfermarkt CC0 snapshot (data_as_of = upstream cutoff).
select source, player_id, team_id, team, player, position, sub_position, nationality,
       date_born, foot, height_cm, market_value_eur, highest_market_value_eur,
       image_url, profile_url, last_season, data_as_of, fetched_at
from {{ source('app', 'open_players') }}
