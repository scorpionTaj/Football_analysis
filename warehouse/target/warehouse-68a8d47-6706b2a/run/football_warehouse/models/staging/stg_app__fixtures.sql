
  
  create view "football"."staging"."stg_app__fixtures__dbt_tmp" as (
    -- Upcoming domestic fixtures from every provider; names are reconciled downstream
-- (football_analysis.teams.team_key) because providers spell clubs differently.
select league, season, match_date, home_team, away_team, event_kind, source, fetched_at
from "football"."main"."recent_events"
where event_kind in ('next', 'fixture') and match_date >= current_date
  );
