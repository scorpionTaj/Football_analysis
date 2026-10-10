"""Candidate match-outcome models. Every model maps a feature frame to [P(H), P(D), P(A)].

`fit(train, calib)` receives two chronologically ordered frames: the model learns on
`train` and may only use `calib` (strictly later, strictly earlier than the test
season) for early stopping, temperature calibration or blend weights.
"""

from __future__ import annotations

import contextlib
import functools
import os
import shutil
import subprocess

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


def recency_weights(train, half_life):
    """Older seasons count less (weight halves every `half_life` seasons); football drifts."""
    if not half_life:
        return None
    return (0.5 ** ((train.season.max() - train.season) / half_life)).to_numpy()


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
    def __init__(self, name="logreg", features=FEATURES, C=0.05, half_life=4):
        self.name, self.features, self.C, self.half_life = name, tuple(features), C, half_life

    def _fit(self, train, calib):
        self.pipe = make_pipeline(StandardScaler(), LogisticRegression(C=self.C, max_iter=2000))
        self.pipe.fit(self._X(train), train.outcome,
                      logisticregression__sample_weight=recency_weights(train, self.half_life))

    def _raw(self, frame):
        return self.pipe.predict_proba(self._X(frame))

    def params(self):
        return {**super().params(), "C": self.C, "n_features": len(self.features), "half_life": self.half_life}


def _nvidia_gpu_present() -> bool:
    """An NVIDIA driver answering nvidia-smi (the only GPUs LightGBM's CUDA/OpenCL paths target here)."""
    if not shutil.which("nvidia-smi"):
        return False
    try:
        return subprocess.run(["nvidia-smi", "-L"], capture_output=True, timeout=10).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


@functools.cache
def lightgbm_device() -> str:
    """LightGBM device: 'cuda' or 'gpu' (OpenCL) when an NVIDIA GPU is detected and this LightGBM
    build can train on it (checked with a tiny fit), else 'cpu'. FOOTBALL_ML_DEVICE=cpu|gpu|cuda
    forces a choice; 'auto' (default) detects. Logistic regression and Poisson stay on CPU
    (scikit-learn/SciPy have no GPU path)."""
    choice = os.environ.get("FOOTBALL_ML_DEVICE", "auto").strip().lower()
    if choice == "cpu":
        return "cpu"
    candidates = [choice] if choice in ("cuda", "gpu") else ["cuda", "gpu"] if _nvidia_gpu_present() else []
    if not candidates:
        return "cpu"
    import lightgbm as lgb

    rng = np.random.default_rng(0)
    probe_x, probe_y = rng.normal(size=(256, 4)), rng.integers(0, 3, 256)
    for device in candidates:
        try:
            with _quiet_native_stderr():  # LightGBM prints [Fatal] lines natively before raising
                lgb.LGBMClassifier(objective="multiclass", n_estimators=2, device_type=device, verbose=-1).fit(probe_x, probe_y)
            return device
        except Exception:  # e.g. "CUDA Tree Learner was not enabled in this build"
            continue
    return "cpu"


@contextlib.contextmanager
def _quiet_native_stderr():
    """Silence C-level stderr (not just sys.stderr) for the duration of a device probe."""
    try:
        saved, devnull = os.dup(2), os.open(os.devnull, os.O_WRONLY)
    except OSError:
        yield
        return
    try:
        os.dup2(devnull, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(devnull)


class LightGBM(Model):
    name = "lightgbm"

    def __init__(self, half_life=6, **overrides):
        self.half_life = half_life
        self.config = dict(objective="multiclass", num_class=3, learning_rate=0.03, n_estimators=2000,
                           num_leaves=15, min_child_samples=200, subsample=0.8, subsample_freq=1,
                           colsample_bytree=0.7, reg_lambda=5.0, verbose=-1)
        self.config.update(overrides)

    def _fit(self, train, calib):
        import lightgbm as lgb

        self.model = lgb.LGBMClassifier(**{"device_type": lightgbm_device(), **self.config})
        self.model.fit(self._X(train), train.outcome, sample_weight=recency_weights(train, self.half_life),
                       eval_X=self._X(calib), eval_y=calib.outcome,
                       callbacks=[lgb.early_stopping(100, verbose=False)])

    def _raw(self, frame):
        return self.model.predict_proba(self._X(frame))

    def params(self):
        return {**super().params(), "best_iteration": int(self.model.best_iteration_ or 0), "device": lightgbm_device(),
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


class Stacked(Model):
    """Out-of-fold stacking: a multinomial logistic meta-learner on member log-probabilities.

    Meta-features come only from the training window: for each of its last `folds` seasons s,
    fresh members train on seasons < s-1, calibrate on s-1 and predict s (time-ordered, so no
    member ever sees the season it predicts). Members are then refitted on the whole window;
    `calib` is used, as for every model, only for member early stopping/temperature and the
    final temperature of the stack.
    """
    name = "stacked"

    def __init__(self, make_members, folds=6, C=1.0):
        self.make_members, self.folds, self.C = make_members, folds, C

    @staticmethod
    def _meta_X(probs):
        return np.hstack([np.log(np.clip(p, EPS, 1)) for p in probs])

    def _fit(self, train, calib):
        seasons = sorted(train.season.unique())
        meta_X, meta_y = [], []
        for season in seasons[-self.folds:]:
            fit_rows, fold_calib = train[train.season < season - 1], train[train.season == season - 1]
            held_out = train[train.season == season]
            if fit_rows.empty or fold_calib.empty:
                continue
            members = [m.fit(fit_rows, fold_calib) for m in self.make_members()]
            meta_X.append(self._meta_X([m.predict_proba(held_out) for m in members]))
            meta_y.append(held_out.outcome.to_numpy())
        if not meta_X:
            raise ValueError("stacking needs at least three seasons in the training window")
        self.meta = make_pipeline(StandardScaler(), LogisticRegression(C=self.C, max_iter=2000))
        self.meta.fit(np.vstack(meta_X), np.concatenate(meta_y))
        self.members = [m.fit(train, calib) for m in self.make_members()]

    def _raw(self, frame):
        return self.meta.predict_proba(self._meta_X([m.predict_proba(frame) for m in self.members]))

    def params(self):
        coef = self.meta[-1].coef_
        return {**super().params(), "folds": self.folds, "C": self.C,
                **{f"coef_{m.name}": round(float(np.abs(coef[:, 3 * i:3 * i + 3]).sum()), 4)
                   for i, m in enumerate(self.members)}}


def _members():
    return [Logit("logreg", FEATURES), LightGBM(), PoissonGoals()]


def candidates():
    """Fresh, unfitted instances of every model in the leaderboard."""
    return [
        Prevalence(),
        Logit("elo_logit", ("elo_diff",), C=1.0),
        Logit("logreg", FEATURES),
        LightGBM(),
        PoissonGoals(),
        Ensemble(_members()),
        Stacked(_members),
        Logit("market_blend", (*FEATURES, *MARKET_FEATURES)),
        MarketClosing(),
    ]


def usable(frame: pd.DataFrame, model: Model) -> pd.Series:
    """Rows a model can score (market models need prices)."""
    needed = list(getattr(model, "features", ()))
    if isinstance(model, MarketClosing):
        needed = ["close_p_home", "close_p_draw", "close_p_away"]
    return frame[needed].notna().all(axis=1) if needed else pd.Series(True, index=frame.index)
