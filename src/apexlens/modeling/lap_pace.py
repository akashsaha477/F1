"""Model A — representative race-lap relative pace.

Target: ``rel_pace_pct`` of representative race/sprint laps (see ``features/definitions.py``).
Horizons:

* ``pre_event``: inputs known before the event's first session + scenario conditions
  (tyre, weather, race phase);
* ``pre_race``: additionally the same event's qualifying result.

Evaluation: walk-forward by season (train on all earlier seasons, calibrate intervals on the most
recent 20% of training events, test on the next season), plus event-held-out folds as a secondary
check. Model selection is made on the walk-forward test seasons.
"""

from __future__ import annotations

import logging
import time
from dataclasses import asdict

import numpy as np
import pandas as pd

from apexlens.evaluation import metrics as M
from apexlens.evaluation.splits import Split, event_group_kfold, final_fit_split, walk_forward_by_season
from apexlens.modeling.models import (
    FeatureSpec,
    HistoricalGroupMedian,
    LightGBMPaceModel,
    LinearPaceModel,
    TeamAdjustedBaseline,
)
from apexlens.modeling.uncertainty import MondrianConformal, condition_group
from apexlens.storage.io import read_table
from apexlens.storage.paths import DataPaths

log = logging.getLogger(__name__)

TASK = "lap_pace"
TARGET = "rel_pace_pct"
ALPHA = 0.1

DRIVER = ["drv_form_pace", "drv_form_n", "drv_teammate_gap_form", "drv_quali_form"]
TEAM = ["team_form_pace", "team_season_form", "team_season_events", "team_quali_form"]
TRACK = ["circuit_length_km", "circuit_turns", "circuit_is_street", "circuit_ref_lap_s"]
CORNER = ["circuit_frac_slow", "circuit_frac_fast", "circuit_full_throttle_frac"]
TYRE = ["tyre_life_laps", "fresh_tyre", "stint"]
WEATHER = ["track_temp_c", "air_temp_c", "humidity_pct", "rainfall", "is_wet_compound"]
RACE = ["race_progress", "lap_number", "is_sprint"]
INTERACTION = ["drv_circuit_hist"]
WEEKEND = ["evt_quali_gap", "evt_team_quali_gap"]
# kept with stored predictions for error analysis (not model inputs by themselves)
CONTEXT = ["lap_number", "tyre_life_laps", "race_progress", "is_sprint", "drv_form_n", "drv_circuit_hist", "circuit_ref_lap_s",
           "track_temp_c"]

GROUPS = {"driver": DRIVER, "team": TEAM, "track": TRACK, "corner": CORNER, "tyre": TYRE + ["compound"],
          "weather": WEATHER, "race_context": RACE, "interaction": INTERACTION, "weekend": WEEKEND}
FEATURE_GROUP = {f: g for g, fs in GROUPS.items() for f in fs}
FEATURE_GROUP["compound_x_tyre_life"] = "tyre"


def feature_spec(horizon: str = "pre_event", exclude_groups: tuple[str, ...] = (), available: set[str] | None = None) -> FeatureSpec:
    groups = ["driver", "team", "track", "corner", "tyre", "weather", "race_context", "interaction"]
    if horizon == "pre_race":
        groups.append("weekend")
    numeric = [f for g in groups if g not in exclude_groups for f in GROUPS[g] if f != "compound"]
    if available is not None:
        numeric = [f for f in numeric if f in available]
    categorical = [] if "tyre" in exclude_groups else ["compound"]
    spline = [f for f in ["race_progress", "tyre_life_laps", "track_temp_c", "drv_form_pace", "team_form_pace"]
              if f in numeric]
    return FeatureSpec(numeric=numeric, categorical=categorical, spline=spline)


def load_dataset(paths: DataPaths) -> pd.DataFrame:
    df = read_table(paths.gold("lap_features"))
    df = df[df["is_representative"] & df[TARGET].notna()].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "session_id", "driver_id", "lap_number"]).reset_index(drop=True)
    return df


# Constant (or nearly constant) within a session. The target is centred on the session reference, so
# these can only matter through interactions; additive models get them as main effects only by
# fitting session-to-session noise, which then extrapolates badly (observed on new circuits).
SESSION_LEVEL = set(TRACK + CORNER + ["team_season_events", "track_temp_c", "air_temp_c", "humidity_pct"])


def make_models(spec: FeatureSpec, include: tuple[str, ...] | None = None) -> dict:
    lin_numeric = [f for f in spec.numeric if f not in SESSION_LEVEL]
    linear_spec = FeatureSpec(numeric=lin_numeric, categorical=spec.categorical, spline=[])
    gam_spec = FeatureSpec(numeric=lin_numeric, categorical=spec.categorical,
                           spline=[f for f in spec.spline if f in lin_numeric])
    models = {
        "hist_group_median": HistoricalGroupMedian(),
        "team_adjusted_form": TeamAdjustedBaseline(),
        "ridge": LinearPaceModel(linear_spec, name="ridge"),
        "spline_gam": LinearPaceModel(gam_spec, name="spline_gam"),
        "lightgbm": LightGBMPaceModel(spec),
    }
    if include:
        models = {k: v for k, v in models.items() if k in include}
    return models


def fit_predict_split(df: pd.DataFrame, split: Split, spec: FeatureSpec, models: dict) -> tuple[pd.DataFrame, dict]:
    split.check_temporal(df) if split.name.startswith("walk_forward") else None
    tr, ca, te = df.loc[split.train_idx], df.loc[split.calib_idx], df.loc[split.test_idx]
    out = te[["event_id", "session_id", "season", "driver_id", "constructor_id", "circuit_id", "compound", "condition",
              "is_wet_compound", "session_ref_s", TARGET]].copy().rename(columns={TARGET: "y"})
    for c in CONTEXT:
        if c in te.columns:
            out[c] = te[c].to_numpy()
    fitted = {}
    for name, model in models.items():
        t0 = time.time()
        if name == "lightgbm":
            model.fit(tr, tr[TARGET], X_val=ca, y_val=ca[TARGET])
        else:
            model.fit(tr, tr[TARGET])
        cal_pred = model.predict(ca)
        conf = MondrianConformal(alpha=ALPHA).fit(ca[TARGET], cal_pred, condition_group(ca))
        pred = model.predict(te) if len(te) else np.array([])
        out[name] = pred
        if len(te):
            lo, hi = conf.interval(pred, condition_group(te))
            out[f"{name}_lo"], out[f"{name}_hi"] = lo, hi
        fitted[name] = {"model": model, "conformal": conf, "fit_seconds": round(time.time() - t0, 2)}
        log.info("%s %s fitted in %.1fs", split.name, name, time.time() - t0)
    return out, fitted


def evaluate_predictions(pred: pd.DataFrame, model_names: list[str], n_boot: int = 300) -> dict:
    res = {}
    for m in model_names:
        rep = M.regression_report(pred["y"], pred[m], pred.get(f"{m}_lo"), pred.get(f"{m}_hi"))
        rep["mae_ci"] = M.cluster_bootstrap(pred, "event_id", lambda d, m=m: M.mae(d["y"], d[m]), n_boot=n_boot)
        rep["by_condition"] = {}
        for cond, g in pred.groupby(np.where(pred["is_wet_compound"] > 0.5, "wet", "dry")):
            r = M.regression_report(g["y"], g[m], g.get(f"{m}_lo"), g.get(f"{m}_hi"))
            rep["by_condition"][cond] = r
        rep["mae_seconds"] = float(np.mean(np.abs(pred["y"] - pred[m]) * pred["session_ref_s"] / 100.0))
        res[m] = rep
    return res


def run_walk_forward(paths: DataPaths, horizon: str = "pre_event", include: tuple[str, ...] | None = None,
                     exclude_groups: tuple[str, ...] = (), n_boot: int = 300) -> dict:
    df = load_dataset(paths)
    spec = feature_spec(horizon, exclude_groups, available=set(df.columns))
    folds, preds = [], []
    last = None
    for split in walk_forward_by_season(df, min_train_seasons=1):
        models = make_models(spec, include)
        pred, fitted = fit_predict_split(df, split, spec, models)
        last = {"split": split, "fitted": fitted}
        pred["fold"] = split.name
        preds.append(pred)
        folds.append({
            "split": split.name, "train_period": split.train_period, "test_period": split.test_period,
            "n_train": int(len(split.train_idx)), "n_calib": int(len(split.calib_idx)), "n_test": int(len(split.test_idx)),
            "metrics": evaluate_predictions(pred, list(models), n_boot=n_boot),
            "conformal": {k: v["conformal"].to_dict() for k, v in fitted.items()},
            "lightgbm_best_iteration": fitted["lightgbm"]["model"].best_iteration_ if "lightgbm" in fitted else None,
        })
    allp = pd.concat(preds, ignore_index=True)
    names = list(make_models(spec, include))
    holdout_season = int(allp["season"].max())
    parts = {"development": allp[allp["season"] < holdout_season], "holdout": allp[allp["season"] == holdout_season]}
    pooled, comparisons = {}, {}
    for part, d in parts.items():
        if d.empty:
            continue
        pooled[part] = evaluate_predictions(d, names, n_boot=n_boot)
        comparisons[part] = {}
        if "lightgbm" in names:
            for other in names:
                if other != "lightgbm":
                    comparisons[part][f"lightgbm_vs_{other}"] = M.paired_mae_difference(d, "lightgbm", other, n_boot=n_boot)
    return {"task": TASK, "horizon": horizon, "target": TARGET, "spec": asdict(spec), "folds": folds,
            "holdout_season": holdout_season, "pooled": pooled, "comparisons": comparisons, "predictions": allp,
            "last_fold": last, "data": df, "spec_obj": spec}


def run_event_kfold(paths: DataPaths, horizon: str = "pre_event", k: int = 5, include=("ridge", "lightgbm")) -> dict:
    df = load_dataset(paths)
    spec = feature_spec(horizon, available=set(df.columns))
    preds = []
    for split in event_group_kfold(df, k=k):
        pred, _ = fit_predict_split(df, split, spec, make_models(spec, include))
        preds.append(pred)
    allp = pd.concat(preds, ignore_index=True)
    return {"split": f"event_group_kfold_{k}", "metrics": evaluate_predictions(allp, list(include), n_boot=200)}


def fit_final(paths: DataPaths, horizon: str = "pre_event", include: tuple[str, ...] | None = None) -> dict:
    df = load_dataset(paths)
    spec = feature_spec(horizon, available=set(df.columns))
    split = final_fit_split(df)
    models = make_models(spec, include)
    _, fitted = fit_predict_split(df, split, spec, models)
    train = df.loc[np.concatenate([split.train_idx, split.calib_idx])]
    ranges = {}
    for f in spec.numeric:
        v = pd.to_numeric(train[f], errors="coerce").astype(float)
        if v.notna().any():
            ranges[f] = {"p01": float(v.quantile(0.01)), "p99": float(v.quantile(0.99)), "min": float(v.min()),
                         "max": float(v.max()), "median": float(v.median())}
    compounds = train["compound"].value_counts().to_dict()
    return {"spec": spec, "fitted": fitted, "split": split, "feature_ranges": ranges, "compound_counts": compounds,
            "n_rows": int(len(df)), "train_period": split.train_period,
            "calib_events": sorted(df.loc[split.calib_idx, "event_id"].unique().tolist())}


def fit_bootstrap_ensemble(paths: DataPaths, horizon: str, n_models: int = 20, n_estimators: int = 300,
                           seed: int = 0) -> list[LightGBMPaceModel]:
    """LightGBM models refit on event-cluster bootstrap resamples.

    The spread of their predictions estimates *model* (estimation) uncertainty of an expected pace or of a
    difference between two drivers — distinct from the lap-to-lap noise covered by conformal intervals.
    """
    df = load_dataset(paths)
    spec = feature_spec(horizon, available=set(df.columns))
    rng = np.random.default_rng(seed)
    events = df["event_id"].unique()
    by_event = {e: idx for e, idx in df.groupby("event_id").indices.items()}
    models = []
    for i in range(n_models):
        pick = rng.choice(events, size=len(events), replace=True)
        idx = np.concatenate([by_event[e] for e in pick])
        sample = df.iloc[idx]
        m = LightGBMPaceModel(spec, params={"n_estimators": n_estimators}, seed=seed + i)
        m.fit(sample, sample[TARGET])
        models.append(m)
    return models
