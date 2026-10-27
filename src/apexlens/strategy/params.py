"""Strategy parameters for one race, estimated only from data available before that race.

Everything is measured, nothing is assumed:

* degradation per dry compound — fuel-corrected stint slopes (Model C), pooled with precision and recency
  weights (half-life one season) and shrunk towards the pool at the circuit, as validated in Model C;
* compound pace offsets — differences between a driver's stints on different compounds in the same race,
  compared at a tyre age every stint actually ran (``REF_AGE`` laps; extrapolating to age 0 was unstable
  across seasons), shrunk towards the pool at the circuit;
* pit-stop time loss — green-flag in-lap + out-lap minus twice the driver's median clean lap, per circuit;
* tyre life — 90th percentile of race stint length as a share of race distance, per compound;
* fuel / track-evolution trend, lap-1 loss and safety-car frequencies from earlier races.

The cut-off is the race start: earlier events plus, on sprint weekends, the same weekend's sprint.
Track temperature is not used for degradation: within-circuit temperature adjustments made held-out stint
predictions worse (see ``tyre_model.temperature_betas`` and ``evaluation_runs/tyre_degradation.json``).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

from apexlens.strategy.data import DRY, StrategyData
from apexlens.strategy.rules import rules_for

RECENCY_HALF_LIFE_SEASONS = 1.0
CIRCUIT_PRIOR_STINTS = 20        # as in Model C
CIRCUIT_PRIOR_PAIRS = 10         # driver-races with two compounds, for compound offsets
CIRCUIT_PRIOR_STOPS = 10
CIRCUIT_PRIOR_RACES = 4
STINT_LIFE_QUANTILE = 0.9
MIN_STINT_LAPS = 5
REF_AGE = 8                      # compound offsets are pace differences at this tyre age
FALLBACK_REF_LAP_S = 90.0


@dataclass
class StrategyParams:
    circuit_id: str
    season: int
    cutoff: str
    laps: int
    ref_lap_s: float
    ref_source: str
    slope_pct: dict[str, float]
    offset_pct: dict[str, float]     # pace at REF_AGE laps of tyre age, relative to MEDIUM
    pit_loss_s: float
    max_stint: dict[str, int]
    min_stint: int
    start_age: float
    fuel_pct_per_lap: float
    lap1_delta_pct: float
    start_share: dict[str, float]    # share of cars starting a dry race on each compound (tie-break only)
    sc_prob: float
    vsc_prob: float
    red_prob: float
    min_stops: int = 1
    rule_notes: list = field(default_factory=list)
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def _session_weights(sessions: np.ndarray, rng: np.random.Generator | None) -> dict:
    """Cluster bootstrap: how often each session is drawn (1 for every session without bootstrap)."""
    uniq = np.unique(sessions)
    if rng is None or len(uniq) == 0:
        return dict.fromkeys(uniq, 1.0)
    draws = rng.choice(uniq, size=len(uniq), replace=True)
    counts = pd.Series(draws).value_counts()
    return {s: float(counts.get(s, 0)) for s in uniq}


def _shrink(local: float, n: float, pooled: float, prior: float) -> float:
    if not np.isfinite(local) or n <= 0:
        return pooled
    return float((n * local + prior * pooled) / (n + prior))


def degradation(st: pd.DataFrame, circuit_id: str, season: int) -> tuple[dict, dict]:
    rec = 0.5 ** ((season - st["season"]).clip(lower=0) / RECENCY_HALF_LIFE_SEASONS)
    w = st["w"] * rec / np.maximum(st["slope_se"], 0.01) ** 2
    slopes, ev = {}, {}
    for c in DRY:
        m = (st["compound"] == c).to_numpy()
        pooled = float(np.sum(w[m] * st["slope_pct"][m]) / np.sum(w[m])) if np.sum(w[m]) > 0 else np.nan
        here = m & (st["circuit_id"] == circuit_id).to_numpy() & (st["w"] > 0).to_numpy()
        n = float(st["w"][here].sum())
        local = float(np.average(st["slope_pct"][here], weights=st["w"][here])) if n > 0 else np.nan
        slopes[c] = _shrink(local, n, pooled, CIRCUIT_PRIOR_STINTS)
        ev[c] = {"stints_at_circuit": int(here.sum()), "stints_total": int(m.sum())}
    known = [v for v in slopes.values() if np.isfinite(v)]
    for c in DRY:  # a compound never seen before the cut-off borrows the mean of the others
        if not np.isfinite(slopes[c]):
            slopes[c] = float(np.mean(known)) if known else 0.0
    return slopes, ev


def _within_offsets(d: pd.DataFrame) -> tuple[dict, int]:
    """Compound pace differences at ``REF_AGE`` within driver-races (fuel-corrected), MEDIUM = 0."""
    if d.empty:
        return {}, 0
    d = d[(d["age_min"] <= REF_AGE) & (d["age_max"] >= REF_AGE)].assign(
        level_at_age0=lambda x: x["level_at_age0"] + x["slope_pct"] * REF_AGE)
    d = d[d.groupby("grp")["compound"].transform("nunique") >= 2]
    if d.empty:
        return {}, 0
    X = pd.DataFrame({c: (d["compound"] == c).astype(float) for c in ("SOFT", "HARD")}, index=d.index)
    Xw = X - X.groupby(d["grp"]).transform("mean")
    yw = d["level_at_age0"] - d.groupby("grp")["level_at_age0"].transform("mean")
    w = d["wt"].to_numpy()
    A = (Xw.to_numpy() * w[:, None]).T @ Xw.to_numpy() + 1e-6 * np.eye(2)
    b = (Xw.to_numpy() * w[:, None]).T @ yw.to_numpy()
    sol = np.linalg.solve(A, b)
    out = {"MEDIUM": 0.0}
    for i, c in enumerate(("SOFT", "HARD")):
        if X[c].sum() > 0:
            out[c] = float(sol[i])
    return out, int(d["grp"].nunique())


def offsets(st: pd.DataFrame, circuit_id: str, season: int) -> tuple[dict, dict]:
    d = st.assign(grp=st["session_id"] + "|" + st["driver_id"],
                  wt=st["w"] * 0.5 ** ((season - st["season"]).clip(lower=0) / RECENCY_HALF_LIFE_SEASONS))
    d = d[d["wt"] > 0]
    pooled, n_pool = _within_offsets(d)
    local, n_loc = _within_offsets(d[d["circuit_id"] == circuit_id])
    out = {}
    for c in DRY:
        p = pooled.get(c, 0.0)
        out[c] = _shrink(local.get(c, np.nan), n_loc if c in local else 0, p, CIRCUIT_PRIOR_PAIRS)
    return out, {"driver_races_at_circuit": n_loc, "driver_races_total": n_pool}


def tyre_life(data: StrategyData, circuit_id: str, before: pd.Timestamp, laps: int) -> tuple[dict, dict]:
    dry_races = set(data.races.loc[~data.races["wet"] & ~data.races["red"], "event_id"])
    s = data.stints[(data.stints["date"] < before) & data.stints["compound"].isin(DRY)
                    & data.stints["event_id"].isin(dry_races)].copy()
    s["frac"] = s["n_laps"] / s["event_id"].map(data.events["laps"]).astype(float)
    out, ev = {}, {}
    for c in DRY:
        g = s[s["compound"] == c]
        here = g[g["circuit_id"] == circuit_id]
        src = here if len(here) >= 8 else g
        q = float(src["frac"].quantile(STINT_LIFE_QUANTILE)) if len(src) else 0.6
        out[c] = int(np.clip(round(q * laps), MIN_STINT_LAPS + 1, laps))
        ev[c] = {"stints": int(len(src)), "circuit_specific": bool(len(here) >= 8)}
    return out, ev


def start_shares(data: StrategyData, circuit_id: str, before: pd.Timestamp) -> dict:
    dry_races = set(data.races.loc[~data.races["wet"], "event_id"])
    first = data.stints[(data.stints["date"] < before) & (data.stints["stint"] == 1) & data.stints["event_id"].isin(dry_races)
                        & data.stints["compound"].isin(DRY)]
    glob = first["compound"].value_counts(normalize=True)
    here = first[first["circuit_id"] == circuit_id]
    loc = here["compound"].value_counts(normalize=True)
    return {c: _shrink(float(loc.get(c, 0.0)) if len(here) else np.nan, len(here), float(glob.get(c, 1 / 3)), 20) for c in DRY}


def estimate_params(data: StrategyData, circuit_id: str, race_date: pd.Timestamp, season: int, laps: int,
                    event_id: str | None = None, rng: np.random.Generator | None = None) -> StrategyParams:
    """Parameters for a race at ``circuit_id`` on ``race_date``; ``rng`` draws one cluster-bootstrap replicate."""
    race_date = pd.Timestamp(race_date)
    st = data.stint_slopes
    allowed = (st["date"] < race_date) | ((st["event_id"] == event_id) & (st["session_code"] == "S"))
    st = st[allowed].copy()
    if "circuit_id" not in st:
        st["circuit_id"] = st["event_id"].map(data.events["circuit_id"])
    sw = _session_weights(st["session_id"].to_numpy(), rng)
    st["w"] = st["session_id"].map(sw).astype(float)
    slopes, ev_slopes = degradation(st, circuit_id, season)
    offs, ev_offs = offsets(st, circuit_id, season)

    races = data.races[data.races["date"] < race_date]
    here = races[races["circuit_id"] == circuit_id]

    stops = data.pit_stops[data.pit_stops["date"] < race_date]
    pw = _session_weights(stops["session_id"].to_numpy(), rng)
    stops = stops.loc[stops.index.repeat(stops["session_id"].map(pw).astype(int))]
    glob_loss = float(stops["loss_s"].median()) if len(stops) else 22.0
    sh = stops[stops["circuit_id"] == circuit_id]
    pit_loss = _shrink(float(sh["loss_s"].median()) if len(sh) else np.nan, len(sh), glob_loss, CIRCUIT_PRIOR_STOPS)

    life, ev_life = tyre_life(data, circuit_id, race_date, laps)

    fuel_all = races["fuel_slope"].dropna()
    fuel_here = here["fuel_slope"].dropna()
    fuel = _shrink(float(fuel_here.median()) if len(fuel_here) else np.nan, len(fuel_here),
                   float(fuel_all.median()) if len(fuel_all) else -0.05, 3)

    lap1 = data.laps[(data.laps["session_code"] == "R") & (data.laps["lap_number"] == 1) & (data.laps["date"] < race_date)
                     & data.laps["compound"].isin(DRY) & (data.laps["exclusion_reason"] == "race_start_lap")]
    d1 = (lap1["lap_time_s"] / lap1["drv_session_median_s"] - 1) * 100
    d1_here = d1[lap1["circuit_id"] == circuit_id]
    lap1_delta = float(d1_here.median()) if d1_here.notna().sum() >= 5 else float(d1.median()) if d1.notna().any() else 5.0

    def prob(col: str) -> float:
        g = float(races[col].mean()) if len(races) else 0.5
        return _shrink(float(here[col].mean()) if len(here) else np.nan, len(here), g, CIRCUIT_PRIOR_RACES)

    ref, ref_src = _reference_lap(data, races, here, event_id)
    rule = rules_for(event_id)
    if "max_stint_laps" in rule:
        life = {c: min(v, rule["max_stint_laps"]) for c, v in life.items()}
    return StrategyParams(
        circuit_id=circuit_id, season=int(season), cutoff=str(race_date.date()), laps=int(laps),
        ref_lap_s=ref, ref_source=ref_src, slope_pct=slopes, offset_pct=offs, pit_loss_s=pit_loss, max_stint=life,
        min_stint=MIN_STINT_LAPS, start_age=data.start_tyre_age, fuel_pct_per_lap=fuel, lap1_delta_pct=lap1_delta,
        start_share=start_shares(data, circuit_id, race_date),
        sc_prob=prob("sc"), vsc_prob=prob("vsc"), red_prob=prob("red"),
        min_stops=int(rule.get("min_stops", 1)), rule_notes=[rule["note"]] if rule else [],
        evidence={"races_at_circuit": int(len(here)), "races_total": int(len(races)), "pit_stops_at_circuit": int(len(sh)),
                  "degradation": ev_slopes, "compound_offsets": ev_offs, "tyre_life": ev_life,
                  "same_weekend_sprint_used": bool(((data.stint_slopes["event_id"] == event_id)
                                                    & (data.stint_slopes["session_code"] == "S")).any())
                  if event_id else False},
    )


def _reference_lap(data: StrategyData, races: pd.DataFrame, here: pd.DataFrame, event_id: str | None) -> tuple[float, str]:
    """Typical race lap in seconds (only used to convert % effects to seconds)."""
    q = data.quali_refs.get(event_id) if event_id else None
    ratio = (races["ref_s"] / races["q_ref_s"]).dropna()
    ratio_here = (here["ref_s"] / here["q_ref_s"]).dropna()
    if q is not None and np.isfinite(q) and len(ratio):
        r = float(ratio_here.median()) if len(ratio_here) else float(ratio.median())
        return float(q * r), "this weekend's qualifying laps x the historical race/qualifying lap ratio"
    if len(here):
        return float(here["ref_s"].median()), "median race lap at this circuit in earlier races"
    return FALLBACK_REF_LAP_S, "no lap times at this circuit yet: nominal 90 s lap"
