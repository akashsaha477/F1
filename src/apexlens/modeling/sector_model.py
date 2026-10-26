"""Model B — race sector pace, and whether driver x corner-type information adds predictive value.

Target: representative race-lap sector time relative to the session's median clean sector time
(``rel_sector_pct``). Each sector is described by its corner composition (from qualifying
telemetry of the same event: shares of slow / medium / fast corners, full-throttle share).

Two otherwise identical LightGBM / Ridge models are compared in walk-forward evaluation:

* base: Model A pre-event features + sector descriptors;
* + driver corner profile: the driver's EWMA team-mate-relative qualifying delta in slow, medium and
  fast corners from *previous* events, and its fit to the sector (sum of profile x composition).

If the corner profile carried a repeatable driver x corner-type effect, the second model should
reduce error on later seasons.
"""

from __future__ import annotations

import logging

import pandas as pd

from apexlens.evaluation import metrics as M
from apexlens.evaluation.splits import walk_forward_by_season
from apexlens.features.lap_features import HALF_LIFE_EVENTS, _ewm_prior
from apexlens.modeling import lap_pace as LP
from apexlens.modeling.models import FeatureSpec, LightGBMPaceModel, LinearPaceModel
from apexlens.storage.io import read_table
from apexlens.storage.paths import DataPaths

log = logging.getLogger(__name__)

CATS = ("slow", "medium", "fast")
SECTOR_FEATURES = ["sector", "sector_frac_slow", "sector_frac_medium", "sector_frac_fast", "sector_full_throttle_frac",
                   "sector_length_share"]
PROFILE_FEATURES = ["drv_corner_slow", "drv_corner_medium", "drv_corner_fast", "drv_sector_fit"]


def driver_corner_form(paths: DataPaths) -> pd.DataFrame:
    """Pre-event EWMA of team-mate-relative corner deltas per category (previous events only)."""
    sess = read_table(paths.gold("driver_corner_sessions"))
    ev = read_table(paths.silver("events"))[["event_id", "date"]]
    sess["event_id"] = sess["session_id"].str[:-2]
    piv = sess.pivot_table(index=["driver_id", "event_id"], columns="category", values="delta_pct", aggfunc="mean").reset_index()
    piv = piv.merge(ev, on="event_id", how="left")
    piv["date"] = pd.to_datetime(piv["date"])
    order = ["date", "event_id"]
    piv = piv.sort_values(order).reset_index(drop=True)
    out = piv[["driver_id", "event_id", "date"]].copy()
    for c in CATS:
        if c in piv:
            out[f"drv_corner_{c}"] = _ewm_prior(piv, "driver_id", c, order, HALF_LIFE_EVENTS)
    return out


def build_sector_dataset(paths: DataPaths) -> pd.DataFrame:
    laps = read_table(paths.gold("all_laps_relative"))
    laps = laps[laps["session_code"].isin(["R", "S"]) & laps["is_representative"]].copy()
    clean = read_table(paths.gold("all_laps_relative"), columns=["session_id", "is_clean", "sector1_s", "sector2_s", "sector3_s"])
    clean = clean[clean["is_clean"]]
    med = clean.groupby("session_id")[["sector1_s", "sector2_s", "sector3_s"]].median()
    lf = read_table(paths.gold("lap_features"))
    keep = ["session_id", "driver_id", "lap_number"] + [c for c in LP.DRIVER + LP.TEAM + LP.TRACK + LP.TYRE + LP.WEATHER + LP.RACE
                                                       + LP.INTERACTION if c in lf.columns] + ["compound", "date", "is_wet_compound"]
    lf = lf[[c for c in dict.fromkeys(keep) if c in lf.columns]]
    rows = []
    for k in (1, 2, 3):
        d = laps[["session_id", "event_id", "season", "driver_id", "constructor_id", "lap_number", f"sector{k}_s", "session_ref_s"]].copy()
        d["sector"] = k
        d["rel_sector_pct"] = 100 * (d[f"sector{k}_s"] / d["session_id"].map(med[f"sector{k}_s"]) - 1)
        d["sector_ref_s"] = d["session_id"].map(med[f"sector{k}_s"])
        rows.append(d.drop(columns=[f"sector{k}_s"]))
    df = pd.concat(rows, ignore_index=True).dropna(subset=["rel_sector_pct"])
    df = df[df["rel_sector_pct"].abs() < 15]
    df = df.merge(lf, on=["session_id", "driver_id", "lap_number"], how="inner")
    sp = read_table(paths.gold("sector_profiles"))
    sp = sp.assign(sector_length_share=sp["length_m"] / sp.groupby("session_id")["length_m"].transform("sum"))
    sp = sp.rename(columns={"frac_slow": "sector_frac_slow", "frac_medium": "sector_frac_medium", "frac_fast": "sector_frac_fast",
                            "full_throttle_frac": "sector_full_throttle_frac"})
    df = df.merge(sp[["event_id", "sector", "sector_frac_slow", "sector_frac_medium", "sector_frac_fast",
                      "sector_full_throttle_frac", "sector_length_share"]], on=["event_id", "sector"], how="inner")
    form = driver_corner_form(paths)
    df = df.merge(form.drop(columns=["date"]), on=["driver_id", "event_id"], how="left")
    df["drv_sector_fit"] = sum(df[f"drv_corner_{c}"].fillna(0) * df[f"sector_frac_{c}"] for c in CATS)
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values(["date", "session_id", "sector"]).reset_index(drop=True)


def evaluate_corner_profile_value(paths: DataPaths, n_boot: int = 300) -> dict:
    df = build_sector_dataset(paths)
    numeric_base = [c for c in LP.DRIVER + LP.TEAM + LP.TYRE + LP.RACE + ["is_wet_compound", "track_temp_c"] + SECTOR_FEATURES
                    if c in df.columns]
    spec_base = FeatureSpec(numeric=numeric_base, categorical=["compound"])
    spec_aug = FeatureSpec(numeric=numeric_base + PROFILE_FEATURES, categorical=["compound"])
    lin_base = FeatureSpec(numeric=[c for c in numeric_base if c not in LP.SESSION_LEVEL], categorical=["compound"])
    lin_aug = FeatureSpec(numeric=lin_base.numeric + PROFILE_FEATURES, categorical=["compound"])
    preds = []
    for split in walk_forward_by_season(df, min_train_seasons=1):
        tr, ca, te = df.loc[split.train_idx], df.loc[split.calib_idx], df.loc[split.test_idx]
        out = te[["event_id", "season", "sector", "rel_sector_pct", "sector_ref_s"]].rename(columns={"rel_sector_pct": "y"}).copy()
        for name, model in [("lgbm_base", LightGBMPaceModel(spec_base)), ("lgbm_profile", LightGBMPaceModel(spec_aug)),
                            ("ridge_base", LinearPaceModel(lin_base)), ("ridge_profile", LinearPaceModel(lin_aug))]:
            if name.startswith("lgbm"):
                model.fit(tr, tr["rel_sector_pct"], X_val=ca, y_val=ca["rel_sector_pct"])
            else:
                model.fit(tr, tr["rel_sector_pct"])
            out[name] = model.predict(te)
        out["fold"] = split.name
        preds.append(out)
        log.info("sector model fold %s done", split.name)
    allp = pd.concat(preds, ignore_index=True)
    res = {"n_rows": int(len(df)), "seasons": sorted(int(s) for s in df["season"].unique()),
           "profile_coverage": float(df["drv_corner_slow"].notna().mean()), "folds": {}}
    for fold, g in allp.groupby("fold"):
        res["folds"][fold] = {m: M.mae(g["y"], g[m]) for m in ["lgbm_base", "lgbm_profile", "ridge_base", "ridge_profile"]}
    res["pooled_mae"] = {m: M.mae(allp["y"], allp[m]) for m in ["lgbm_base", "lgbm_profile", "ridge_base", "ridge_profile"]}
    res["profile_minus_base"] = {
        "lightgbm": M.paired_mae_difference(allp, "lgbm_profile", "lgbm_base", n_boot=n_boot),
        "ridge": M.paired_mae_difference(allp, "ridge_profile", "ridge_base", n_boot=n_boot),
    }
    res["interpretation"] = (
        "Negative differences mean the driver corner profile reduced error. A confidence interval spanning zero "
        "means no repeatable driver x corner-type predictive value was found.")
    return res
