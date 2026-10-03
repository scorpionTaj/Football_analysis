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
    frame = build_features(_league(seasons=6))  # stacking needs out-of-fold seasons inside train
    train, calib, test = frame[frame.season <= 2021], frame[frame.season == 2022], frame[frame.season == 2023]
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


def test_stacking_meta_features_never_see_their_own_season():
    from football_analysis.ml.models import Stacked

    seen = []

    class Spy:
        name = "spy"

        def fit(self, train, calib):
            self.trained = set(train.season) | set(calib.season)
            return self

        def predict_proba(self, frame):
            seen.append((self.trained, set(frame.season)))
            return np.full((len(frame), 3), 1 / 3)

    frame = build_features(_league(seasons=6))
    Stacked(lambda: [Spy()]).fit(frame[frame.season <= 2021], frame[frame.season == 2022])
    out_of_fold = seen[:2]  # the two fold predictions; later calls score calib with refitted members
    assert out_of_fold and all(not (trained & predicted) for trained, predicted in out_of_fold)
    assert all(max(trained) < min(predicted) for trained, predicted in out_of_fold)
