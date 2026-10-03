-- At most 120 minutes (extra time) per appearance, and no minutes without an appearance.
select * from {{ ref('fct_player_competition_season') }}
where minutes_played > 120 * appearances
