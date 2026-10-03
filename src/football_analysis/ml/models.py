"""Candidate match-outcome models. Every model maps a feature frame to [P(H), P(D), P(A)].

`fit(train, calib)` receives two chronologically ordered frames: the model learns on
`train` and may only use `calib` (strictly later, strictly earlier than the test
season) for early stopping, temperature calibration or blend weights.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize, minimize_scalar
from scipy.stats import poisson
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURES, MARKET_FEATURES

EPS = 1e-12


def log_loss(p, y):
    return float(-np.mean(np.log(np.clip(p[np.arange(len(y)), y], EPS, 1))))


def _temper(p, t):
    logits = np.log(np.clip(p, EPS, 1)) / t
    logits -= logits.max(axis=1, keepdims=True)
    e = np.exp(logits)
    return e / e.sum(axis=1, keepdims=True)


def fit_temperature(p, y):
    return float(minimize_scalar(lambda t: log_loss(_temper(p, t), y), bounds=(0.5, 2.5), method="bounded").x)


class Model:
    name = "model"
    features: tuple = FEATURES
    temperature = 1.0
    calibrate = True

    def _X(self, frame):
        return frame[list(self.features)].to_numpy(dtype=float)

    def fit(self, train, calib):
        self._fit(train, calib)
        if self.calibrate and len(calib):
            self.temperature = fit_temperature(self._raw(calib), calib.outcome.to_numpy())
        return self

    def predict_proba(self, frame):
        return _temper(self._raw(frame), self.temperature)

    def params(self):
        return {"temperature": round(self.temperature, 4)}


class Prevalence(Model):
    name = "prevalence_baseline"
    calibrate = False

    def _fit(self, train, calib):
        self.p = np.bincount(train.outcome, minlength=3) / len(train)

    def _raw(self, frame):
        return np.tile(self.p, (len(frame), 1))


class MarketClosing(Model):
    """Pinnacle/market closing line, margin removed. A benchmark, never a feature."""
    name = "market_closing"
    calibrate = False

    def _fit(self, train, calib):
        pass

    def _raw(self, frame):
        return frame[["close_p_home", "close_p_draw", "close_p_away"]].to_numpy(dtype=float)


class Logit(Model):
    def __init__(self, name="logreg", features=FEATURES, C=0.05):
        self.name, self.features, self.C = name, tuple(features), C

    def _fit(self, train, calib):
        self.pipe = make_pipeline(StandardScaler(), LogisticRegression(C=self.C, max_iter=2000))
        self.pipe.fit(self._X(train), train.outcome)

    def _raw(self, frame):
        return self.pipe.predict_proba(self._X(frame))

    def params(self):
        return {**super().params(), "C": self.C, "n_features": len(self.features)}


class LightGBM(Model):
    name = "lightgbm"

    def __init__(self, **overrides):
        self.config = dict(objective="multiclass", num_class=3, learning_rate=0.03, n_estimators=2000,
                           num_leaves=15, min_child_samples=200, subsample=0.8, subsample_freq=1,
                           colsample_bytree=0.7, reg_lambda=5.0, verbose=-1)
        self.config.update(overrides)

    def _fit(self, train, calib):
        import lightgbm as lgb

        self.model = lgb.LGBMClassifier(**self.config)
        self.model.fit(self._X(train), train.outcome, eval_X=self._X(calib), eval_y=calib.outcome,
                       callbacks=[lgb.early_stopping(100, verbose=False)])

    def _raw(self, frame):
        return self.model.predict_proba(self._X(frame))

    def params(self):
        return {**super().params(), "best_iteration": int(self.model.best_iteration_ or 0),
                **{k: v for k, v in self.config.items() if k in ("learning_rate", "num_leaves", "min_child_samples")}}


class PoissonGoals(Model):
    """Independent Poisson goal models with a Dixon-Coles low-score correction (rho fitted on calib)."""
    name = "poisson_dixon_coles"
    max_goals = 10
    alpha = 0.01

    def _fit(self, train, calib):
        X = self._X(train)
        self.scaler = StandardScaler().fit(X)
        self.home = PoissonRegressor(alpha=self.alpha, max_iter=1000).fit(self.scaler.transform(X), train.home_goals)
        self.away = PoissonRegressor(alpha=self.alpha, max_iter=1000).fit(self.scaler.transform(X), train.away_goals)
        self.rho = 0.0
        if len(calib):
            y = calib.outcome.to_numpy()
            self.rho = float(minimize_scalar(lambda r: log_loss(self._outcomes(calib, r), y),
                                             bounds=(-0.25, 0.1), method="bounded").x)

    def rates(self, frame):
        X = self.scaler.transform(self._X(frame))
        return np.clip(self.home.predict(X), 0.1, 6), np.clip(self.away.predict(X), 0.1, 6)

    def score_matrix(self, frame, rho=None):
        rho = self.rho if rho is None else rho
        lh, la = self.rates(frame)
        goals = np.arange(self.max_goals + 1)
        m = poisson.pmf(goals[None, :, None], lh[:, None, None]) * poisson.pmf(goals[None, None, :], la[:, None, None])
        # Dixon-Coles tau for 0-0, 1-0, 0-1, 1-1
        m[:, 0, 0] *= 1 - lh * la * rho
        m[:, 1, 0] *= 1 + la * rho
        m[:, 0, 1] *= 1 + lh * rho
        m[:, 1, 1] *= 1 - rho
        return m / m.sum(axis=(1, 2), keepdims=True)

    def _outcomes(self, frame, rho=None):
        m = self.score_matrix(frame, rho)
        home = np.tril(np.ones(m.shape[1:]), -1)
        return np.stack([(m * home).sum((1, 2)), np.trace(m, axis1=1, axis2=2), (m * home.T).sum((1, 2))], axis=1)

    _raw = _outcomes

    def over_under(self, frame, line=2.5):
        m = self.score_matrix(frame)
        total = np.add.outer(np.arange(m.shape[1]), np.arange(m.shape[2]))
        return (m * (total > line)).sum((1, 2))

    def params(self):
        return {**super().params(), "rho": round(self.rho, 4)}


class Ensemble(Model):
    """Convex blend of member probabilities; weights minimise calib log loss."""
    name = "ensemble"

    def __init__(self, members):
        self.members = members

    def fit(self, train, calib):
        # Members learn on train; weights need predictions they did not train on.
        for member in self.members:
            member.fit(train, calib)
        y = calib.outcome.to_numpy()
        probs = [member.predict_proba(calib) for member in self.members]

        def loss(w):
            w = np.abs(w) / np.abs(w).sum()
            return log_loss(sum(wi * p for wi, p in zip(w, probs)), y)

        result = minimize(loss, np.ones(len(probs)) / len(probs), method="Nelder-Mead")
        self.weights = np.abs(result.x) / np.abs(result.x).sum()
        return self

    def predict_proba(self, frame):
        return sum(w * m.predict_proba(frame) for w, m in zip(self.weights, self.members))

    def params(self):
        return {f"w_{m.name}": round(float(w), 4) for m, w in zip(self.members, self.weights)}


def candidates():
    """Fresh, unfitted instances of every model in the leaderboard."""
    return [
        Prevalence(),
        Logit("elo_logit", ("elo_diff",), C=1.0),
        Logit("logreg", FEATURES),
        LightGBM(),
        PoissonGoals(),
        Ensemble([Logit("logreg", FEATURES), LightGBM(), PoissonGoals()]),
        Logit("market_blend", (*FEATURES, *MARKET_FEATURES)),
        MarketClosing(),
    ]


def usable(frame: pd.DataFrame, model: Model) -> pd.Series:
    """Rows a model can score (market models need prices)."""
    needed = list(getattr(model, "features", ()))
    if isinstance(model, MarketClosing):
        needed = ["close_p_home", "close_p_draw", "close_p_away"]
    return frame[needed].notna().all(axis=1) if needed else pd.Series(True, index=frame.index)
