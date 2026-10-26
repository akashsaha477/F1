"""Global explanations: contribution magnitudes, grouped permutation importance and ALE curves.

Inputs are often correlated (driver form and team form; race progress and lap number), so no single
method is trusted on its own: SHAP-style contributions describe how the model *uses* a feature,
grouped permutation importance measures how much *predictive accuracy* depends on a block of
features, and ALE avoids the extrapolation that partial-dependence plots suffer from under correlation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def mean_abs_contributions(model, X: pd.DataFrame, feature_group: dict[str, str]) -> dict:
    base, contrib = model.contributions(X)
    feat = contrib.abs().mean().sort_values(ascending=False)
    signed = contrib.mean()
    groups = contrib.T.groupby(lambda f: feature_group.get(f, "other")).sum().T
    grp = groups.abs().mean().sort_values(ascending=False)
    return {
        "base_value_mean": float(np.mean(base)),
        "features": [{"feature": f, "group": feature_group.get(f, "other"), "mean_abs": float(v),
                      "mean_signed": float(signed[f])} for f, v in feat.items()],
        "groups": [{"group": g, "mean_abs": float(v)} for g, v in grp.items()],
        "n_rows": int(len(X)),
    }


def grouped_permutation_importance(model, X: pd.DataFrame, y, groups: dict[str, list[str]], n_repeats: int = 3,
                                   seed: int = 0) -> list[dict]:
    """Increase in MAE when all columns of a feature group are permuted jointly (rows shuffled together)."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    base_mae = float(np.mean(np.abs(y - model.predict(X))))
    out = []
    for g, cols in groups.items():
        cols = [c for c in cols if c in X.columns]
        if not cols:
            continue
        deltas = []
        for _ in range(n_repeats):
            Xp = X.copy()
            perm = rng.permutation(len(X))
            Xp[cols] = X[cols].to_numpy()[perm]
            deltas.append(float(np.mean(np.abs(y - model.predict(Xp)))) - base_mae)
        out.append({"group": g, "features": cols, "mae_increase": float(np.mean(deltas)),
                    "mae_increase_sd": float(np.std(deltas)), "baseline_mae": base_mae})
    return sorted(out, key=lambda r: -r["mae_increase"])


def ale_1d(model, X: pd.DataFrame, feature: str, n_bins: int = 15) -> dict:
    """First-order accumulated local effects for a numeric feature (centred to mean zero)."""
    x = pd.to_numeric(X[feature], errors="coerce")
    ok = x.notna().to_numpy()
    Xo = X.loc[ok]
    xo = x[ok].to_numpy()
    if len(xo) < 50 or np.unique(xo).size < 3:
        return {"feature": feature, "grid": [], "ale": [], "counts": []}
    edges = np.unique(np.quantile(xo, np.linspace(0, 1, n_bins + 1)))
    if len(edges) < 3:
        return {"feature": feature, "grid": [], "ale": [], "counts": []}
    idx = np.clip(np.searchsorted(edges, xo, side="right") - 1, 0, len(edges) - 2)
    effects, counts = [], []
    for b in range(len(edges) - 1):
        m = idx == b
        counts.append(int(m.sum()))
        if not m.any():
            effects.append(0.0)
            continue
        lo_X, hi_X = Xo.loc[m].copy(), Xo.loc[m].copy()
        lo_X[feature], hi_X[feature] = edges[b], edges[b + 1]
        effects.append(float(np.mean(model.predict(hi_X) - model.predict(lo_X))))
    ale = np.concatenate([[0.0], np.cumsum(effects)])
    centers_w = np.array(counts, dtype=float)
    mid = (ale[:-1] + ale[1:]) / 2
    ale = ale - (np.sum(mid * centers_w) / centers_w.sum() if centers_w.sum() else 0.0)
    return {"feature": feature, "grid": edges.tolist(), "ale": ale.tolist(), "counts": counts}
