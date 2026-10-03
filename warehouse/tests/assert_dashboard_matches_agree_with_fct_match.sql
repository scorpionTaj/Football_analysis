-- The dashboard's validated results and the 2005+ fact table come from the same Football-Data files:
-- every dashboard match must exist in fct_match with identical scores and statistics.
select d.league, d.season, d.home_team, d.away_team
from {{ ref('mart_dashboard_match') }} d
left join {{ ref('fct_match') }} f using (league, season, home_team, away_team)
where f.match_id is null
   or d.match_date <> f.match_date
   or d.home_goals <> f.home_goals or d.away_goals <> f.away_goals
   or d.home_shots is distinct from f.home_shots or d.away_shots is distinct from f.away_shots
   or d.home_sot is distinct from f.home_sot or d.away_sot is distinct from f.away_sot
   or d.half_time_home_goals is distinct from f.half_time_home_goals
   or d.half_time_away_goals is distinct from f.half_time_away_goals
   or d.home_corners is distinct from f.home_corners or d.away_corners is distinct from f.away_corners
   or d.home_reds is distinct from f.home_reds or d.away_reds is distinct from f.away_reds
   or nullif(d.referee, '') is distinct from f.referee
