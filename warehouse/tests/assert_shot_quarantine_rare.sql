-- Staging nulls shot pairs where shots on target exceed shots (so downstream rows always pass
-- sot <= shots). Guard the quarantine itself: it must stay a small share of rows with shots.
select count(*) filter (where shots_quarantined) as quarantined, count(*) as rows_with_shots
from {{ ref('stg_fd__results') }}
where home_shots is not null or shots_quarantined
having count(*) filter (where shots_quarantined) > 0.01 * count(*)
