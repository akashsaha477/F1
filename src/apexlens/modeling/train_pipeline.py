"""Train, evaluate and register the lap-pace models; write experiment records.

Experiment record contents: dataset version, source manifest summary, feature-set version, training /
calibration / test periods, model configurations, seeds, software environment, metrics (development
folds and the untouched final holdout season), interval diagnostics, global explanations and the
artifact versions.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import UTC, datetime

import pandas as pd

from apexlens.data_sources.registry import ProvenanceRegistry
from apexlens.evaluation import metrics as M
from apexlens.explainability.global_explain import (
    ale_1d,
    grouped_permutation_importance,
    mean_abs_contributions,
)
from apexlens.modeling import lap_pace as LP
from apexlens.modeling.registry import environment, make_version, save_artifact, set_production, short_hash
from apexlens.storage.io import read_json, sha256_bytes, write_json, write_table
from apexlens.storage.paths import DataPaths

log = logging.getLogger(__name__)

ALE_FEATURES = ["race_progress", "tyre_life_laps", "drv_form_pace", "team_form_pace", "drv_quali_form",
                "track_temp_c", "evt_quali_gap"]


def dataset_version(paths: DataPaths) -> dict:
    manifest = paths.manifests / "sessions_ingested.json"
    lf = sorted(paths.gold("lap_features").glob("*.parquet"))
    f1db = read_json(paths.manifests / "f1db_seasons.json", default=[])
    return {
        "sessions_manifest_sha": sha256_bytes(manifest.read_bytes())[:16] if manifest.exists() else None,
        "lap_features_sha": sha256_bytes(lf[0].read_bytes())[:16] if lf else None,
        "f1db_seasons": len(f1db),
    }


def _strip(metrics: dict) -> dict:
    return {k: {kk: vv for kk, vv in v.items()} for k, v in metrics.items()}


def global_explanations(wf: dict, sample: int = 15000, seed: int = 0) -> dict:
    """Explanations of the last walk-forward fold's models on their own (unseen) test season."""
    last = wf["last_fold"]
    df = wf["data"]
    test = df.loc[last["split"].test_idx]
    if len(test) > sample:
        test = test.sample(sample, random_state=seed)
    out = {"explained_on": f"test season {last['split'].test_period} (model trained on {last['split'].train_period})",
           "n_rows": int(len(test))}
    lgbm = last["fitted"].get("lightgbm", {}).get("model")
    ridge = last["fitted"].get("ridge", {}).get("model")
    groups = {g: [f for f in fs if f in test.columns] for g, fs in LP.GROUPS.items()}
    if lgbm is not None:
        out["lightgbm_contributions"] = mean_abs_contributions(lgbm, test, LP.FEATURE_GROUP)
        out["lightgbm_gain_importance"] = lgbm.split_importance()
        out["lightgbm_permutation"] = grouped_permutation_importance(lgbm, test, test[LP.TARGET], groups, n_repeats=3)
        out["ale"] = [ale_1d(lgbm, test, f) for f in ALE_FEATURES if f in lgbm.spec.numeric]
    if ridge is not None:
        out["ridge_contributions"] = mean_abs_contributions(ridge, test, LP.FEATURE_GROUP)
        out["ridge_coefficients"] = ridge.coefficients()
    if lgbm is not None and ridge is not None:
        a = {r["feature"]: r["mean_abs"] for r in out["lightgbm_contributions"]["features"]}
        b = {r["feature"]: r["mean_abs"] for r in out["ridge_contributions"]["features"]}
        common = sorted(set(a) & set(b))
        out["method_agreement"] = {"features_compared": common,
                                   "spearman_lightgbm_vs_ridge": M.spearman([a[f] for f in common], [b[f] for f in common])
                                   if len(common) > 2 else None}
    return out


def train_lap_pace(paths: DataPaths, horizons=("pre_event", "pre_race"), n_boot: int = 300, seed: int = 42) -> dict:
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    dv = dataset_version(paths)
    sources = ProvenanceRegistry(paths.manifests).summary()
    summary = {"run_id": run_id, "task": LP.TASK, "target": LP.TARGET, "dataset_version": dv,
               "source_manifest": sources, "environment": environment(), "seed": seed, "horizons": {}}
    for horizon in horizons:
        log.info("walk-forward evaluation (%s)", horizon)
        wf = LP.run_walk_forward(paths, horizon=horizon, n_boot=n_boot)
        log.info("event-held-out folds (%s)", horizon)
        ek = LP.run_event_kfold(paths, horizon=horizon)
        expl = global_explanations(wf)
        dev = wf["pooled"]["development"]
        selected = min(dev, key=lambda m: dev[m]["mae"])
        log.info("selected %s by development MAE", selected)

        preds = wf["predictions"]
        write_table(paths.models / "evaluation" / f"{run_id}_{horizon}_predictions", preds)
        final = LP.fit_final(paths, horizon=horizon)
        versions = {}
        spec_dict = asdict(final["spec"])
        for name, fitted in final["fitted"].items():
            config = {"model": name, "horizon": horizon, "spec": spec_dict, "params": getattr(fitted["model"], "params", None),
                      "data": dv}
            version = make_version(f"{LP.TASK}_{horizon}", name, config)
            meta = {
                "task": f"{LP.TASK}_{horizon}", "model": name, "horizon": horizon, "target": LP.TARGET,
                "target_unit": "% of session reference lap (negative = faster)",
                "feature_set_version": short_hash(spec_dict), "features": spec_dict,
                "feature_ranges": final["feature_ranges"], "compound_counts": final["compound_counts"],
                "train_period": final["train_period"], "calibration_events": final["calib_events"],
                "conformal": fitted["conformal"].to_dict(), "dataset_version": dv, "seed": seed,
                "environment": summary["environment"], "evaluation_run": run_id,
                "test_metrics": {"development": dev[name], "holdout": wf["pooled"]["holdout"][name]},
                "is_production": name == selected,
            }
            save_artifact(paths.models, version, {"model": fitted["model"], "conformal": fitted["conformal"],
                                                  "spec": final["spec"], "horizon": horizon}, meta)
            versions[name] = version
        set_production(paths.models, f"{LP.TASK}_{horizon}", versions[selected])
        write_json(paths.models / versions[selected] / "global_explanations.json", expl)
        summary["horizons"][horizon] = {
            "spec": wf["spec"], "folds": wf["folds"], "pooled": wf["pooled"], "comparisons": wf["comparisons"],
            "holdout_season": wf["holdout_season"], "event_kfold": ek, "selected_model": selected,
            "selection_rule": "lowest MAE on development walk-forward folds (holdout season not used for selection)",
            "versions": versions, "global_explanations": expl,
            "residuals_selected": M.residual_summary(preds[selected] - preds["y"]),
            "error_breakdown": {
                by: M.breakdown(preds[preds.season == wf["holdout_season"]], by, "y", selected)
                for by in ["circuit_id", "driver_id", "compound", "condition", "constructor_id"]},
        }
    if {"pre_event", "pre_race"} <= set(summary["horizons"]):
        summary["horizon_gain_pre_race_vs_pre_event"] = horizon_gain(paths, summary, n_boot=n_boot)
    write_json(paths.models / "evaluation_runs" / f"{run_id}.json", summary)
    write_json(paths.models / "evaluation_runs" / "latest.json", {"run_id": run_id})
    return summary


def horizon_gain(paths: DataPaths, run: dict, n_boot: int = 300) -> dict | None:
    """Paired comparison of the selected pre-race vs pre-event model on identical test laps."""
    try:
        pe = pd.read_parquet(sorted((paths.models / "evaluation" / f"{run['run_id']}_pre_event_predictions").glob("*.parquet"))[0])
        pr = pd.read_parquet(sorted((paths.models / "evaluation" / f"{run['run_id']}_pre_race_predictions").glob("*.parquet"))[0])
    except IndexError:
        return None
    m1, m2 = run["horizons"]["pre_event"]["selected_model"], run["horizons"]["pre_race"]["selected_model"]
    d = pe[["event_id", "season", "y", m1]].rename(columns={m1: "pre_event"})
    d["pre_race"] = pr[m2].to_numpy()
    holdout = run["horizons"]["pre_event"]["holdout_season"]
    return {part: M.paired_mae_difference(g, "pre_race", "pre_event", n_boot=n_boot)
            for part, g in (("development", d[d.season < holdout]), ("holdout", d[d.season == holdout]))}

