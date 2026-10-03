import numpy as np
import pandas as pd

from football_analysis.ml.evaluate import metrics, rps
from football_analysis.ml.features import FEATURES, build_features
from football_analysis.ml.models import candidates, usable


def _league(seasons=4, teams=16, seed=0):
    rng = np.random.default_rng(seed)
    strength = dict(zip([f"T{i}" for i in range(teams)], rng.normal(0, 0.5, teams)))
    rows = []
    for season in range(2018, 2018 + seasons):
        day = pd.Timestamp(f"{season}-08-01")
        names = list(strength)
        for round_ in range(2 * (teams - 1)):
            rng.shuffle(names)
            for a, b in zip(names[::2], names[1::2]):
                lam_h, lam_a = np.exp(0.3 + strength[a] - strength[b]), np.exp(strength[b] - strength[a])
                rows.append(dict(league="X1", country="X", tier=1, season=season, match_date=day,
                                 home_team=a, away_team=b, home_goals=rng.poisson(lam_h), away_goals=rng.poisson(lam_a),
                                 home_sot=4, away_sot=4, close_p_home=0.45, close_p_draw=0.27, close_p_away=0.28))
            day = day + pd.Timedelta(days=7)
    return pd.DataFrame(rows)


def test_features_ignore_same_day_and_future_results():
    matches = _league()
    base = build_features(matches)
    changed = matches.copy()
    last_day = changed.match_date.max()
    changed.loc[changed.match_date == last_day, "home_goals"] += 5  # rewrite the final day's results
    again = build_features(changed)
    on_last = base.match_date == last_day
    np.testing.assert_allclose(base.loc[on_last, list(FEATURES)], again.loc[on_last, list(FEATURES)])
    assert set(FEATURES) <= set(base.columns) and base[list(FEATURES)].notna().all().all()


def test_every_candidate_returns_valid_probabilities():
    frame = build_features(_league())
    train, calib, test = (frame[frame.season == s] for s in (2019, 2020, 2021))
    train = pd.concat([frame[frame.season == 2018], train])
    for model in candidates():
        if model.name == "market_blend":  # synthetic data has no opening odds
            continue
        rows = test[usable(test, model)]
        p = model.fit(train[usable(train, model)], calib[usable(calib, model)]).predict_proba(rows)
        assert p.shape == (len(rows), 3), model.name
        np.testing.assert_allclose(p.sum(1), 1, atol=1e-6)
        assert metrics(p, rows.outcome.to_numpy())["log_loss"] < 1.2, model.name


def test_rps_rewards_ordered_closeness():
    y = np.array([0])
    assert rps(np.array([[0.0, 1.0, 0.0]]), y) < rps(np.array([[0.0, 0.0, 1.0]]), y)
    assert rps(np.array([[1.0, 0.0, 0.0]]), y) == 0
