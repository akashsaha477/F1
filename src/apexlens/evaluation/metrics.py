"""Regression, interval and ranking metrics with cluster-bootstrap confidence intervals.

Laps of one event are strongly correlated, so uncertainty is estimated by resampling whole events
(cluster bootstrap) rather than individual laps.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def mae(y, p) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def rmse(y, p) -> float:
    return float(np.sqrt(np.mean((np.asarray(y) - np.asarray(p)) ** 2)))


def r2(y, p) -> float:
    y, p = np.asarray(y), np.asarray(p)
    ss = np.sum((y - y.mean()) ** 2)
    return float(1 - np.sum((y - p) ** 2) / ss) if ss > 0 else float("nan")


def coverage(y, lo, hi) -> float:
    y = np.asarray(y)
    return float(np.mean((y >= np.asarray(lo)) & (y <= np.asarray(hi))))


def mean_width(lo, hi) -> float:
    return float(np.mean(np.asarray(hi) - np.asarray(lo)))


def regression_report(y, p, lo=None, hi=None) -> dict:
    out = {"n": int(len(y)), "mae": mae(y, p), "rmse": rmse(y, p), "r2": r2(y, p),
           "bias": float(np.mean(np.asarray(p) - np.asarray(y)))}
    if lo is not None and hi is not None:
        out["coverage"] = coverage(y, lo, hi)
        out["interval_width"] = mean_width(lo, hi)
    return out


def cluster_bootstrap(df: pd.DataFrame, cluster: str, stat, n_boot: int = 500, seed: int = 11, level: float = 0.95) -> dict:
    """Percentile CI of ``stat(df_resampled)`` resampling clusters with replacement."""
    rng = np.random.default_rng(seed)
    groups = {k: g for k, g in df.groupby(cluster)}
    keys = np.array(list(groups))
    vals = []
    for _ in range(n_boot):
        pick = rng.choice(keys, size=len(keys), replace=True)
        vals.append(stat(pd.concat([groups[k] for k in pick], ignore_index=True)))
    vals = np.asarray(vals, dtype=float)
    a = (1 - level) / 2
    return {"estimate": float(stat(df)), "lo": float(np.nanquantile(vals, a)), "hi": float(np.nanquantile(vals, 1 - a)),
            "n_clusters": int(len(keys)), "n_boot": n_boot}


def paired_mae_difference(df: pd.DataFrame, a: str, b: str, y: str = "y", cluster: str = "event_id",
                          n_boot: int = 500, seed: int = 11) -> dict:
    """MAE(a) - MAE(b) with an event-cluster bootstrap CI (negative = a better)."""
    def stat(d):
        return float(np.mean(np.abs(d[y] - d[a])) - np.mean(np.abs(d[y] - d[b])))
    res = cluster_bootstrap(df, cluster, stat, n_boot=n_boot, seed=seed)
    res["significant"] = bool(res["hi"] < 0 or res["lo"] > 0)
    return res


def breakdown(df: pd.DataFrame, by: str, y: str, p: str, min_n: int = 50) -> list[dict]:
    rows = []
    for k, g in df.groupby(by):
        if len(g) < min_n:
            continue
        rows.append({by: k, "n": int(len(g)), "mae": mae(g[y], g[p]), "bias": float(np.mean(g[p] - g[y]))})
    return sorted(rows, key=lambda r: -r["mae"])


def spearman(a, b) -> float:
    return float(stats.spearmanr(a, b).statistic)


def residual_summary(resid) -> dict:
    r = np.asarray(resid)
    q = np.quantile(r, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    return {"quantiles": dict(zip(["p01", "p05", "p25", "p50", "p75", "p95", "p99"], map(float, q), strict=True)),
            "skew": float(stats.skew(r)), "kurtosis": float(stats.kurtosis(r))}
