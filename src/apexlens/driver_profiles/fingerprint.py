"""Driver performance fingerprints (Phase 3).

Stage 2 decomposes condition-adjusted race pace (stage 1, :mod:`session_adjust`) into

    adj_pace = event effect (fixed) + driver + driver-season + team-season + residual

with crossed random effects fitted by REML (:mod:`mixed_model`). The driver's *team-adjusted pace*
for a season is driver + driver-season; its uncertainty is the prediction-error variance from the
mixed-model equations.

Identification caveat (shown to users): within a team-season only the *difference* between
team-mates is identified by the data. How the team-season mean is split between "car" and "drivers"
relies on drivers who changed teams across seasons and on the estimated variance components, so
cross-team comparisons are weaker than team-mate comparisons.

Condition-specific dimensions (wet races, wet qualifying, street circuits) are residual deviations
from the dry model, averaged per driver and shrunk towards zero by empirical Bayes. Sparse evidence
is reported as insufficient instead of being ranked.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from apexlens.driver_profiles.mixed_model import empirical_bayes, fit_mixed_model
from apexlens.driver_profiles.session_adjust import adjust_all
from apexlens.storage.io import read_table, write_json, write_table
from apexlens.storage.paths import DataPaths

log = logging.getLogger(__name__)

Z90 = 1.6449
MIN_EVENTS_FOR_RANK = 5
WET_MIN_SESSIONS, WET_MIN_LAPS = 2, 30
COND_MIN_SESSIONS = 3
QUALI_MAX_GAP = 5.0  # % — larger gaps are crashes, red flags or no-time runs, not pace
BOOT = 500


def _boot_ci(values: np.ndarray, stat=np.median, n: int = BOOT, seed: int = 0) -> tuple[float, float]:
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) < 3:
        return np.nan, np.nan
    rng = np.random.default_rng(seed)
    samples = [stat(rng.choice(v, size=len(v), replace=True)) for _ in range(n)]
    return float(np.quantile(samples, 0.05)), float(np.quantile(samples, 0.95))


def _percentile_lower_better(values: pd.Series) -> pd.Series:
    """Share of the reference group with a *worse* (higher) value, 0-100."""
    n = values.notna().sum()
    if n < 2:
        return pd.Series(np.nan, index=values.index)
    worse = values.rank(ascending=False, method="average") - 1
    return 100.0 * worse / (n - 1)


def _status(n_sessions: int, n_laps: int, post_mean: float, post_sd: float, min_sessions: int, min_laps: int) -> str:
    if n_sessions < min_sessions or n_laps < min_laps or not np.isfinite(post_sd):
        return "insufficient_evidence"
    if post_sd == 0 or abs(post_mean) <= Z90 * post_sd:  # tau = 0 means complete shrinkage
        return "not_distinguishable_from_zero"
    return "supported"


def quali_table(paths: DataPaths, seasons: list[int]) -> pd.DataFrame:
    q = read_table(paths.silver("qualifying_results"))
    q = q[q["season"].isin(seasons) & (q["session_code"] == "Q") & q["best_s"].notna()].copy()
    q["quali_gap_pct"] = 100.0 * (q["best_s"] / q.groupby("event_id")["best_s"].transform("min") - 1.0)
    laps = read_table(paths.silver("laps"), columns=["session_id", "session_code", "is_wet_compound"])
    laps = laps[laps["session_code"] == "Q"]
    wet = laps.groupby("session_id")["is_wet_compound"].mean()
    q["session_id"] = q["event_id"] + "-Q"
    q["wet_share"] = q["session_id"].map(wet)
    q["condition"] = np.where(q["wet_share"] > 0.5, "wet", np.where(q["wet_share"].isna(), "unknown", "dry"))
    tm = q.groupby(["event_id", "constructor_id"])["quali_gap_pct"].transform("sum")
    cnt = q.groupby(["event_id", "constructor_id"])["quali_gap_pct"].transform("count")
    q["quali_teammate_gap"] = np.where(cnt == 2, q["quali_gap_pct"] - (tm - q["quali_gap_pct"]), np.nan)
    return q


def fit_pace_model(adj: pd.DataFrame) -> tuple:
    dry = adj[adj["condition"] == "dry"].copy()
    dry["driver_season"] = dry["driver_id"] + ":" + dry["season"].astype(str)
    dry["team_season"] = dry["constructor_id"] + ":" + dry["season"].astype(str)
    dry["m"] = dry["se"] ** 2
    res = fit_mixed_model(dry, "adj_pace", random=["driver_id", "driver_season", "team_season"], fixed=["session_id"],
                          meas_var="m")
    fixed = res.fixed
    dry["fixed"] = fixed["intercept"] + dry["session_id"].map(
        {k.split("=", 1)[1]: v for k, v in fixed.items() if k.startswith("session_id=")}).fillna(0.0)
    eff = {b: res.effects[b].set_index("level")["estimate"] for b in res.effects}
    dry["u_driver"] = dry["driver_id"].map(eff["driver_id"]).fillna(0.0)
    dry["u_ds"] = dry["driver_season"].map(eff["driver_season"]).fillna(0.0)
    dry["u_ts"] = dry["team_season"].map(eff["team_season"]).fillna(0.0)
    dry["resid"] = dry["adj_pace"] - dry["fixed"] - dry["u_driver"] - dry["u_ds"] - dry["u_ts"]
    return res, dry


def fit_quali_model(q: pd.DataFrame):
    d = q[(q["condition"] == "dry") & (q["quali_gap_pct"] <= QUALI_MAX_GAP)].copy()
    d["driver_season"] = d["driver_id"] + ":" + d["season"].astype(str)
    d["team_season"] = d["constructor_id"] + ":" + d["season"].astype(str)
    res = fit_mixed_model(d, "quali_gap_pct", random=["driver_id", "driver_season", "team_season"], fixed=["event_id"])
    return res, d


def session_regression_residuals(df: pd.DataFrame, obs: str, exp: str, session: str = "session_id",
                                 min_n: int = 6) -> pd.DataFrame:
    """Per session, regress observed on dry-expected performance; residuals are condition-specific deviations.

    The slope absorbs the general widening of gaps in the wet (everyone's differences scale up), so a
    driver only shows a deviation when they beat or miss what their dry pace implies *in that session*.
    The residual variance of each session's fit is used as that session's noise level.
    """
    out = []
    for _sid, g in df.groupby(session):
        g = g.dropna(subset=[obs, exp])
        if len(g) < min_n:
            continue
        x = g[exp].to_numpy(dtype=float)
        y = g[obs].to_numpy(dtype=float)
        X = np.column_stack([np.ones_like(x), x])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ beta
        s2 = float(r @ r / max(len(r) - 2, 1))
        out.append(g.assign(dev=r, var=s2, slope=float(beta[1])))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=list(df.columns) + ["dev", "var", "slope"])


def condition_deviation(rows: pd.DataFrame, value: str, var: str, group: str = "driver_id") -> pd.DataFrame:
    """Per-driver mean deviation with its variance, then empirical-Bayes shrinkage across drivers."""
    g = rows.groupby(group)
    agg = pd.DataFrame({"raw": g[value].mean(), "raw_var": g[var].sum() / g.size() ** 2, "n_sessions": g["session_id"].nunique(),
                        "n_laps": g["n_laps"].sum() if "n_laps" in rows else g.size()}).reset_index()
    post, pvar, tau2 = empirical_bayes(agg["raw"].to_numpy(), agg["raw_var"].to_numpy())
    agg["posterior_mean"], agg["posterior_sd"], agg["tau"] = post, np.sqrt(pvar), np.sqrt(tau2)
    agg["raw_se"] = np.sqrt(agg["raw_var"])
    return agg.drop(columns="raw_var")


def build_profiles(paths: DataPaths) -> dict:
    laps = read_table(paths.gold("lap_features"))
    seasons = sorted(int(s) for s in laps["season"].unique())
    adj = adjust_all(laps)
    write_table(paths.gold("driver_session_adjusted"), adj)

    res, dry = fit_pace_model(adj)
    q = quali_table(paths, seasons)
    qres, qdry = fit_quali_model(q)

    # --- per driver-season core table ---------------------------------------------------------
    ds = dry.groupby(["driver_id", "season"]).agg(
        n_dry_races=("session_id", "nunique"), n_laps=("n_laps", "sum"), raw_adj_pace=("adj_pace", "mean"),
        main_team=("constructor_id", lambda s: s.value_counts().index[0]),
        teams=("constructor_id", lambda s: ",".join(sorted(set(s)))),
        consistency_sd=("resid_robust_sd", "median")).reset_index()
    rows = []
    for r in ds.itertuples():
        est, pev = res.combined([("driver_id", r.driver_id), ("driver_season", f"{r.driver_id}:{r.season}")])
        team_key = f"{r.main_team}:{r.season}"
        te = res.effects["team_season"].set_index("level")
        team_est = float(te.loc[team_key, "estimate"]) if team_key in te.index else np.nan
        team_sd = float(np.sqrt(te.loc[team_key, "pev"])) if team_key in te.index else np.nan
        sub = dry[(dry.driver_id == r.driver_id) & (dry.season == r.season)]
        tm = sub["teammate_gap"].dropna().to_numpy()
        cons = sub["resid_robust_sd"].to_numpy()
        qe, qpev = qres.combined([("driver_id", r.driver_id), ("driver_season", f"{r.driver_id}:{r.season}")])
        qs = q[(q.driver_id == r.driver_id) & (q.season == r.season)]
        qdry_ds = qs[(qs["condition"] == "dry") & (qs["quali_gap_pct"] <= QUALI_MAX_GAP)]
        tmq = qdry_ds["quali_teammate_gap"].dropna().to_numpy()
        rows.append({
            "driver_id": r.driver_id, "season": r.season, "main_team": r.main_team, "teams": r.teams,
            "n_dry_races": r.n_dry_races, "n_laps": r.n_laps,
            "race_pace_adj": est, "race_pace_adj_sd": float(np.sqrt(pev)),
            "race_pace_adj_lo": est - Z90 * np.sqrt(pev), "race_pace_adj_hi": est + Z90 * np.sqrt(pev),
            "race_pace_raw": r.raw_adj_pace, "team_effect": team_est, "team_effect_sd": team_sd,
            "teammate_gap_race": float(np.median(tm)) if len(tm) else np.nan,
            "teammate_gap_race_lo": _boot_ci(tm)[0], "teammate_gap_race_hi": _boot_ci(tm)[1], "n_teammate_races": int(len(tm)),
            "consistency_sd": float(np.median(cons)), "consistency_lo": _boot_ci(cons)[0], "consistency_hi": _boot_ci(cons)[1],
            "quali_adj": qe, "quali_adj_sd": float(np.sqrt(qpev)) if np.isfinite(qpev) else np.nan,
            "quali_gap_median": float(qdry_ds["quali_gap_pct"].median()) if len(qdry_ds) else np.nan,
            "quali_teammate_gap": float(np.median(tmq)) if len(tmq) else np.nan,
            "quali_teammate_gap_lo": _boot_ci(tmq)[0], "quali_teammate_gap_hi": _boot_ci(tmq)[1],
            "n_quali": int(len(qdry_ds)), "n_quali_teammate": int(len(tmq)),
        })
    prof = pd.DataFrame(rows)

    # --- racecraft and outcomes (reported separately from pace) --------------------------------
    rr = read_table(paths.silver("race_results"))
    rr = rr[rr["season"].isin(seasons) & (rr["session_code"] == "R")]
    lap1 = read_table(paths.silver("laps"), columns=["session_id", "season", "session_code", "driver_id", "lap_number", "position"])
    lap1 = lap1[(lap1["session_code"] == "R") & (lap1["lap_number"] == 1)].copy()
    lap1["event_id"] = lap1["session_id"].str[:-2]
    grid = read_table(paths.silver("starting_grids"))
    grid = grid[(grid["session_code"] == "R") & grid["position"].notna()][["event_id", "driver_id", "position"]].rename(
        columns={"position": "grid"})
    lap1 = lap1.merge(grid, on=["event_id", "driver_id"], how="inner")
    lap1["lap1_gain"] = lap1["grid"].astype(float) - lap1["position"].astype(float)
    l1 = lap1.groupby(["driver_id", "season"]).agg(lap1_gain_mean=("lap1_gain", "mean"), n_lap1=("lap1_gain", "count")).reset_index()
    fin = rr[rr["position"].notna() & rr["grid_position"].notna()].copy()
    fin["gain"] = fin["grid_position"].astype(float) - fin["position"].astype(float)
    gains = fin.groupby(["driver_id", "season"]).agg(positions_gained_mean=("gain", "mean"), n_classified=("gain", "count")).reset_index()
    outc = rr.pivot_table(index=["driver_id", "season"], columns="outcome_category", values="event_id", aggfunc="count",
                          fill_value=0).add_prefix("outcome_").reset_index()
    prof = prof.merge(l1, on=["driver_id", "season"], how="left").merge(gains, on=["driver_id", "season"], how="left") \
        .merge(outc, on=["driver_id", "season"], how="left")

    # --- percentiles within season among drivers with enough events --------------------------
    for col, out in [("race_pace_adj", "race_pace_adj_pctile"), ("consistency_sd", "consistency_pctile"),
                     ("quali_adj", "quali_adj_pctile")]:
        prof[out] = np.nan
        for _season, idx in prof.groupby("season").groups.items():
            sub = prof.loc[idx]
            ok = sub["n_dry_races"] >= MIN_EVENTS_FOR_RANK
            prof.loc[sub[ok].index, out] = _percentile_lower_better(sub.loc[ok, col]).to_numpy()
    prof["rank_reference"] = (f"drivers of the same season with >= {MIN_EVENTS_FOR_RANK} dry races "
                              "(percentile = share of that group with a worse value)")

    # --- condition-specific deviations ---------------------------------------------------------
    cond_rows = []
    wet = adj[adj["condition"] == "wet"].copy()
    if len(wet):
        u_d = res.effects["driver_id"].set_index("level")["estimate"]
        u_ds = res.effects["driver_season"].set_index("level")["estimate"]
        u_ts = res.effects["team_season"].set_index("level")["estimate"]
        wet["expected"] = (wet["driver_id"].map(u_d).fillna(0) + (wet["driver_id"] + ":" + wet["season"].astype(str)).map(u_ds).fillna(0)
                           + (wet["constructor_id"] + ":" + wet["season"].astype(str)).map(u_ts).fillna(0))
        wet = session_regression_residuals(wet, "adj_pace", "expected")
        w = condition_deviation(wet, "dev", "var")
        w["dimension"] = "wet_race"
        w["status"] = [_status(a, b, c, d, WET_MIN_SESSIONS, WET_MIN_LAPS) for a, b, c, d in
                       zip(w["n_sessions"], w["n_laps"], w["posterior_mean"], w["posterior_sd"], strict=True)]
        cond_rows.append(w)
    qwet = q[(q["condition"] == "wet") & q["quali_gap_pct"].notna()].copy()
    if len(qwet):
        qd = qres.effects["driver_id"].set_index("level")["estimate"]
        qds = qres.effects["driver_season"].set_index("level")["estimate"]
        qts = qres.effects["team_season"].set_index("level")["estimate"]
        qwet["expected"] = (qwet["driver_id"].map(qd).fillna(0) + (qwet["driver_id"] + ":" + qwet["season"].astype(str)).map(qds).fillna(0)
                            + (qwet["constructor_id"] + ":" + qwet["season"].astype(str)).map(qts).fillna(0))
        qwet = qwet[qwet["quali_gap_pct"] <= 3 * QUALI_MAX_GAP]
        qwet = session_regression_residuals(qwet, "quali_gap_pct", "expected")
        qwet["n_laps"] = 1
        wq = condition_deviation(qwet, "dev", "var")
        wq["dimension"] = "wet_qualifying"
        wq["status"] = [_status(a, a, c, d, WET_MIN_SESSIONS, WET_MIN_SESSIONS) for a, c, d in
                        zip(wq["n_sessions"], wq["posterior_mean"], wq["posterior_sd"], strict=True)]
        cond_rows.append(wq)
    circuits = read_table(paths.silver("circuits"))[["circuit_id", "type"]]
    d2 = dry.merge(circuits, on="circuit_id", how="left")
    d2["var"] = d2["se"] ** 2 + res.variances["residual"]
    dims = [("street_circuit", d2["type"] == "STREET")]
    cprof = read_table(paths.gold("circuit_profiles"))
    if len(cprof):
        d2 = d2.merge(cprof[["circuit_id", "circuit_frac_fast", "circuit_frac_slow"]], on="circuit_id", how="left")
        hi_fast = cprof["circuit_frac_fast"].quantile(2 / 3)
        hi_slow = cprof["circuit_frac_slow"].quantile(2 / 3)
        dims += [("high_speed_circuit", d2["circuit_frac_fast"] >= hi_fast),
                 ("slow_corner_circuit", d2["circuit_frac_slow"] >= hi_slow)]
    for dim, mask in dims:
        a = d2[mask]
        b = d2[~mask]
        da = condition_deviation(a, "resid", "var").set_index("driver_id")
        db = b.groupby("driver_id").agg(m=("resid", "mean"), v=("var", "sum"), n=("resid", "size"))
        both = da.join(db, how="inner")
        raw = both["raw"] - both["m"]
        rvar = both["raw_se"] ** 2 + both["v"] / both["n"] ** 2
        post, pvar, tau2 = empirical_bayes(raw.to_numpy(), rvar.to_numpy())
        out = pd.DataFrame({"driver_id": both.index, "raw": raw.to_numpy(), "raw_se": np.sqrt(rvar.to_numpy()),
                            "n_sessions": both["n_sessions"].to_numpy(), "n_laps": both["n_laps"].to_numpy(),
                            "posterior_mean": post, "posterior_sd": np.sqrt(pvar), "tau": np.sqrt(tau2), "dimension": dim})
        out["status"] = [_status(n, n * 10, c, d, COND_MIN_SESSIONS, 0) for n, c, d in
                         zip(out["n_sessions"], out["posterior_mean"], out["posterior_sd"], strict=True)]
        cond_rows.append(out)
    cond = pd.concat(cond_rows, ignore_index=True) if cond_rows else pd.DataFrame()
    if len(cond):
        cond["unit"] = np.where(cond["dimension"] == "wet_qualifying", "% gap to pole", "% of lap")
        cond["seasons"] = f"{seasons[0]}-{seasons[-1]}"

    meta = {
        "race_model": {"variances": res.variances, "n_obs": res.n_obs, "loglik": res.loglik, "converged": res.converged,
                       "formula": "adj_pace ~ session (fixed) + (1|driver) + (1|driver:season) + (1|team:season)"},
        "quali_model": {"variances": qres.variances, "n_obs": qres.n_obs, "loglik": qres.loglik, "converged": qres.converged,
                        "formula": f"quali_gap_pct ~ event (fixed) + (1|driver) + (1|driver:season) + (1|team:season); dry, gap <= {QUALI_MAX_GAP}%"},
        "seasons": seasons, "n_sessions_adjusted": int(adj["session_id"].nunique()),
        "condition_definitions": {
            "wet_race": "wet-tyre race sessions; per-session regression of adjusted pace on dry-model expectation",
            "wet_qualifying": "wet qualifying sessions; same regression on qualifying gap to pole",
            "street_circuit": "F1DB circuit type STREET vs all other dry races (model residuals)",
            "high_speed_circuit": "circuits in the top third of share of fast corners (>= 200 km/h minimum speed)",
            "slow_corner_circuit": "circuits in the top third of share of slow corners (< 125 km/h minimum speed)",
        },
        "stage1_adjustments": adj["adjusted_for"].value_counts().to_dict(),
        "thresholds": {"min_events_for_rank": MIN_EVENTS_FOR_RANK, "wet_min_sessions": WET_MIN_SESSIONS,
                       "wet_min_laps": WET_MIN_LAPS, "condition_min_sessions": COND_MIN_SESSIONS, "quali_max_gap": QUALI_MAX_GAP},
        "identification_note": (
            "Team-mate differences are directly identified. The split of a team-season's mean pace into car and driver "
            "components relies on drivers who changed teams and on the estimated variance components; cross-team "
            "driver comparisons are therefore less certain than the intervals of a single effect suggest."),
    }
    write_table(paths.gold("driver_profiles"), prof)
    write_table(paths.gold("driver_condition_effects"), cond)
    write_table(paths.gold("team_season_effects"), res.effects["team_season"])
    write_json(paths.gold("driver_profiles") / "meta.json", meta)
    log.info("profiles: %d driver-seasons, %d condition rows", len(prof), len(cond))
    return {"profiles": prof, "conditions": cond, "meta": meta, "adjusted": adj}
