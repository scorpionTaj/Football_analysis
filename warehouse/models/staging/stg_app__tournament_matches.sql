-- Cup, continental and international results (OpenFootball, Transfermarkt CC0, TheSportsDB sample).
select competition, season, stage, group_name, match_date, home_team, away_team,
       home_goals, away_goals, home_penalties, away_penalties, venue, neutral, status,
       source, source_url, fetched_at
from {{ source('app', 'tournament_matches') }}
