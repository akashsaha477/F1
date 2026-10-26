"""Model portfolio for relative-pace regression with a common interface.

Every model implements ``fit``, ``predict`` and ``contributions``. ``contributions`` returns an
additive decomposition ``prediction = base + sum(contributions)`` per *input feature*:

* linear / spline models: exact (coefficient x centred design column, summed per input feature);
* LightGBM: exact path-dependent TreeSHAP values computed by LightGBM (``pred_contrib``);
* baselines: the lookup value is attributed to the group it was looked up from.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import RidgeCV
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

COMPOUNDS = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]


@dataclass
class FeatureSpec:
    numeric: list[str]
    categorical: list[str] = field(default_factory=lambda: ["compound"])
    spline: list[str] = field(default_factory=list)

    @property
    def all(self) -> list[str]:
        return self.numeric + self.categorical


def add_interactions(X: pd.DataFrame) -> pd.DataFrame:
    """Compound-specific tyre-age columns for the linear models (LightGBM learns these itself)."""
    X = X.copy()
    if "tyre_life_laps" in X.columns and "compound" in X.columns:
        tl = X["tyre_life_laps"].fillna(0)
        for c in COMPOUNDS:
            X[f"tyre_life_x_{c.lower()}"] = tl * (X["compound"] == c)
    return X


def _source_feature(col: str, features: list[str]) -> str:
    name = col.split("__", 1)[-1]
    if name.startswith("missingindicator_"):
        name = name[len("missingindicator_"):]
    if name.startswith("tyre_life_x_"):
        return "compound_x_tyre_life"
    for f in sorted(features, key=len, reverse=True):
        if name == f or name.startswith(f + "_") or name.startswith(f + "_sp_"):
            return f
    return name


class LinearPaceModel:
    """Ridge regression; with ``spline`` features it becomes an additive spline model (GAM-style)."""

    def __init__(self, spec: FeatureSpec, name: str = "ridge", alphas=(0.1, 1.0, 10.0, 100.0, 1000.0), n_knots: int = 6):
        self.spec, self.name, self.alphas, self.n_knots = spec, name, alphas, n_knots

    def _design_cols(self, X: pd.DataFrame) -> list[str]:
        inter = [c for c in X.columns if c.startswith("tyre_life_x_")]
        return self.spec.numeric + inter + self.spec.categorical

    def fit(self, X: pd.DataFrame, y, **_):
        X = add_interactions(X)
        lin = [c for c in self.spec.numeric if c not in self.spec.spline] + [c for c in X.columns if c.startswith("tyre_life_x_")]
        transformers = [("num", Pipeline([("imp", SimpleImputer(strategy="median", add_indicator=True,
                                                                 keep_empty_features=True)),
                                          ("sc", StandardScaler())]), lin),
                        ("cat", OneHotEncoder(handle_unknown="ignore", categories=[COMPOUNDS]), self.spec.categorical)]
        if self.spec.spline:
            transformers.append(("spl", Pipeline([("imp", SimpleImputer(strategy="median", keep_empty_features=True)),
                                                  ("sp", SplineTransformer(n_knots=self.n_knots, degree=3,
                                                                           extrapolation="constant"))]),
                                 self.spec.spline))
        self.pre = ColumnTransformer(transformers, verbose_feature_names_out=True)
        Z = self.pre.fit_transform(X[self._design_cols(X)])
        self.reg = RidgeCV(alphas=self.alphas).fit(Z, np.asarray(y))
        self.z_mean_ = Z.mean(axis=0)
        names = list(self.pre.get_feature_names_out())
        # spline columns are named spl__<feature>_sp_<k>
        self.col_source_ = [_source_feature(n, self.spec.all) for n in names]
        self.design_names_ = names
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        X = add_interactions(X)
        return self.reg.predict(self.pre.transform(X[self._design_cols(X)]))

    def contributions(self, X: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
        X = add_interactions(X)
        Z = self.pre.transform(X[self._design_cols(X)])
        parts = (Z - self.z_mean_) * self.reg.coef_
        df = pd.DataFrame(parts, columns=self.design_names_, index=X.index)
        contrib = df.T.groupby(self.col_source_).sum().T
        base = np.full(len(X), float(self.reg.intercept_ + self.z_mean_ @ self.reg.coef_))
        return base, contrib

    def coefficients(self) -> list[dict]:
        return [{"design_column": n, "feature": s, "coef_per_sd": float(c)}
                for n, s, c in zip(self.design_names_, self.col_source_, self.reg.coef_, strict=True)]


class LightGBMPaceModel:
    name = "lightgbm"

    def __init__(self, spec: FeatureSpec, params: dict | None = None, seed: int = 42):
        self.spec = spec
        self.seed = seed
        self.params = {"n_estimators": 2000, "learning_rate": 0.03, "num_leaves": 31, "min_child_samples": 200,
                       "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.8, "reg_lambda": 1.0,
                       "verbose": -1, **(params or {})}

    def _prep(self, X: pd.DataFrame) -> pd.DataFrame:
        Z = X[self.spec.all].copy()
        for c in self.spec.categorical:
            Z[c] = pd.Categorical(Z[c], categories=COMPOUNDS)
        for c in self.spec.numeric:
            Z[c] = pd.to_numeric(Z[c], errors="coerce").astype(float)
        return Z

    def fit(self, X: pd.DataFrame, y, X_val: pd.DataFrame | None = None, y_val=None):
        self.model = lgb.LGBMRegressor(random_state=self.seed, **self.params)
        kw = {}
        if X_val is not None and len(X_val):
            kw = {"eval_set": [(self._prep(X_val), np.asarray(y_val))],
                  "callbacks": [lgb.early_stopping(100, verbose=False)]}
        self.model.fit(self._prep(X), np.asarray(y), **kw)
        self.best_iteration_ = int(self.model.best_iteration_ or self.params["n_estimators"])
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict(self._prep(X), num_iteration=self.best_iteration_)

    def contributions(self, X: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
        raw = self.model.predict(self._prep(X), num_iteration=self.best_iteration_, pred_contrib=True)
        contrib = pd.DataFrame(raw[:, :-1], columns=self.spec.all, index=X.index)
        return raw[:, -1], contrib

    def split_importance(self) -> dict[str, float]:
        gain = self.model.booster_.feature_importance(importance_type="gain")
        return dict(zip(self.spec.all, map(float, gain / gain.sum()), strict=True))


def _progress_bin(x: pd.Series) -> pd.Series:
    return pd.cut(x.astype(float), bins=[-np.inf, 0.2, 0.4, 0.6, 0.8, np.inf], labels=False)


class HistoricalGroupMedian:
    """Baseline: median relative pace of the most specific matching group in the training period.

    Groups tried in order: (driver, compound, race-phase bin), (driver, race-phase bin),
    (compound, race-phase bin), (race-phase bin).
    """

    name = "hist_group_median"
    levels = [("driver_id", "compound", "phase"), ("driver_id", "phase"), ("compound", "phase"), ("phase",)]

    def fit(self, X: pd.DataFrame, y, **_):
        d = X[["driver_id", "compound"]].copy()
        d["phase"] = _progress_bin(X["race_progress"])
        d["y"] = np.asarray(y)
        self.tables = [d.groupby(list(lv))["y"].agg(["median", "size"]) for lv in self.levels]
        self.global_ = float(np.median(d["y"]))
        return self

    def _lookup(self, X: pd.DataFrame):
        d = X[["driver_id", "compound"]].copy()
        d["phase"] = _progress_bin(X["race_progress"])
        pred = pd.Series(np.nan, index=X.index)
        level = pd.Series(len(self.levels), index=X.index)
        for i, (lv, tab) in enumerate(zip(self.levels, self.tables, strict=True)):
            tab = tab[tab["size"] >= 20]["median"]
            keys = pd.MultiIndex.from_frame(d[list(lv)]) if len(lv) > 1 else d[lv[0]]
            vals = pd.Series(tab.reindex(keys).to_numpy(), index=X.index)
            fill = pred.isna() & vals.notna()
            pred[fill] = vals[fill]
            level[fill] = i
        pred = pred.fillna(self.global_)
        return pred.to_numpy(), level

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self._lookup(X)[0]

    def contributions(self, X: pd.DataFrame):
        pred, level = self._lookup(X)
        contrib = pd.DataFrame({"historical_group": pred - self.global_}, index=X.index)
        return np.full(len(X), self.global_), contrib


class TeamAdjustedBaseline:
    """Baseline: team form + half the driver's team-mate gap + a common (compound, race-phase) curve."""

    name = "team_adjusted_form"

    def _core(self, X):
        team = X["team_form_pace"].astype(float)
        team = team.fillna(team.median() if team.notna().any() else 0.0)
        return team + 0.5 * X["drv_teammate_gap_form"].astype(float).fillna(0.0)

    def fit(self, X: pd.DataFrame, y, **_):
        resid = np.asarray(y) - self._core(X).to_numpy()
        d = pd.DataFrame({"compound": X["compound"].to_numpy(), "phase": _progress_bin(X["race_progress"]).to_numpy(),
                          "r": resid})
        self.curve_ = d.groupby(["compound", "phase"])["r"].median()
        self.default_ = float(np.median(resid))
        return self

    def _curve(self, X):
        keys = pd.MultiIndex.from_arrays([X["compound"].to_numpy(), _progress_bin(X["race_progress"]).to_numpy()])
        return pd.Series(self.curve_.reindex(keys).to_numpy(), index=X.index).fillna(self.default_)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return (self._core(X) + self._curve(X)).to_numpy()

    def contributions(self, X: pd.DataFrame):
        team = X["team_form_pace"].astype(float)
        contrib = pd.DataFrame({
            "team_form_pace": team.fillna(team.median() if team.notna().any() else 0.0),
            "drv_teammate_gap_form": 0.5 * X["drv_teammate_gap_form"].astype(float).fillna(0.0),
            "compound_x_race_phase": self._curve(X),
        }, index=X.index)
        return np.zeros(len(X)), contrib
