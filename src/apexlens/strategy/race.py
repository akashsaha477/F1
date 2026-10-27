"""Finishing-order prediction.

Every car is given the same optimal tyre plan, so the plan does not reorder the field; what separates the
cars is their expected pace and where they start. Overtaking is hard, so the order is a blend of the two:
``score = w * grid rank + (1 - w) * pace rank``. The weight ``w`` is fitted on earlier races only (maximum
mean Spearman correlation with the classified finishing order). Retirements are not predicted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

DEFAULT_W = 0.5
GRID = np.round(np.linspace(0, 1, 21), 2)


def predict_order(field: pd.DataFrame, w: float) -> pd.DataFrame:
    """``field``: driver_id, grid, base_pct. Adds pace_rank, score and predicted_position."""
    f = field.copy()
    grid = f["grid"].astype(float)
    f["grid_used"] = grid.fillna(grid.max() + 1 if grid.notna().any() else len(f))
    f["grid_rank"] = f["grid_used"].rank(method="first")
    f["pace_rank"] = f["base_pct"].rank(method="first")
    f["score"] = w * f["grid_rank"] + (1 - w) * f["pace_rank"]
    f = f.sort_values(["score", "pace_rank"])
    f["predicted_position"] = np.arange(1, len(f) + 1)
    return f


def order_metrics(pred: pd.Series, actual: pd.Series) -> dict:
    """Metrics on classified finishers; ``pred`` and ``actual`` are positions indexed by driver."""
    both = pd.DataFrame({"p": pred, "a": actual}).dropna()
    if len(both) < 5:
        return {}
    both["p"] = both["p"].rank(method="first")  # re-rank among finishers
    rho = float(stats.spearmanr(both["p"], both["a"]).statistic)
    win_pred = both["p"].idxmin()
    podium = len(set(both.nsmallest(3, "p").index) & set(both.nsmallest(3, "a").index)) / 3
    return {"spearman": rho, "winner_correct": bool(win_pred == both["a"].idxmin()), "podium_overlap": podium,
            "position_mae": float(np.mean(np.abs(both["p"] - both["a"]))), "n_finishers": int(len(both))}


def fit_weight(rows: pd.DataFrame) -> tuple[float, int]:
    """Blend weight maximising mean Spearman over the races in ``rows`` (event_id, driver_id, grid, base_pct, position)."""
    races = []
    for _, g in rows.groupby("event_id"):
        fin = g["position"].notna().to_numpy()
        if fin.sum() < 5:
            continue
        grid = g["grid"].astype(float)
        grid = grid.fillna(grid.max() + 1 if grid.notna().any() else len(g)).to_numpy()
        races.append((stats.rankdata(grid, method="ordinal"), stats.rankdata(g["base_pct"].to_numpy(), method="ordinal"),
                      g["position"].to_numpy(float), fin))
    if not races:
        return DEFAULT_W, 0
    best, best_w = -np.inf, DEFAULT_W
    for w in GRID:
        vals = []
        for gr, pr, pos, fin in races:
            score = w * gr + (1 - w) * pr + 1e-6 * pr  # ties broken by pace, as in predict_order
            vals.append(stats.spearmanr(score[fin], pos[fin]).statistic)
        if np.mean(vals) > best + 1e-9:
            best, best_w = float(np.mean(vals)), float(w)
    return best_w, len(races)
