"""Feature-group ablations for Model A (LightGBM, walk-forward by season).

* cumulative: driver -> + team/car -> + track -> + tyre -> + weather -> + race context ->
  + driver x circuit interaction -> + corner profile
* leave-one-group-out from the full pre-event feature set

Each configuration is compared with the full model on identical test laps (paired, event-cluster
bootstrap). Reported on development folds and the final holdout season separately.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from apexlens.evaluation import metrics as M
from apexlens.evaluation.splits import walk_forward_by_season
from apexlens.modeling import lap_pace as LP
from apexlens.modeling.models import FeatureSpec, LightGBMPaceModel
from apexlens.storage.io import write_json
from apexlens.storage.paths import DataPaths

log = logging.getLogger(__name__)

ORDER = ["driver", "team", "track", "tyre", "weather", "race_context", "interaction", "corner"]


def spec_for(groups: list[str], available: set[str]) -> FeatureSpec:
    numeric = [f for g in groups for f in LP.GROUPS[g] if f != "compound" and f in available]
    categorical = ["compound"] if "tyre" in groups else []
    return FeatureSpec(numeric=numeric, categorical=categorical)


def _predict_all(df: pd.DataFrame, spec: FeatureSpec) -> np.ndarray:
    pred = np.full(len(df), np.nan)
    for split in walk_forward_by_season(df, min_train_seasons=1):
        tr, ca, te = df.loc[split.train_idx], df.loc[split.calib_idx], df.loc[split.test_idx]
        m = LightGBMPaceModel(spec).fit(tr, tr[LP.TARGET], X_val=ca, y_val=ca[LP.TARGET])
        pred[split.test_idx] = m.predict(te)
    return pred


def run_ablations(paths: DataPaths, n_boot: int = 200) -> dict:
    df = LP.load_dataset(paths)
    avail = set(df.columns)
    full_groups = [g for g in ORDER]
    configs = {}
    for i in range(1, len(ORDER) + 1):
        configs["+".join(ORDER[:i])] = ("cumulative", ORDER[:i])
    for g in ORDER:
        configs[f"full_minus_{g}"] = ("leave_one_out", [x for x in full_groups if x != g])
    preds = {}
    for name, (_, groups) in configs.items():
        spec = spec_for(groups, avail)
        if not spec.all:
            continue
        log.info("ablation %s (%d features)", name, len(spec.all))
        preds[name] = _predict_all(df, spec)
    full_name = "+".join(ORDER)
    test = df[~np.isnan(preds[full_name])].copy()
    holdout = int(test["season"].max())
    for k, v in preds.items():
        test[k] = v[test.index]
    out = {"target": LP.TARGET, "model": "lightgbm (Huber)", "full_config": full_name, "holdout_season": holdout,
           "configs": []}
    for name, (kind, groups) in configs.items():
        if name not in preds:
            continue
        row = {"name": name, "kind": kind, "groups": groups, "n_features": len(spec_for(groups, avail).all)}
        for part, d in (("development", test[test["season"] < holdout]), ("holdout", test[test["season"] == holdout])):
            row[part] = {"mae": M.mae(d["y"] if "y" in d else d[LP.TARGET], d[name])}
            if name != full_name:
                dd = d.rename(columns={LP.TARGET: "y"})
                row[part]["vs_full"] = M.paired_mae_difference(dd, name, full_name, n_boot=n_boot)
        out["configs"].append(row)
    write_json(paths.models / "evaluation_runs" / "ablations.json", out)
    return out
