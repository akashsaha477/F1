"""Error analysis of the stored walk-forward lap-pace predictions.

Where does the selected model fail, and is it better than the simple team-form baseline there?
Errors and 90% interval coverage are broken down by condition, compound, tyre age, race phase,
session type, driver experience and circuit novelty. Contrasts between groups get event-cluster
bootstrap intervals. The largest event-level errors are listed, per-team signed errors are compared
between the first and second half of each season (do the form features lag car development?), and
the model's ordering of drivers within each session is scored with a Spearman correlation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from apexlens.evaluation import metrics as M
from apexlens.storage.io import read_json, read_table, write_json
from apexlens.storage.paths import DataPaths

BASELINE = "team_adjusted_form"
BUCKETS = {
    "tyre_age": ("tyre_life_laps", [-np.inf, 5, 15, 25, np.inf], ["1-5 laps", "6-15 laps", "16-25 laps", "26+ laps"]),
    "race_phase": ("race_progress", [-np.inf, 1 / 3, 2 / 3, np.inf], ["first third", "middle third", "final third"]),
    "driver_experience": ("drv_form_n", [-np.inf, 0.5, 4.5, 9.5, np.inf],
                          ["no earlier event", "1-4 earlier events", "5-9 earlier events", "10+ earlier events"]),
}


def load_predictions(paths: DataPaths, horizon: str, run_id: str | None = None) -> tuple[pd.DataFrame, dict]:
    run_id = run_id or read_json(paths.models / "evaluation_runs" / "latest.json")["run_id"]
    run = read_json(paths.models / "evaluation_runs" / f"{run_id}.json")
    preds = read_table(paths.models / "evaluation" / f"{run_id}_{horizon}_predictions")
    return preds, run


def add_groups(p: pd.DataFrame) -> pd.DataFrame:
    p = p.copy()
    for name, (col, bins, labels) in BUCKETS.items():
        if col in p.columns:
            p[name] = pd.cut(pd.to_numeric(p[col], errors="coerce"), bins=bins, labels=labels).astype(str)
    if "is_sprint" in p.columns:
        p["session_type"] = np.where(p["is_sprint"].astype(float) > 0, "sprint", "grand prix")
    if "circuit_ref_lap_s" in p.columns:
        p["circuit_novelty"] = np.where(p["circuit_ref_lap_s"].isna(), "no earlier season at circuit", "circuit seen before")
    if "drv_circuit_hist" in p.columns:
        p["driver_circuit_history"] = np.where(p["drv_circuit_hist"].isna(), "no earlier-season race here", "raced here in an earlier season")
    return p


def group_table(p: pd.DataFrame, by: str, model: str, min_n: int = 100) -> list[dict]:
    rows = []
    for k, g in p.groupby(by, observed=True):
        if len(g) < min_n or str(k) == "nan":
            continue
        row = {"group": str(k), "n_laps": int(len(g)), "n_events": int(g["event_id"].nunique()),
               "mae": M.mae(g["y"], g[model]), "bias": float(np.mean(g[model] - g["y"])),
               "baseline_mae": M.mae(g["y"], g[BASELINE])}
        row["skill_vs_baseline"] = 1 - row["mae"] / row["baseline_mae"] if row["baseline_mae"] > 0 else None
        if f"{model}_lo" in g:
            row["coverage_90"] = M.coverage(g["y"], g[f"{model}_lo"], g[f"{model}_hi"])
            row["interval_width"] = M.mean_width(g[f"{model}_lo"], g[f"{model}_hi"])
        rows.append(row)
    return rows


def group_contrast(p: pd.DataFrame, by: str, a: str, b: str, model: str, n_boot: int = 300) -> dict | None:
    """MAE(group a) - MAE(group b), event-cluster bootstrap CI."""
    d = p[p[by].isin([a, b])]
    if d[by].nunique() < 2:
        return None

    def stat(x):
        ea, eb = x[x[by] == a], x[x[by] == b]
        if not len(ea) or not len(eb):
            return np.nan
        return M.mae(ea["y"], ea[model]) - M.mae(eb["y"], eb[model])

    res = M.cluster_bootstrap(d, "event_id", stat, n_boot=n_boot)
    res.update({"by": by, "a": a, "b": b, "significant": bool(res["lo"] > 0 or res["hi"] < 0)})
    return res


def worst_events(p: pd.DataFrame, model: str, events: pd.DataFrame, k: int = 10) -> list[dict]:
    g = p.groupby("event_id").apply(
        lambda d: pd.Series({"n_laps": len(d), "mae": M.mae(d["y"], d[model]), "bias": float(np.mean(d[model] - d["y"])),
                             "baseline_mae": M.mae(d["y"], d[BASELINE]), "wet_share": float((d["condition"] != "dry").mean())}),
        include_groups=False).reset_index()
    g = g.merge(events[["event_id", "official_name", "circuit_id"]], on="event_id", how="left")
    med = float(g["mae"].median())
    out = g.sort_values("mae", ascending=False).head(k)
    rows = []
    for r in out.itertuples(index=False):
        rows.append({"event_id": r.event_id, "name": r.official_name, "circuit_id": r.circuit_id, "n_laps": int(r.n_laps),
                     "mae": float(r.mae), "bias": float(r.bias), "baseline_mae": float(r.baseline_mae),
                     "wet_share": float(r.wet_share), "ratio_to_median_event": float(r.mae / med) if med else None})
    return rows


def team_drift(p: pd.DataFrame, model: str, events: pd.DataFrame, min_laps: int = 200) -> list[dict]:
    """Per constructor-season: mean signed error (pred - actual) in the first and second half of the season.

    The target is relative lap time (higher = slower), so a positive bias means the team was faster than
    predicted (e.g. the car improved faster than its pre-event form features captured) and a negative
    bias means it was slower than predicted.
    """
    d = p.merge(events[["event_id", "round"]], on="event_id", how="left")
    rows = []
    for (season, team), g in d.groupby(["season", "constructor_id"]):
        mid = d.loc[d["season"] == season, "round"].median()
        h1, h2 = g[g["round"] <= mid], g[g["round"] > mid]
        if len(h1) < min_laps or len(h2) < min_laps:
            continue
        b1, b2 = float(np.mean(h1[model] - h1["y"])), float(np.mean(h2[model] - h2["y"]))
        rows.append({"season": int(season), "constructor_id": team, "bias_first_half": b1, "bias_second_half": b2,
                     "change": b2 - b1, "n_laps": int(len(g))})
    return sorted(rows, key=lambda r: -abs(r["change"]))


def session_ranking(p: pd.DataFrame, models: list[str], min_drivers: int = 8) -> dict:
    """Spearman correlation between predicted and actual mean driver pace within each session."""
    out = {}
    for m in models:
        rhos = []
        for _, g in p.groupby("session_id"):
            agg = g.groupby("driver_id")[["y", m]].mean()
            if len(agg) >= min_drivers:
                rhos.append(M.spearman(agg["y"], agg[m]))
        rhos = np.asarray(rhos, dtype=float)
        out[m] = {"n_sessions": int(len(rhos)), "median": float(np.nanmedian(rhos)),
                  "q25": float(np.nanquantile(rhos, 0.25)), "q75": float(np.nanquantile(rhos, 0.75)),
                  "share_below_0_5": float(np.mean(rhos < 0.5))}
    return out


def run_error_analysis(paths: DataPaths, horizon: str = "pre_event", run_id: str | None = None, n_boot: int = 300) -> dict:
    preds, run = load_predictions(paths, horizon, run_id)
    h = run["horizons"][horizon]
    model, holdout = h["selected_model"], int(h["holdout_season"])
    p = add_groups(preds)
    events = read_table(paths.silver("events"))
    parts = {"development": p[p["season"] < holdout], "holdout": p[p["season"] == holdout]}
    dims = [c for c in ["condition", "compound", "session_type", *BUCKETS, "circuit_novelty", "driver_circuit_history",
                        "constructor_id"] if c in p.columns]
    out: dict = {"run_id": run["run_id"], "horizon": horizon, "model": model, "baseline": BASELINE, "holdout_season": holdout,
                 "breakdowns": {}, "contrasts": [], "notes": []}
    for part, d in parts.items():
        out["breakdowns"][part] = {dim: group_table(d, dim, model) for dim in dims}
    contrasts = [("condition", "wet", "dry"), ("session_type", "sprint", "grand prix"),
                 ("tyre_age", "26+ laps", "1-5 laps"), ("race_phase", "final third", "first third"),
                 ("driver_experience", "no earlier event", "10+ earlier events"),
                 ("circuit_novelty", "no earlier season at circuit", "circuit seen before")]
    for by, a, b in contrasts:
        if by in p.columns:
            res = group_contrast(p, by, a, b, model, n_boot=n_boot)
            if res:
                out["contrasts"].append(res)
    out["worst_events"] = {part: worst_events(d, model, events) for part, d in parts.items() if len(d)}
    out["team_drift"] = team_drift(p, model, events)
    out["session_ranking"] = session_ranking(p, [model, BASELINE, "ridge"])
    out["notes"] = [
        "Errors are in percentage points of the session reference lap (median clean lap of the session).",
        "Development = pooled walk-forward folds before the holdout season; holdout = final season, used once.",
        "Groups with fewer than 100 laps are omitted. Contrast intervals resample whole events.",
        "Wet-condition laps are rare; their intervals are wide.",
    ]
    write_json(paths.models / "evaluation_runs" / f"error_analysis_{horizon}.json", out)
    return out
