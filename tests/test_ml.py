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


def test_promoted_flag_holds_for_the_whole_season():
    rows = []
    for i in range(3):
        day = pd.Timestamp("2018-09-01") + pd.Timedelta(days=7 * i)
        rows += [dict(league="X2", country="X", tier=2, season=2018, match_date=day, home_team="P", away_team="Q",
                      home_goals=1, away_goals=0),
                 dict(league="X1", country="X", tier=1, season=2018, match_date=day, home_team="A", away_team="B",
                      home_goals=1, away_goals=0)]
    for i in range(3):
        day = pd.Timestamp("2019-09-01") + pd.Timedelta(days=7 * i)
        rows.append(dict(league="X1", country="X", tier=1, season=2019, match_date=day, home_team="P", away_team="A",
                         home_goals=0, away_goals=0))
    frame = build_features(pd.DataFrame(rows))
    season = frame[frame.season == 2019]
    assert (season.home_promoted == 1).all() and (season.away_promoted == 0).all()


def test_play_off_rematches_keep_fixtures_and_resolve_by_meeting():
    import importlib.util
    from pathlib import Path

    import duckdb

    from football_analysis.ml.publish import _reconcile_forecast_history

    spec = importlib.util.spec_from_file_location(
        "ml_match_features", Path(__file__).parents[1] / "warehouse/models/ml/ml_match_features.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    played = pd.DataFrame([
        dict(league="B1", country="B", season=2025, match_date=pd.Timestamp("2025-10-01"),
             home_team="Gent", away_team="Genk", home_goals=2, away_goals=0),
        dict(league="B2", country="B", season=2025, match_date=pd.Timestamp("2025-10-01"),
             home_team="Newcomer", away_team="Other", home_goals=1, away_goals=1),
    ])
    fixtures = pd.DataFrame([
        dict(league="B1", country="B", tier=1, season=2025, match_date=pd.Timestamp("2026-04-10"), home_team="Gent",
             away_team="Genk", event_kind="fixture", fetched_at=pd.Timestamp("2026-04-01")),
        dict(league="B1", country="B", tier=1, season=2025, match_date=pd.Timestamp("2025-10-02"), home_team="Gent",
             away_team="Genk", event_kind="next", fetched_at=pd.Timestamp("2025-09-30")),
        dict(league="B1", country="B", tier=1, season=2025, match_date=pd.Timestamp("2026-04-11"),
             home_team="Newcomer", away_team="Gent", event_kind="fixture", fetched_at=pd.Timestamp("2026-04-01")),
    ])
    kept = module.reconcile_fixtures(fixtures, played)
    assert sorted(kept.match_date.dt.day) == [10, 11]  # rematch and the new club survive; the played one is gone

    con = duckdb.connect()
    con.execute("CREATE TABLE forecast_history (model_id VARCHAR, league VARCHAR, season INTEGER, match_date DATE, "
                "home_team VARCHAR, away_team VARCHAR, issued_at TIMESTAMP, actual_result VARCHAR, resolved_at TIMESTAMP)")
    con.execute("INSERT INTO forecast_history VALUES ('m', 'B1', 2025, '2026-04-10', 'Gent', 'Genk', '2026-04-01', NULL, NULL)")
    _reconcile_forecast_history(con, played)  # only the October meeting is played: stays pending
    assert con.execute("SELECT actual_result FROM forecast_history").fetchall()[0][0] is None
    rematch = dict(played.iloc[0], match_date=pd.Timestamp("2026-04-10"), home_goals=0, away_goals=1)
    _reconcile_forecast_history(con, pd.concat([played, pd.DataFrame([rematch])]))
    assert con.execute("SELECT actual_result FROM forecast_history").fetchall()[0][0] == "Away"


def test_fixtures_further_ahead_roll_rest_days_and_match_count_forward():
    played = _league(seasons=2)
    last = played.match_date.max()
    fixtures = pd.DataFrame([
        dict(league="X1", country="X", tier=1, season=2019, match_date=last + pd.Timedelta(days=7 * i),
             home_team=a, away_team=b, home_goals=np.nan, away_goals=np.nan, is_future=True)
        for i, (a, b) in enumerate([("T0", "T1"), ("T1", "T0"), ("T0", "T1")], start=1)])
    frame = build_features(pd.concat([played.assign(is_future=False), fixtures], ignore_index=True))
    future = frame[frame.is_future].sort_values("match_date")
    assert (future.home_rest_days == 7).all()  # not 14, 21, 28 days since the last played match
    assert list(future.home_season_matches.diff().dropna()) == [1, 1]


def test_market_strength_never_sees_its_own_match_prices():
    matches = _league().assign(odds_open_home=2.0, odds_open_draw=3.4, odds_open_away=3.8)
    base = build_features(matches)
    changed = matches.copy()
    last_day = changed.match_date.max()
    changed.loc[changed.match_date == last_day, "odds_open_home"] = 1.2  # reprice the final day only
    again = build_features(changed)
    on_last = base.match_date == last_day
    np.testing.assert_allclose(base.loc[on_last, "market_strength_diff"], again.loc[on_last, "market_strength_diff"])
    assert base.market_strength_diff.std() > 0  # the rating actually learns from earlier prices


def test_lightgbm_uses_a_detected_gpu_and_falls_back_to_cpu(monkeypatch):
    from football_analysis.ml import models

    def device(env, gpu_present, working):
        monkeypatch.setenv("FOOTBALL_ML_DEVICE", env)
        monkeypatch.setattr(models, "_nvidia_gpu_present", lambda: gpu_present)

        class FakeClassifier:
            def __init__(self, device_type, **_):
                self.device_type = device_type

            def fit(self, *_):
                if self.device_type not in working:
                    raise RuntimeError(f"{self.device_type} not enabled in this build")
                return self

        import lightgbm
        monkeypatch.setattr(lightgbm, "LGBMClassifier", FakeClassifier)
        models.lightgbm_device.cache_clear()
        try:
            return models.lightgbm_device()
        finally:
            models.lightgbm_device.cache_clear()

    assert device("auto", True, {"gpu"}) == "gpu"          # pip build: CUDA missing, OpenCL works
    assert device("auto", True, {"cuda", "gpu"}) == "cuda"  # CUDA build preferred when present
    assert device("auto", True, set()) == "cpu"            # GPU present but unusable
    assert device("auto", False, {"gpu"}) == "cpu"          # no NVIDIA GPU detected
    assert device("cpu", True, {"gpu"}) == "cpu"            # explicit override
