"""Explanation validation for the production lap-pace models.

Checks (all computed, none asserted a priori):

1. exactness: LightGBM's TreeSHAP contributions vs the ``shap`` library, and additivity
   (base + contributions = prediction);
2. stability under resampling: global importance rankings and local top-feature signs across the
   event-bootstrap ensemble;
3. sensitivity: prediction and explanation change for small input perturbations;
4. agreement across model versions (pre-event vs pre-race) and with an interpretable model (Ridge,
   from the evaluation run);
5. correlated inputs: pairs of features whose credit SHAP may split arbitrarily.
"""

from __future__ import annotations

import itertools
import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from scipy import stats

from apexlens.modeling import lap_pace as LP
from apexlens.modeling.registry import load_artifact, production_version
from apexlens.predictions.service import evaluation_run
from apexlens.storage.io import write_json
from apexlens.storage.paths import DataPaths

log = logging.getLogger(__name__)


def _global_rank(model, X: pd.DataFrame) -> pd.Series:
    _, c = model.contributions(X)
    return c.abs().mean()


def validate_explanations(paths: DataPaths, horizon: str = "pre_event", n_rows: int = 3000, seed: int = 0) -> dict:
    version = production_version(paths.models, f"{LP.TASK}_{horizon}")
    obj, meta = load_artifact(paths.models, version)
    model = obj["model"]
    ens_path = Path(paths.models) / version / "ensemble.joblib"
    ensemble = joblib.load(ens_path) if ens_path.exists() else []
    df = LP.load_dataset(paths)
    latest = df[df["season"] == df["season"].max()]
    X = latest.sample(min(n_rows, len(latest)), random_state=seed)
    out: dict = {"model_version": version, "horizon": horizon, "n_rows": int(len(X)), "sample": f"season {int(df['season'].max())}"}

    # 1. exactness ---------------------------------------------------------------------------------
    base, contrib = model.contributions(X)
    pred = model.predict(X)
    out["additivity_max_abs_error"] = float(np.max(np.abs(base + contrib.sum(axis=1).to_numpy() - pred)))
    sub = X.iloc[:300]
    try:
        sv = shap.TreeExplainer(model.model.booster_).shap_values(model._prep(sub))
        _, c_sub = model.contributions(sub)
        out["treeshap_vs_shap_library_max_abs_diff"] = float(np.max(np.abs(sv - c_sub.to_numpy())))
    except Exception as exc:  # noqa: BLE001 - report rather than fail
        out["treeshap_vs_shap_library_error"] = str(exc)

    # 2. stability across bootstrap refits ------------------------------------------------------------
    if ensemble:
        ranks = pd.DataFrame({i: _global_rank(m, X) for i, m in enumerate(ensemble)})
        rho = [stats.spearmanr(ranks[a], ranks[b]).statistic for a, b in itertools.combinations(ranks.columns, 2)]
        tops = [set(ranks[c].sort_values(ascending=False).index[:5]) for c in ranks.columns]
        jac = [len(a & b) / len(a | b) for a, b in itertools.combinations(tops, 2)]
        prod_top = list(_global_rank(model, X).sort_values(ascending=False).index[:5])
        out["global_stability"] = {
            "n_models": len(ensemble), "mean_pairwise_spearman": float(np.mean(rho)), "min_pairwise_spearman": float(np.min(rho)),
            "mean_top5_jaccard": float(np.mean(jac)), "production_top5": prod_top,
            "top5_frequency": {f: float(np.mean([f in t for t in tops])) for f in prod_top},
            "importance_cv": {f: float(ranks.loc[f].std() / ranks.loc[f].mean()) for f in prod_top},
        }
        rows = X.iloc[:200]
        local = np.stack([m.contributions(rows)[1][contrib.columns].to_numpy() for m in ensemble])  # models x rows x features
        _, c_prod = model.contributions(rows)
        agree, sds = [], []
        for i in range(len(rows)):
            top = np.argsort(-np.abs(c_prod.iloc[i].to_numpy()))[:3]
            sign = np.sign(c_prod.iloc[i].to_numpy()[top])
            agree.append(np.mean(np.sign(local[:, i, top]) == sign))
            sds.append(np.mean(local[:, i, top].std(axis=0)))
        out["local_stability"] = {"rows": int(len(rows)), "top3_sign_agreement": float(np.mean(agree)),
                                  "mean_sd_of_top3_contributions_pct": float(np.mean(sds))}

    # 3. sensitivity to small perturbations ------------------------------------------------------------
    rng = np.random.default_rng(seed)
    sens = {}
    for f in [c for c in model.spec.numeric if c in X.columns]:
        col = pd.to_numeric(df[f], errors="coerce")
        sd = float(col.std())
        if not np.isfinite(sd) or sd == 0 or col.nunique() <= 2:
            continue  # small perturbations of binary flags are not meaningful
        Xp = X.copy()
        Xp[f] = pd.to_numeric(Xp[f], errors="coerce") + 0.05 * sd * rng.choice([-1, 1], len(X))
        d = np.abs(model.predict(Xp) - pred)
        sens[f] = {"mean_abs_change_pct": float(np.mean(d)), "p99_abs_change_pct": float(np.quantile(d, 0.99))}
    out["sensitivity_5pct_sd"] = dict(sorted(sens.items(), key=lambda kv: -kv[1]["mean_abs_change_pct"]))

    # 4. agreement across versions / with an interpretable model -------------------------------------
    other_h = "pre_race" if horizon == "pre_event" else "pre_event"
    other_v = production_version(paths.models, f"{LP.TASK}_{other_h}")
    if other_v:
        o_obj, _ = load_artifact(paths.models, other_v)
        a, b = _global_rank(model, X), _global_rank(o_obj["model"], X)
        common = sorted(set(a.index) & set(b.index))
        out["cross_version"] = {"other_version": other_v,
                                "spearman_global_importance": float(stats.spearmanr(a[common], b[common]).statistic)}
    run = evaluation_run(paths)
    if run and horizon in run.get("horizons", {}):
        ge = run["horizons"][horizon]["global_explanations"]
        lg = {r["feature"]: r for r in ge["lightgbm_contributions"]["features"]}
        rg = {r["feature"]: r for r in ge.get("ridge_contributions", {}).get("features", [])}
        common = sorted(set(lg) & set(rg))
        if len(common) > 2:
            out["vs_ridge"] = {
                "features_compared": common,
                "spearman_mean_abs": float(stats.spearmanr([lg[f]["mean_abs"] for f in common], [rg[f]["mean_abs"] for f in common]).statistic),
                "sign_agreement_of_mean_effect": float(np.mean([np.sign(lg[f]["mean_signed"]) == np.sign(rg[f]["mean_signed"])
                                                               for f in common])),
                "explained_on": ge.get("explained_on"),
            }

    # 5. correlated inputs ----------------------------------------------------------------------------
    num = [c for c in model.spec.numeric if c in X.columns]
    corr = X[num].apply(pd.to_numeric, errors="coerce").corr(method="spearman")
    pairs = [{"a": a, "b": b, "spearman": float(corr.loc[a, b])} for a, b in itertools.combinations(num, 2)
             if np.isfinite(corr.loc[a, b]) and abs(corr.loc[a, b]) >= 0.6]
    out["correlated_pairs"] = sorted(pairs, key=lambda r: -abs(r["spearman"]))
    out["notes"] = [
        "SHAP values are exact for the fitted trees but split credit arbitrarily between strongly correlated inputs; "
        "grouped permutation importance (evaluation run) is the safer guide for correlated groups.",
        "None of these checks establishes causality.",
    ]
    write_json(Path(paths.models) / version / "explanation_validation.json", out)
    return out
