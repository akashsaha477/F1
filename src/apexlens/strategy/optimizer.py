"""Exact strategy optimisation for a dry race.

Race time is decomposed into a part every strategy shares (base pace, fuel burn, lap 1) and a part that
depends on the strategy: per lap ``offset[c] + slope[c] * (age - REF_AGE)`` (% of the reference lap) plus
the pit-stop loss. For a given compound sequence the best pit laps are found exactly with a min-plus
dynamic programme over stint lengths; every sequence of 1–3 stops that uses at least two dry compounds
(the sporting rule for dry races) is evaluated. Pit windows are the laps at which a stop still gives a
race time within ``window_s`` of that plan's optimum (forward/backward pass of the same programme).
"""

from __future__ import annotations

import itertools

import numpy as np

from apexlens.strategy.data import DRY
from apexlens.strategy.params import REF_AGE, StrategyParams

ABBR = {"SOFT": "S", "MEDIUM": "M", "HARD": "H"}


def label(seq: tuple[str, ...]) -> str:
    stops = len(seq) - 1
    return f"{'-'.join(ABBR[c] for c in seq)} ({stops} stop{'s' if stops != 1 else ''})"


def sequences(max_stops: int) -> list[tuple[str, ...]]:
    out = []
    for stops in range(1, max_stops + 1):
        for seq in itertools.product(DRY, repeat=stops + 1):
            if len(set(seq)) >= 2:
                out.append(seq)
    return out


def stint_cost_s(p: StrategyParams, compound: str, first: bool) -> np.ndarray:
    """Seconds lost (vs. a MEDIUM tyre at REF_AGE) over a stint of L laps, for L = 0..N (inf if not allowed)."""
    n = p.laps
    L = np.arange(n + 1, dtype=float)
    a0 = p.start_age if first else 0.0
    # tyre age on the k-th lap of the stint (k = 0..L-1) is a0 + k + 1
    pct = L * (p.offset_pct[compound] - p.slope_pct[compound] * REF_AGE) + p.slope_pct[compound] * (L * a0 + L * (L + 1) / 2)
    cost = pct * p.ref_lap_s / 100.0
    ok = (p.min_stint <= L) & (p.max_stint[compound] >= L)
    return np.where(ok, cost, np.inf)


def _minplus(a: np.ndarray, f: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """out[t] = min_L a[t-L] + f[L] and the minimising L."""
    n = len(a) - 1
    t = np.arange(n + 1)[:, None]
    L = np.arange(n + 1)[None, :]
    idx = t - L
    vals = np.where(idx >= 0, a[np.clip(idx, 0, n)] + f[L], np.inf)
    arg = np.argmin(vals, axis=1)
    return vals[np.arange(n + 1), arg], arg


def _backward(costs: list[np.ndarray], n: int) -> list[np.ndarray]:
    """G[k][t]: best cost of stints k.. covering laps t+1..n."""
    m = len(costs)
    G = [None] * m
    t = np.arange(n + 1)
    G[m - 1] = costs[m - 1][n - t]
    for k in range(m - 2, -1, -1):
        Lg = np.arange(n + 1)[None, :]
        nxt = t[:, None] + Lg
        vals = np.where(nxt <= n, costs[k][Lg] + G[k + 1][np.clip(nxt, 0, n)], np.inf)
        G[k] = vals.min(axis=1)
    return G


def optimise_sequence(p: StrategyParams, seq: tuple[str, ...], window_s: float) -> dict | None:
    n = p.laps
    costs = [stint_cost_s(p, c, i == 0) for i, c in enumerate(seq)]
    F, args = [costs[0]], []
    for k in range(1, len(seq)):
        f, a = _minplus(F[-1], costs[k])
        F.append(f)
        args.append(a)
    total = F[-1][n]
    if not np.isfinite(total):
        return None
    lengths, t = [], n
    for k in range(len(seq) - 1, 0, -1):
        L = int(args[k - 1][t])
        lengths.append(L)
        t -= L
    lengths.append(t)
    lengths = lengths[::-1]
    pit_laps = [int(x) for x in np.cumsum(lengths)[:-1]]
    stops = len(seq) - 1
    total_s = float(total + stops * p.pit_loss_s)
    G = _backward(costs, n)
    windows = []
    for k in range(1, len(seq)):
        through = F[k - 1] + G[k]
        ok = np.flatnonzero(through <= total + window_s)
        windows.append({"stop": k, "best_lap": pit_laps[k - 1], "from_lap": int(ok.min()), "to_lap": int(ok.max())})
    return {"sequence": list(seq), "label": label(seq), "stops": stops, "stint_laps": lengths, "pit_laps": pit_laps,
            "strategy_cost_s": total_s, "pit_windows": windows}


def optimise(p: StrategyParams, max_stops: int = 3, window_s: float = 2.0) -> list[dict]:
    """Best plan per compound combination, ranked by strategy-dependent race time.

    The cost model does not depend on the order of the stints (fuel burn affects every strategy alike), so
    orderings of the same tyres tie. One plan is kept per combination: the ordering whose first compound
    teams have most often started this race on; the other orderings are listed with it.
    """
    seqs = [s for s in sequences(max(max_stops, p.min_stops)) if len(s) - 1 >= p.min_stops]
    plans = [r for seq in seqs if (r := optimise_sequence(p, seq, window_s)) is not None]
    groups: dict[tuple, list[dict]] = {}
    for r in plans:
        groups.setdefault((r["stops"], tuple(sorted(r["sequence"]))), []).append(r)
    kept = []
    for members in groups.values():
        low = min(m["strategy_cost_s"] for m in members)
        tied = [m for m in members if m["strategy_cost_s"] <= low + 0.05]
        tied.sort(key=lambda m: (-p.start_share.get(m["sequence"][0], 0.0), m["strategy_cost_s"]))
        best = dict(tied[0])
        best["equivalent_orders"] = [m["label"] for m in tied[1:]]
        kept.append(best)
    kept.sort(key=lambda r: r["strategy_cost_s"])
    if kept:
        top = kept[0]["strategy_cost_s"]
        for r in kept:
            r["delta_s"] = r["strategy_cost_s"] - top
    return kept


def robustness(param_draws: list[StrategyParams], max_stops: int = 3) -> dict:
    """How often each sequence is optimal when the parameters are re-estimated on bootstrap resamples."""
    winners, first_stop = [], []
    for q in param_draws:
        plans = optimise(q, max_stops=max_stops)
        if plans:
            winners.append(plans[0]["label"])
            first_stop.append(plans[0]["pit_laps"][0])
    if not winners:
        return {"n": 0}
    labels, counts = np.unique(winners, return_counts=True)
    order = np.argsort(-counts)
    return {"n": len(winners),
            "best_share": [{"label": str(labels[i]), "share": float(counts[i] / len(winners))} for i in order],
            "first_stop_lap": {"p10": float(np.quantile(first_stop, 0.1)), "median": float(np.median(first_stop)),
                               "p90": float(np.quantile(first_stop, 0.9))}}


def lap_trace(p: StrategyParams, seq: list[str], stint_laps: list[int], base_pct: float = 0.0) -> list[dict]:
    """Lap-by-lap expected lap time for a plan. ``base_pct`` is the driver/car pace on MEDIUM at REF_AGE, mid-race."""
    rows, lap = [], 0
    mid = (p.laps + 1) / 2
    for i, (c, L) in enumerate(zip(seq, stint_laps, strict=True)):
        a0 = p.start_age if i == 0 else 0.0
        for k in range(L):
            lap += 1
            age = a0 + k + 1
            pct = (base_pct + p.offset_pct[c] + p.slope_pct[c] * (age - REF_AGE)
                   + p.fuel_pct_per_lap * (lap - mid) + (p.lap1_delta_pct if lap == 1 else 0.0))
            t = p.ref_lap_s * (1 + pct / 100)
            pit = None
            if k == L - 1 and i < len(seq) - 1:
                t += p.pit_loss_s / 2
                pit = "in"
            elif k == 0 and i > 0:
                t += p.pit_loss_s / 2
                pit = "out"
            rows.append({"lap": lap, "compound": c, "stint": i + 1, "tyre_age": age, "lap_time_s": float(t), "pit": pit})
    return rows
