"""Model F (extension) — pre-event qualifying gap to pole.

Target: a driver's qualifying gap to pole (%) from F1DB, dry sessions with gap <= 5%. Inputs are
pre-event form features only (no information from the weekend being predicted). Compared with a
team-qualifying-form baseline; evaluated with MAE and per-event rank agreement (Spearman) and
pole/top-3 hit rates, walk-forward by season.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from apexlens.driver_profiles.fingerprint import QUALI_MAX_GAP, quali_table
from apexlens.evaluation import metrics as M
from apexlens.evaluation.splits import walk_forward_by_season
from apexlens.modeling.models import FeatureSpec, LightGBMPaceModel
from apexlens.storage.io import read_table, write_json
from apexlens.storage.paths import DataPaths

FEATURES = ["drv_quali_form", "team_quali_form", "drv_form_pace", "team_form_pace", "drv_teammate_gap_form", "drv_form_n",
            "team_season_events", "team_season_form", "circuit_frac_slow", "circuit_frac_fast", "circuit_full_throttle_frac"]


def run_quali_model(paths: DataPaths, n_boot: int = 200) -> dict:
    form = read_table(paths.gold("driver_event_form"))
    seasons = sorted(form["season"].unique().tolist())
    q = quali_table(paths, seasons)
    q = q[(q["condition"] == "dry") & (q["quali_gap_pct"] <= QUALI_MAX_GAP)]
    df = q[["event_id", "driver_id", "quali_gap_pct", "position"]].merge(form, on=["event_id", "driver_id"], how="inner")
    prof = read_table(paths.gold("circuit_profiles"))
    if len(prof):
        df = df.merge(prof[["circuit_id", "circuit_frac_slow", "circuit_frac_fast", "circuit_full_throttle_frac"]], on="circuit_id", how="left")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "event_id"]).reset_index(drop=True)
    spec = FeatureSpec(numeric=[f for f in FEATURES if f in df.columns], categorical=[])
    preds = []
    for split in walk_forward_by_season(df, min_train_seasons=1):
        tr, ca, te = df.loc[split.train_idx], df.loc[split.calib_idx], df.loc[split.test_idx]
        m = LightGBMPaceModel(spec, params={"min_child_samples": 30}).fit(tr, tr["quali_gap_pct"], X_val=ca, y_val=ca["quali_gap_pct"])
        out = te[["event_id", "season", "driver_id", "quali_gap_pct", "position"]].rename(columns={"quali_gap_pct": "y"}).copy()
        out["lightgbm"] = m.predict(te)
        out["team_form_baseline"] = te["team_quali_form"].fillna(tr["quali_gap_pct"].median()).to_numpy()
        preds.append(out)
    p = pd.concat(preds, ignore_index=True)
    res = {"n_rows": int(len(p)), "target": "qualifying gap to pole, % (dry, <= 5%)", "models": {}}
    for m in ["lightgbm", "team_form_baseline"]:
        rho, top1, top3 = [], [], []
        for _, g in p.groupby("event_id"):
            if len(g) < 5:
                continue
            rho.append(M.spearman(g["y"], g[m]))
            top1.append(g.loc[g[m].idxmin(), "y"] == g["y"].min())
            top3.append(len(set(g.nsmallest(3, m)["driver_id"]) & set(g.nsmallest(3, "y")["driver_id"])) / 3)
        res["models"][m] = {"mae": M.mae(p["y"], p[m]), "mean_event_spearman": float(np.mean(rho)),
                            "pole_hit_rate": float(np.mean(top1)), "top3_overlap": float(np.mean(top3)), "n_events": len(rho)}
    res["lightgbm_vs_baseline"] = M.paired_mae_difference(p, "lightgbm", "team_form_baseline", n_boot=n_boot)
    res["note"] = "Pre-event forecast; the weekend's practice and qualifying are not used. Wet qualifying sessions are excluded."
    write_json(paths.models / "evaluation_runs" / "quali_model.json", res)
    return res
