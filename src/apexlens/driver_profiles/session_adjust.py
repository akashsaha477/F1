"""Stage 1: condition-adjusted driver pace within one session.

Per session, an OLS model of representative-lap relative pace on driver indicators, compound
offsets, compound-specific tyre-age slopes and lap number (fuel burn / track evolution) separates
each driver's pace from the tyres and race phase on which their laps happened. The driver
coefficient, evaluated at common reference conditions, is the *adjusted pace*.

Standard errors are inflated for within-stint autocorrelation with the AR(1) variance factor
sqrt((1 + rho) / (1 - rho)), rho estimated from consecutive residuals.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

REF_TYRE_AGE = 10.0
MIN_LAPS = 5
MIN_COMPOUND_LAPS = 10


def adjust_session(laps: pd.DataFrame) -> pd.DataFrame:
    """``laps``: representative laps of one session (rel_pace_pct, driver_id, compound, tyre_life_laps,
    lap_number, stint). Returns one row per driver with at least MIN_LAPS laps."""
    d = laps.dropna(subset=["rel_pace_pct", "tyre_life_laps", "lap_number"]).copy()
    comp_counts = d["compound"].value_counts()
    d = d[d["compound"].isin(comp_counts[comp_counts >= MIN_COMPOUND_LAPS].index)]
    counts = d["driver_id"].value_counts()
    d = d[d["driver_id"].isin(counts[counts >= MIN_LAPS].index)]
    if d["driver_id"].nunique() < 2:
        return pd.DataFrame()
    drivers = sorted(d["driver_id"].unique())
    comps = d["compound"].value_counts()
    ref_comp = comps.index[0]
    other = [c for c in comps.index if c != ref_comp]
    blocks: dict[str, tuple[list, list]] = {"driver": ([], []), "compound": ([], []), "age": ([], []), "lap": ([], [])}
    for drv in drivers:
        blocks["driver"][0].append((d["driver_id"] == drv).astype(float).to_numpy())
        blocks["driver"][1].append(f"drv:{drv}")
    for c in other:
        blocks["compound"][0].append((d["compound"] == c).astype(float).to_numpy())
        blocks["compound"][1].append(f"comp:{c}")
    for c in comps.index:
        blocks["age"][0].append(((d["compound"] == c) * d["tyre_life_laps"]).astype(float).to_numpy())
        blocks["age"][1].append(f"age:{c}")
    lap_c = d["lap_number"].astype(float).to_numpy()
    blocks["lap"][0].append(lap_c - float(np.median(lap_c)))
    blocks["lap"][1].append("lap")

    # Drop terms that cannot be identified from this session, in a fixed order, and record it:
    # no pit stops -> fuel and tyre-age trends coincide (keep tyre age); one compound per driver ->
    # compound offset coincides with driver pace (keep driver pace, which then includes tyre choice).
    adjusted_for = ["compound", "age", "lap"]
    for drop in [None, "lap", "compound"]:
        if drop:
            adjusted_for.remove(drop)
        use = ["driver"] + adjusted_for
        cols = [c for b in use for c in blocks[b][0]]
        names = [n for b in use for n in blocks[b][1]]
        X = np.column_stack(cols)
        if np.linalg.matrix_rank(X) == X.shape[1]:
            break
    else:
        return pd.DataFrame()  # driver effects not identifiable from this session's laps
    y = d["rel_pace_pct"].to_numpy(dtype=float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    dof = max(len(y) - np.linalg.matrix_rank(X), 1)
    s2 = float(resid @ resid / dof)
    xtx_inv = np.linalg.pinv(X.T @ X)
    # AR(1) inflation from consecutive residuals within driver-stints
    d = d.assign(_res=resid).sort_values(["driver_id", "stint", "lap_number"])
    prev = d.groupby(["driver_id", "stint"])["_res"].shift(1)
    m = prev.notna()
    rho = float(np.corrcoef(d.loc[m, "_res"], prev[m])[0, 1]) if m.sum() > 10 else 0.0
    rho = float(np.clip(np.nan_to_num(rho), 0.0, 0.8))
    infl = np.sqrt((1 + rho) / (1 - rho))
    coef = dict(zip(names, beta, strict=True))
    ref_shift = coef.get(f"age:{ref_comp}", 0.0) * REF_TYRE_AGE
    rows = []
    for i, drv in enumerate(drivers):
        r = d.loc[d["driver_id"] == drv, "_res"].to_numpy()
        rows.append({
            "driver_id": drv,
            "adj_pace": float(beta[i] + ref_shift),
            "se": float(np.sqrt(s2 * xtx_inv[i, i]) * infl),
            "n_laps": int(len(r)),
            "resid_robust_sd": float(1.4826 * np.median(np.abs(r - np.median(r)))),
            "ref_compound": ref_comp,
            "adjusted_for": "+".join(adjusted_for),
        })
    out = pd.DataFrame(rows)
    out["fuel_slope_pct_per_lap"] = coef.get("lap", np.nan)
    out["ar1_rho"] = rho
    for c in comps.index:
        out[f"deg_{c.lower()}_pct_per_lap"] = coef.get(f"age:{c}", np.nan)
    return out


def adjust_all(laps: pd.DataFrame, codes=("R", "S")) -> pd.DataFrame:
    """Run stage 1 on every race/sprint session; wet sessions use only wet-tyre laps."""
    rep = laps[laps["is_representative"] & laps["session_code"].isin(codes)]
    out = []
    for sid, g in rep.groupby("session_id"):
        wet_share = float(g["is_wet_compound"].astype(float).mean())
        condition = "wet" if wet_share > 0.5 else ("dry" if wet_share < 0.1 else "mixed")
        use = g[g["is_wet_compound"].astype(float) > 0.5] if condition == "wet" else g[g["is_wet_compound"].astype(float) < 0.5]
        res = adjust_session(use)
        if res.empty:
            continue
        meta = g.iloc[0]
        teams = use.groupby("driver_id")["constructor_id"].agg(lambda s: s.mode().iloc[0])
        res["constructor_id"] = res["driver_id"].map(teams)
        res = res.assign(session_id=sid, event_id=meta["event_id"], season=int(meta["season"]),
                         session_code=meta["session_code"], circuit_id=meta["circuit_id"], condition=condition,
                         wet_share=wet_share, date=meta.get("date"))
        out.append(res)
    df = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    if len(df):
        tm = df.groupby(["session_id", "constructor_id"])["adj_pace"].transform("sum")
        cnt = df.groupby(["session_id", "constructor_id"])["adj_pace"].transform("count")
        df["teammate_gap"] = np.where(cnt == 2, df["adj_pace"] - (tm - df["adj_pace"]), np.nan)
    return df
