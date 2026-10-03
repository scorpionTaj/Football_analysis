"""Pre-match features for every played match and every upcoming fixture."""

import pandas as pd

from football_analysis.ml.features import build_features
from football_analysis.teams import team_key


def reconcile_fixtures(fixtures, played):
    """Map provider names onto Football-Data names; keep one row per pairing."""
    names = {}
    for league, group in played.groupby("league"):
        for name in pd.unique(group[["home_team", "away_team"]].values.ravel()):
            names[(league, team_key(name))] = name
    fixtures = fixtures.assign(
        home_team=[names.get((l, team_key(t))) for l, t in zip(fixtures.league, fixtures.home_team)],
        away_team=[names.get((l, team_key(t))) for l, t in zip(fixtures.league, fixtures.away_team)],
        priority=fixtures.event_kind.map({"fixture": 0, "next": 1}),
    ).dropna(subset=["home_team", "away_team"])
    fixtures = fixtures.sort_values(["priority", "fetched_at"], ascending=[True, False])
    fixtures = fixtures.drop_duplicates(["league", "season", "home_team", "away_team"])
    completed = set(zip(played.league, played.season, played.home_team, played.away_team))
    keep = [k not in completed for k in zip(fixtures.league, fixtures.season, fixtures.home_team, fixtures.away_team)]
    return fixtures[keep][["league", "season", "match_date", "home_team", "away_team"]]


def model(dbt, session):
    dbt.config(materialized="table")
    played = dbt.ref("fct_match").df()
    leagues = dbt.ref("leagues").df()[["league", "country", "tier"]]
    fixtures = reconcile_fixtures(dbt.ref("stg_app__fixtures").df(), played).merge(leagues, on="league")
    fixtures["is_future"] = True
    played["is_future"] = False
    return build_features(pd.concat([played, fixtures], ignore_index=True))
