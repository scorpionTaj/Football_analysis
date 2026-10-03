-- Completed top-five seasons must contain every home/away pairing exactly once
-- Known exception: Ligue 1 2019/20 was abandoned in March 2020 (COVID-19) at 279 matches.
with completed as (
    select league, season, count(*) as matches,
           count(distinct home_team) as teams
    from {{ ref('fct_match') }}
    where league in ('E0', 'SP1', 'D1', 'I1', 'F1')
      and season < (select max(season) from {{ ref('fct_match') }})
      and not (league = 'F1' and season = 2019)
    group by all
)
select * from completed where matches <> teams * (teams - 1)
