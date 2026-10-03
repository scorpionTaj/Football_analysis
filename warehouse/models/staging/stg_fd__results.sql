-- Every landed Football-Data CSV (2005+, first and second divisions), typed.
-- Raw files are read directly: the landing zone is the raw layer for this source.
with raw as (
    select *
    from read_csv(
        '{{ var("raw_dir") }}/[0-9][0-9][0-9][0-9]/*.csv',
        union_by_name = true, all_varchar = true, header = true,
        filename = true, null_padding = true
    )
),

typed as (
    select
        trim(Div) as league,
        2000 + cast(regexp_extract(filename, '/(\d{2})\d{2}/[^/]+\.csv$', 1) as integer) as season,
        case when length(trim(Date)) = 8 then strptime(trim(Date), '%d/%m/%y')
             else strptime(trim(Date), '%d/%m/%Y') end::date as match_date,
        nullif(trim(Time), '') as kickoff_time,
        trim(HomeTeam) as home_team,
        trim(AwayTeam) as away_team,
        cast(FTHG as integer) as home_goals,
        cast(FTAG as integer) as away_goals,
        try_cast(HTHG as integer) as half_time_home_goals,
        try_cast(HTAG as integer) as half_time_away_goals,
        try_cast(HS as integer) as home_shots_raw,
        try_cast("AS" as integer) as away_shots_raw,
        try_cast(HST as integer) as home_sot_raw,
        try_cast(AST as integer) as away_sot_raw,
        try_cast(HC as integer) as home_corners,
        try_cast(AC as integer) as away_corners,
        try_cast(HF as integer) as home_fouls,
        try_cast(AF as integer) as away_fouls,
        try_cast(HY as integer) as home_yellows,
        try_cast(AY as integer) as away_yellows,
        try_cast(HR as integer) as home_reds,
        try_cast(AR as integer) as away_reds,
        nullif(trim(Referee), '') as referee,
        -- Market average before kick-off (Betbrain average until 2019, then Football-Data's own).
        coalesce(try_cast(AvgH as double), try_cast(BbAvH as double)) as odds_open_home,
        coalesce(try_cast(AvgD as double), try_cast(BbAvD as double)) as odds_open_draw,
        coalesce(try_cast(AvgA as double), try_cast(BbAvA as double)) as odds_open_away,
        -- Pinnacle closing line (2012/13+), the sharpest public benchmark.
        coalesce(try_cast(PSCH as double), try_cast(AvgCH as double)) as odds_close_home,
        coalesce(try_cast(PSCD as double), try_cast(AvgCD as double)) as odds_close_draw,
        coalesce(try_cast(PSCA as double), try_cast(AvgCA as double)) as odds_close_away,
        filename as source_file
    from raw
    where nullif(trim(HomeTeam), '') is not null and nullif(trim(FTHG), '') is not null
)

select
    * exclude (home_shots_raw, away_shots_raw, home_sot_raw, away_sot_raw),
    -- Quarantine impossible shot pairs (same rule as adapters.normalize).
    case when home_sot_raw > home_shots_raw then null else home_shots_raw end as home_shots,
    case when away_sot_raw > away_shots_raw then null else away_shots_raw end as away_shots,
    case when home_sot_raw > home_shots_raw then null else home_sot_raw end as home_sot,
    case when away_sot_raw > away_shots_raw then null else away_sot_raw end as away_sot
from typed
