"""Pre-match features for every played match and every upcoming fixture."""

import pandas as pd

from football_analysis.ml.features import build_features
from football_analysis.teams import team_key


def reconcile_fixtures(fixtures, played):
    """Map provider names onto Football-Data names; keep one row per upcoming meeting.

    Names are matched per country (not per league) so a club new to a league is still
    found through its lower-division history. A fixture is dropped only when that same
    meeting was played (pairing within 3 days), so play-off rematches keep their forecast.
    """
    names = {}
    for country, group in played.groupby("country"):
        for name in pd.unique(group[["home_team", "away_team"]].values.ravel()):
            names[(country, team_key(name))] = name
    fixtures = fixtures.assign(
        home_team=[names.get((c, team_key(t))) for c, t in zip(fixtures.country, fixtures.home_team)],
        away_team=[names.get((c, team_key(t))) for c, t in zip(fixtures.country, fixtures.away_team)],
        priority=fixtures.event_kind.map({"fixture": 0, "next": 1}),
    ).dropna(subset=["home_team", "away_team"])
    fixtures = fixtures.sort_values(["priority", "match_date", "fetched_at"], ascending=[True, True, False])
    fixtures = fixtures.drop_duplicates(["league", "season", "home_team", "away_team"])
    pair = ["league", "season", "home_team", "away_team"]
    meetings = fixtures[pair + ["match_date"]].reset_index().merge(
        played[pair + ["match_date"]], on=pair, how="inner", suffixes=("", "_played"))
    gap = (pd.to_datetime(meetings.match_date) - pd.to_datetime(meetings.match_date_played)).abs()
    done = set(meetings.loc[gap <= pd.Timedelta(days=3), "index"])
    return fixtures[~fixtures.index.isin(done)][["league", "season", "match_date", "home_team", "away_team", "country", "tier"]]


def model(dbt, session):
    dbt.config(materialized="table")
    played = dbt.ref("fct_match").df()
    leagues = dbt.ref("leagues").df()[["league", "country", "tier"]]
    fixtures = reconcile_fixtures(dbt.ref("stg_app__fixtures").df().merge(leagues, on="league"), played)
    fixtures["is_future"] = True
    played["is_future"] = False
    return build_features(pd.concat([played, fixtures], ignore_index=True))
