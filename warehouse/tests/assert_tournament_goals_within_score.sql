-- Goal events never exceed a side's final score (events may be incomplete, never extra).
-- Known exceptions: results awarded by the federation, where the events record the match as played
-- (Preußen Münster 2-0 Wolfsburg, DFB-Pokal 2021, substitution breach; Arosa 3-0 Granada, Copa del Rey 2023).
with goals as (
    select competition, season, match_date, team, count(*) as events
    from {{ ref('fct_tournament_goal') }}
    group by all
)
select m.competition, m.season, m.match_date, m.home_team, m.away_team, m.home_goals, m.away_goals,
       h.events as home_events, a.events as away_events
from {{ ref('fct_tournament_match') }} m
left join goals h on h.competition = m.competition and h.season = m.season
    and h.match_date = m.match_date and h.team = m.home_team
left join goals a on a.competition = m.competition and a.season = m.season
    and a.match_date = m.match_date and a.team = m.away_team
where (coalesce(h.events, 0) > m.home_goals or coalesce(a.events, 0) > m.away_goals)
  and not (m.competition = 'DFB' and m.match_date = date '2021-08-08' and m.home_team = 'Preußen Münster')
  and not (m.competition = 'CDR' and m.match_date = date '2023-11-02' and m.home_team = 'Arosa SC')
