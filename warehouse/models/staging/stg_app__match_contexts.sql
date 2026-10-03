-- Manager, formation, venue and referee per match (Transfermarkt CC0 game records).
select source, match_id, competition_id, season, match_date, home_team, away_team,
       home_coach, away_coach, home_formation, away_formation, stadium, attendance, referee,
       source_url, fetched_at
from {{ source('app', 'match_contexts') }}
