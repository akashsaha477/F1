"""Linear mixed model with crossed random effects, fitted by REML through Henderson's equations.

    y = X b + sum_k Z_k u_k + e,    u_k ~ N(0, s2_k I),    e_i ~ N(0, s2_e + m_i)

``m_i`` is a *known* measurement variance per observation (e.g. the squared standard error of a
driver's adjusted pace in one race), so noisy observations are automatically down-weighted.

With ``C`` the mixed-model-equation matrix, the REML log-likelihood is (up to a constant)

    -1/2 [ log|R| + sum_k q_k log s2_k + log|C| + y'R^-1 y - sol' rhs ]

which only needs a Cholesky factorisation of a (p + q) x (p + q) matrix, so dozens of drivers,
team-seasons and events are cheap. ``C^-1`` gives prediction-error (co)variances of the BLUPs,
i.e. the posterior uncertainty of each effect given the estimated variance components.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from scipy import linalg, optimize


@dataclass
class MixedModelResult:
    fixed: pd.Series
    effects: dict[str, pd.DataFrame]  # block -> DataFrame(level, estimate, pev)
    variances: dict[str, float]
    loglik: float
    n_obs: int
    converged: bool
    cov_inv: np.ndarray = field(repr=False)
    index: dict[str, dict[str, int]] = field(repr=False)
    p: int = 0

    def combined(self, terms: list[tuple[str, str]]) -> tuple[float, float]:
        """Estimate and prediction-error variance of a sum of random effects, e.g. driver + driver-season."""
        idx = [self.p + self.index[b][lvl] for b, lvl in terms if lvl in self.index[b]]
        est = sum(float(self.effects[b].set_index("level").loc[lvl, "estimate"]) for b, lvl in terms
                  if lvl in self.index[b])
        if not idx:
            return 0.0, float("nan")
        sub = self.cov_inv[np.ix_(idx, idx)]
        return est, float(sub.sum())


def _design(levels: pd.Series) -> tuple[np.ndarray, list[str]]:
    cats = pd.Categorical(levels.astype(str))
    Z = np.zeros((len(levels), len(cats.categories)))
    Z[np.arange(len(levels)), cats.codes] = 1.0
    return Z, list(cats.categories)


def fit_mixed_model(df: pd.DataFrame, y: str, random: list[str], fixed: list[str] | None = None,
                    meas_var: str | None = None, init: dict[str, float] | None = None) -> MixedModelResult:
    """Fit by REML. ``fixed`` are categorical columns entered as fixed effects (plus an intercept)."""
    yv = df[y].to_numpy(dtype=float)
    n = len(yv)
    X_parts = [np.ones((n, 1))]
    fixed_names = ["intercept"]
    for f in fixed or []:
        Zf, lv = _design(df[f])
        X_parts.append(Zf[:, 1:])  # drop first level (reference)
        fixed_names += [f"{f}={v}" for v in lv[1:]]
    X = np.hstack(X_parts)
    Zs, names, index = [], [], {}
    for r in random:
        Zr, lv = _design(df[r])
        Zs.append(Zr)
        names.append(r)
        index[r] = {lvl: i for i, lvl in enumerate(lv)}
    offsets = np.cumsum([0] + [z.shape[1] for z in Zs])
    for r, off in zip(names, offsets[:-1], strict=False):
        index[r] = {k: v + int(off) for k, v in index[r].items()}
    Z = np.hstack(Zs)
    q_sizes = [z.shape[1] for z in Zs]
    m = df[meas_var].to_numpy(dtype=float) if meas_var else np.zeros(n)
    m = np.nan_to_num(m, nan=np.nanmedian(m) if np.isfinite(m).any() else 0.0)
    W = np.hstack([X, Z])
    p = X.shape[1]
    q = Z.shape[1]
    var_y = float(np.var(yv)) or 1.0

    def build(theta):
        s2 = np.exp(theta)
        s2_e, s2_r = s2[0], s2[1:]
        rinv = 1.0 / (s2_e + m)
        C = (W.T * rinv) @ W
        ginv = np.concatenate([np.full(k, 1.0 / v) for k, v in zip(q_sizes, s2_r, strict=True)])
        C[p:, p:] += np.diag(ginv)
        rhs = (W.T * rinv) @ yv
        return s2_e, s2_r, rinv, C, rhs

    def negloglik(theta):
        s2_e, s2_r, rinv, C, rhs = build(theta)
        try:
            L = linalg.cholesky(C, lower=True)
        except linalg.LinAlgError:
            return 1e12
        sol = linalg.cho_solve((L, True), rhs)
        logdetC = 2.0 * np.sum(np.log(np.diag(L)))
        logdetR = float(np.sum(np.log(s2_e + m)))
        logdetG = float(np.sum([k * np.log(v) for k, v in zip(q_sizes, s2_r, strict=True)]))
        quad = float(yv @ (rinv * yv) - sol @ rhs)
        return 0.5 * (logdetR + logdetG + logdetC + quad)

    theta0 = np.log(np.array([var_y / 2] + [var_y / (2 * len(random))] * len(random)))
    if init:
        theta0 = np.log(np.array([init.get("residual", var_y / 2)] + [init.get(r, var_y / 4) for r in random]))
    bounds = [(np.log(var_y * 1e-6), np.log(var_y * 10))] * (1 + len(random))
    res = optimize.minimize(negloglik, theta0, method="L-BFGS-B", bounds=bounds)
    s2_e, s2_r, rinv, C, rhs = build(res.x)
    L = linalg.cholesky(C, lower=True)
    sol = linalg.cho_solve((L, True), rhs)
    Cinv = linalg.cho_solve((L, True), np.eye(p + q))
    effects = {}
    for r, off, k in zip(names, offsets[:-1], q_sizes, strict=True):
        lv = sorted(index[r], key=lambda x: index[r][x])
        sl = slice(p + int(off), p + int(off) + k)
        effects[r] = pd.DataFrame({"level": lv, "estimate": sol[sl], "pev": np.diag(Cinv)[sl]})
    # store random-effect indices relative to the start of the random block
    rel_index = {r: {k2: v - 0 for k2, v in index[r].items()} for r in names}
    return MixedModelResult(
        fixed=pd.Series(sol[:p], index=fixed_names), effects=effects,
        variances={"residual": float(s2_e), **{r: float(v) for r, v in zip(names, s2_r, strict=True)}},
        loglik=float(-res.fun), n_obs=n, converged=bool(res.success), cov_inv=Cinv, index=rel_index, p=p,
    )


def empirical_bayes(estimates: np.ndarray, variances: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Normal-normal shrinkage of independent estimates towards zero.

    tau^2 is estimated by the method of moments (DerSimonian-Laird style) and floored at 0.
    Returns (posterior means, posterior variances, tau^2).
    """
    est = np.asarray(estimates, dtype=float)
    var = np.asarray(variances, dtype=float)
    ok = np.isfinite(est) & np.isfinite(var) & (var > 0)
    if ok.sum() < 3:
        return np.zeros_like(est), np.full_like(est, np.nan), 0.0
    w = 1.0 / var[ok]
    mean_w = np.sum(w * est[ok]) / np.sum(w)
    qstat = np.sum(w * (est[ok] - mean_w) ** 2)
    df_ = ok.sum() - 1
    denom = np.sum(w) - np.sum(w**2) / np.sum(w)
    tau2 = max(0.0, (qstat - df_) / denom) if denom > 0 else 0.0
    shrink = tau2 / (tau2 + var)
    post_mean = shrink * est
    post_var = shrink * var
    post_mean[~ok] = 0.0
    post_var[~ok] = tau2
    return post_mean, post_var, tau2
