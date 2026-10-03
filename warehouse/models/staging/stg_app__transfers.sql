select transfer_id, player_id, player_name, transfer_date, transfer_season, season,
       from_club_id, from_club_name, to_club_id, to_club_name, transfer_fee, market_value_eur,
       from_competition, to_competition, image_url
from {{ source('app', 'transfers') }}
