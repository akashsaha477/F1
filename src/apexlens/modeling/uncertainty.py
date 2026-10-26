"""Prediction intervals.

Split-conformal intervals from absolute residuals on a held-out, chronologically later calibration
set. "Mondrian" variant: separate quantiles per condition group (dry / wet) so wet laps, which are
much noisier, do not borrow the narrow dry intervals. Groups with too few calibration rows fall
back to the pooled quantile.

Laps within a session are correlated, so the exchangeability assumption of conformal prediction
only holds approximately; empirical coverage on later test seasons is therefore always reported.
"""

from __future__ import annotations

import numpy as np


def conformal_quantile(abs_resid: np.ndarray, alpha: float) -> float:
    r = np.sort(np.asarray(abs_resid, dtype=float))
    n = len(r)
    if n == 0:
        return float("nan")
    k = int(np.ceil((n + 1) * (1 - alpha))) - 1
    return float(r[min(max(k, 0), n - 1)])


class MondrianConformal:
    def __init__(self, alpha: float = 0.1, min_group: int = 200):
        self.alpha, self.min_group = alpha, min_group

    def fit(self, y, pred, groups) -> MondrianConformal:
        res = np.abs(np.asarray(y) - np.asarray(pred))
        groups = np.asarray(groups)
        self.global_q_ = conformal_quantile(res, self.alpha)
        self.group_q_ = {}
        self.group_n_ = {}
        for g in np.unique(groups):
            m = groups == g
            self.group_n_[str(g)] = int(m.sum())
            if m.sum() >= self.min_group:
                self.group_q_[str(g)] = conformal_quantile(res[m], self.alpha)
        return self

    def half_width(self, groups) -> np.ndarray:
        return np.array([self.group_q_.get(str(g), self.global_q_) for g in np.asarray(groups)])

    def interval(self, pred, groups) -> tuple[np.ndarray, np.ndarray]:
        hw = self.half_width(groups)
        return np.asarray(pred) - hw, np.asarray(pred) + hw

    def to_dict(self) -> dict:
        return {"alpha": self.alpha, "level": 1 - self.alpha, "global_half_width": self.global_q_,
                "group_half_width": self.group_q_, "calibration_n": self.group_n_, "method": "split-conformal (Mondrian by condition)"}


def condition_group(df) -> np.ndarray:
    wet = np.asarray(df["is_wet_compound"]).astype(float) > 0.5
    return np.where(wet, "wet", "dry")
