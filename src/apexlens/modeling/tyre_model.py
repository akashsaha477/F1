"""Model C — tyre degradation.

Unit of analysis: a driver's stint of representative race laps. Lap times are first corrected for
fuel burn (and the general track-evolution trend) with the lap-number slope of that session's
stage-1 model (identified through pit stops, see ``driver_profiles/session_adjust.py``); the slope
of the corrected pace against tyre age is the stint's *degradation rate* (% of lap time per lap).

Not every lap-time increase is degradation: traffic, management, damage and changing conditions
also move pace. Stints with fewer than ``MIN_STINT_LAPS`` representative laps are not used, and
only dry-compound stints enter the degradation summaries.

Predictive check (walk-forward by season): for every test-season stint with at least
``MIN_EVAL_LAPS`` laps, the first ``ANCHOR_LAPS`` laps fix the level and the rest are predicted with
(a) no degradation, (b) the compound's pooled training slope, (c) + the circuit's slope from earlier
seasons (shrunk), (d) + the driver's shrunk deviation from earlier seasons.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from apexlens.driver_profiles.mixed_model import empirical_bayes
from apexlens.evaluation import metrics as M
from apexlens.storage.io import read_table, write_json, write_table
from apexlens.storage.paths import DataPaths

log = logging.getLogger(__name__)

DRY = ("SOFT", "MEDIUM", "HARD")
MIN_STINT_LAPS = 8
MIN_EVAL_LAPS = 14
ANCHOR_LAPS = 5
CIRCUIT_PRIOR_STINTS = 20  # shrinkage weight of the pooled compound slope against a circuit's own estimate
MIN_DRIVER_STINTS = 3


def _ols_slope(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
    xm = x - x.mean()
    sxx = float(xm @ xm)
    if sxx <= 0:
        return np.nan, np.nan, np.nan
    b = float(xm @ (y - y.mean()) / sxx)
    a = float(y.mean() - b * x.mean())
    resid = y - (a + b * x)
    se = float(np.sqrt(resid @ resid / max(len(x) - 2, 1) / sxx))
    return b, se, a


def stint_table(paths: DataPaths) -> tuple[pd.DataFrame, pd.DataFrame]:
    laps = read_table(paths.gold("all_laps_relative"))
    laps = laps[laps["session_code"].isin(["R", "S"]) & laps["is_representative"] & laps["tyre_life_laps"].notna()].copy()
    adj = read_table(paths.gold("driver_session_adjusted"))
    fuel = adj.groupby("session_id")["fuel_slope_pct_per_lap"].first()
    pooled_fuel = float(np.nanmedian(fuel))
    laps["fuel_slope"] = laps["session_id"].map(fuel).fillna(pooled_fuel)
    laps["lap_c"] = laps["lap_number"].astype(float) - laps.groupby("session_id")["lap_number"].transform("median")
    laps["corrected"] = laps["rel_pace_pct"] - laps["fuel_slope"] * laps["lap_c"]
    ev = read_table(paths.silver("events"))[["event_id", "date", "circuit_id"]]
    rows = []
    for (sid, drv, stint), g in laps.groupby(["session_id", "driver_id", "stint"]):
        if len(g) < MIN_STINT_LAPS or g["compound"].nunique() != 1:
            continue
        b, se, a = _ols_slope(g["tyre_life_laps"].to_numpy(float), g["corrected"].to_numpy(float))
        if not np.isfinite(b):
            continue
        rows.append({"session_id": sid, "event_id": g["event_id"].iloc[0], "season": int(g["season"].iloc[0]),
                     "session_code": g["session_code"].iloc[0], "driver_id": drv, "constructor_id": g["constructor_id"].iloc[0],
                     "stint": int(stint), "compound": g["compound"].iloc[0], "n_laps": int(len(g)),
                     "age_min": float(g["tyre_life_laps"].min()), "age_max": float(g["tyre_life_laps"].max()),
                     "fresh": bool(g["tyre_life_laps"].min() <= 2), "slope_pct": b, "slope_se": se, "level_at_age0": a,
                     "track_temp_c": float(g["track_temp_c"].mean()), "fuel_slope": float(g["fuel_slope"].iloc[0]),
                     "session_ref_s": float(g["session_ref_s"].iloc[0])})
    st = pd.DataFrame(rows).merge(ev, on="event_id", how="left")
    st["date"] = pd.to_datetime(st["date"])
    return st, laps


def _boot_mean(df: pd.DataFrame, col: str, weight: str, cluster: str = "session_id", n: int = 300, seed: int = 0):
    if df.empty:
        return np.nan, np.nan, np.nan
    groups = {k: g for k, g in df.groupby(cluster)}
    keys = np.array(list(groups))
    w = 1.0 / np.maximum(df[weight].to_numpy() ** 2, 1e-4)
    est = float(np.sum(w * df[col]) / np.sum(w))
    if len(keys) < 3:
        return est, np.nan, np.nan
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        d = pd.concat([groups[k] for k in rng.choice(keys, len(keys))])
        ww = 1.0 / np.maximum(d[weight].to_numpy() ** 2, 1e-4)
        vals.append(np.sum(ww * d[col]) / np.sum(ww))
    return est, float(np.quantile(vals, 0.05)), float(np.quantile(vals, 0.95))


def degradation_summaries(st: pd.DataFrame) -> dict[str, pd.DataFrame]:
    dry = st[st["compound"].isin(DRY)]
    by_comp = []
    for (season, comp), g in dry.groupby(["season", "compound"]):
        est, lo, hi = _boot_mean(g, "slope_pct", "slope_se")
        by_comp.append({"season": season, "compound": comp, "slope_pct": est, "ci_lo": lo, "ci_hi": hi,
                        "n_stints": int(len(g)), "n_sessions": int(g["session_id"].nunique()),
                        "slope_s_per_lap": est * float(g["session_ref_s"].median()) / 100})
    by_circuit = []
    for (circ, comp), g in dry.groupby(["circuit_id", "compound"]):
        est, lo, hi = _boot_mean(g, "slope_pct", "slope_se")
        by_circuit.append({"circuit_id": circ, "compound": comp, "slope_pct": est, "ci_lo": lo, "ci_hi": hi,
                           "n_stints": int(len(g)), "n_sessions": int(g["session_id"].nunique())})
    # temperature association across sessions (descriptive; temperature is confounded with circuit and season)
    sess = dry.groupby(["session_id", "compound"]).agg(slope=("slope_pct", "mean"), temp=("track_temp_c", "mean"),
                                                       n=("slope_pct", "size")).reset_index()
    temp = []
    for comp, g in sess.groupby("compound"):
        g = g.dropna()
        if len(g) < 8:
            continue
        x = g["temp"].to_numpy()
        y = g["slope"].to_numpy()
        b, se, a = _ols_slope(x, y)
        temp.append({"compound": comp, "slope_per_degC": b, "se": se, "ci_lo": b - 1.96 * se, "ci_hi": b + 1.96 * se,
                     "intercept": a, "n_sessions": int(len(g)), "temp_min": float(x.min()), "temp_max": float(x.max())})
    return {"by_compound": pd.DataFrame(by_comp), "by_circuit": pd.DataFrame(by_circuit), "temperature": pd.DataFrame(temp),
            "session_points": sess}


def driver_deg_effects(st: pd.DataFrame) -> pd.DataFrame:
    """Driver deviation from the session-compound mean slope, shrunk by empirical Bayes per compound."""
    dry = st[st["compound"].isin(DRY)].copy()
    grp = dry.groupby(["session_id", "compound"])
    tot, cnt = grp["slope_pct"].transform("sum"), grp["slope_pct"].transform("count")
    dry = dry[cnt >= 4].copy()
    tot, cnt = tot[dry.index], cnt[dry.index]
    dry["dev"] = dry["slope_pct"] - (tot - dry["slope_pct"]) / (cnt - 1)  # vs the *other* drivers' stints
    out = []
    for comp, g in dry.groupby("compound"):
        agg = g.groupby(["driver_id", "season"]).agg(raw=("dev", "mean"), var=("slope_se", lambda s: float(np.sum(s**2)) / len(s) ** 2),
                                                     n_stints=("dev", "size"), n_sessions=("session_id", "nunique")).reset_index()
        # residual spread between stints beyond their standard errors
        extra = max(float(np.var(g["dev"]) - np.mean(g["slope_se"] ** 2)), 0.0)
        agg["var"] = agg["var"] + extra / agg["n_stints"]
        post, pvar, tau2 = empirical_bayes(agg["raw"].to_numpy(), agg["var"].to_numpy())
        agg["posterior_mean"], agg["posterior_sd"], agg["tau"] = post, np.sqrt(pvar), np.sqrt(tau2)
        agg["raw_se"] = np.sqrt(agg["var"])
        agg["compound"] = comp
        out.append(agg.drop(columns="var"))
    res = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    if len(res):
        res["status"] = np.where(res["n_stints"] < MIN_DRIVER_STINTS, "insufficient_evidence",
                                 np.where((res["posterior_sd"] == 0) | (res["posterior_mean"].abs() <= 1.645 * res["posterior_sd"]),
                                          "not_distinguishable_from_zero", "supported"))
    return res


def temperature_betas(st: pd.DataFrame, min_stints: int = 30) -> dict[str, float]:
    """Within-circuit association of stint degradation with track temperature, per dry compound.

    Slopes and temperatures are centred on their circuit-compound means, so the coefficient answers "is
    degradation higher than usual *at this circuit* when it is hotter than usual there", which is not
    confounded with the circuit itself. Precision-weighted least squares.
    """
    out = {}
    d = st[st["compound"].isin(DRY)].dropna(subset=["track_temp_c", "slope_pct"]).copy()
    if d.empty:
        return out
    g = d.groupby(["circuit_id", "compound"])
    d["ds"] = d["slope_pct"] - g["slope_pct"].transform("mean")
    d["dt"] = d["track_temp_c"] - g["track_temp_c"].transform("mean")
    for comp, x in d.groupby("compound"):
        w = 1.0 / np.maximum(x["slope_se"].to_numpy(), 0.01) ** 2
        sxx = float(np.sum(w * x["dt"] ** 2))
        if len(x) >= min_stints and sxx > 0:
            out[comp] = float(np.sum(w * x["dt"] * x["ds"]) / sxx)
    return out


def evaluate_degradation_models(st: pd.DataFrame, laps: pd.DataFrame, n_boot: int = 300) -> dict:
    seasons = sorted(st["season"].unique())
    groups = laps.groupby(["session_id", "driver_id", "stint"]).indices
    preds = []
    for test in seasons[1:]:
        train = st[(st["season"] < test) & st["compound"].isin(DRY)]
        pooled_fuel = float(np.nanmedian(train.groupby("session_id")["fuel_slope"].first()))
        comp_slope = train.groupby("compound").apply(
            lambda g: np.sum(g["slope_pct"] / np.maximum(g["slope_se"], 0.01) ** 2) / np.sum(1 / np.maximum(g["slope_se"], 0.01) ** 2),
            include_groups=False)
        circ = train.groupby(["circuit_id", "compound"]).agg(m=("slope_pct", "mean"), n=("slope_pct", "size"),
                                                            t=("track_temp_c", "mean"))
        temp_beta = temperature_betas(train)
        pooled_temp = train.groupby("compound")["track_temp_c"].mean()
        drv = driver_deg_effects(train).set_index(["driver_id", "compound"]) if len(train) else pd.DataFrame()
        if len(drv):
            drv = drv.groupby(level=[0, 1])["posterior_mean"].last()
        test_st = st[(st["season"] == test) & st["compound"].isin(DRY) & (st["n_laps"] >= MIN_EVAL_LAPS)]
        for r in test_st.itertuples():
            idx = groups.get((r.session_id, r.driver_id, r.stint))
            if idx is None:
                continue
            g = laps.iloc[idx].sort_values("tyre_life_laps")
            y = (g["rel_pace_pct"] - pooled_fuel * g["lap_c"]).to_numpy()
            age = g["tyre_life_laps"].to_numpy(float)
            anchor, rest = slice(0, ANCHOR_LAPS), slice(ANCHOR_LAPS, None)
            base_slope = float(comp_slope.get(r.compound, 0.0))
            key = (r.circuit_id, r.compound)
            if key in circ.index:
                n = circ.loc[key, "n"]
                c_slope = (n * circ.loc[key, "m"] + CIRCUIT_PRIOR_STINTS * base_slope) / (n + CIRCUIT_PRIOR_STINTS)
            else:
                c_slope = base_slope
            d_dev = float(drv.get((r.driver_id, r.compound), 0.0)) if len(drv) else 0.0
            t_ref = circ.loc[key, "t"] if key in circ.index else pooled_temp.get(r.compound, np.nan)
            t_adj = temp_beta.get(r.compound, 0.0) * (r.track_temp_c - t_ref) if np.isfinite(r.track_temp_c - t_ref) else 0.0
            out = {}
            for name, slope in (("flat", 0.0), ("compound", base_slope), ("compound_circuit", c_slope),
                                ("compound_circuit_driver", c_slope + d_dev), ("compound_circuit_temp", c_slope + t_adj)):
                level = np.mean(y[anchor] - slope * age[anchor])
                out[name] = level + slope * age[rest]
            for i, yy in enumerate(y[rest]):
                preds.append({"season": test, "event_id": r.event_id, "y": yy, **{k: v[i] for k, v in out.items()},
                              "ref_s": r.session_ref_s})
    p = pd.DataFrame(preds)
    models = ["flat", "compound", "compound_circuit", "compound_circuit_driver", "compound_circuit_temp"]
    res = {"n_predicted_laps": int(len(p)), "n_events": int(p["event_id"].nunique()),
           "mae_pct": {m: M.mae(p["y"], p[m]) for m in models},
           "mae_s": {m: float(np.mean(np.abs(p["y"] - p[m]) * p["ref_s"] / 100)) for m in models},
           "by_season": {int(s): {m: M.mae(g["y"], g[m]) for m in models} for s, g in p.groupby("season")},
           "comparisons": {
               "compound_vs_flat": M.paired_mae_difference(p, "compound", "flat", n_boot=n_boot),
               "circuit_vs_compound": M.paired_mae_difference(p, "compound_circuit", "compound", n_boot=n_boot),
               "driver_vs_circuit": M.paired_mae_difference(p, "compound_circuit_driver", "compound_circuit", n_boot=n_boot),
               "temp_vs_circuit": M.paired_mae_difference(p, "compound_circuit_temp", "compound_circuit", n_boot=n_boot),
           },
           "protocol": f"walk-forward by season; first {ANCHOR_LAPS} laps of each stint (>= {MIN_EVAL_LAPS} laps) anchor the level"}
    return res


def build_tyre_tables(paths: DataPaths, evaluate: bool = True) -> dict:
    st, laps = stint_table(paths)
    summ = degradation_summaries(st)
    drv = driver_deg_effects(st)
    write_table(paths.gold("tyre_stints"), st)
    write_table(paths.gold("tyre_degradation"), summ["by_compound"])
    write_table(paths.gold("tyre_degradation_circuit"), summ["by_circuit"])
    write_table(paths.gold("tyre_temperature"), summ["temperature"])
    write_table(paths.gold("tyre_session_points"), summ["session_points"])
    write_table(paths.gold("driver_tyre_effects"), drv)
    out = {"n_stints": int(len(st)), "n_driver_compound_rows": int(len(drv))}
    if evaluate:
        ev = evaluate_degradation_models(st, laps)
        write_json(paths.models / "evaluation_runs" / "tyre_degradation.json", ev)
        out["evaluation"] = ev
    return out
