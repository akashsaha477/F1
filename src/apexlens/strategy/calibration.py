"""Calibration of the strategy cost to teams' revealed choices.

Lap times do not show everything that makes a strategy expensive: losing track position (and time in
traffic) after a stop, or that few new SOFT sets are left after qualifying and SOFTs grain or overheat
on long runs. Both are modelled as constant extra costs — seconds per pit stop and per SOFT stint —
which leave each plan's best pit laps unchanged and only re-rank compound sequences.

The two costs are chosen on *earlier* races only (grid search) to maximise agreement with the strategy
most often used by the top-10 finishers: half credit for the stop count, half for the set of compounds.
Ties go to the smallest costs. The backtest reports the planner with and without this calibration.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

GRID_S = np.arange(0.0, 30.01, 2.5)


def plan_key(stops: int, sequence) -> str:
    return f"{int(stops)}|{'+'.join(sorted(set(sequence)))}"


def apply(plans: list[dict], cal: dict | None) -> list[dict]:
    """Re-rank plans with the calibrated extra costs (adds ``calibrated_cost_s``; keeps the physical cost)."""
    stop_s = (cal or {}).get("stop_s", 0.0)
    soft_s = (cal or {}).get("soft_stint_s", 0.0)
    out = []
    for p in plans:
        q = dict(p)
        q["calibration_cost_s"] = stop_s * p["stops"] + soft_s * sum(c == "SOFT" for c in p["sequence"])
        q["calibrated_cost_s"] = p["strategy_cost_s"] + q["calibration_cost_s"]
        out.append(q)
    out.sort(key=lambda r: r["calibrated_cost_s"])
    if out:
        top = out[0]["calibrated_cost_s"]
        for r in out:
            r["delta_s"] = r["calibrated_cost_s"] - top
    return out


def candidate_table(event_id: str, plans: list[dict]) -> pd.DataFrame:
    return pd.DataFrame([{"event_id": event_id, "stops": p["stops"], "n_soft": sum(c == "SOFT" for c in p["sequence"]),
                          "key": plan_key(p["stops"], p["sequence"]), "cost_s": p["strategy_cost_s"]} for p in plans])


def fit(candidates: pd.DataFrame, targets: pd.DataFrame) -> dict:
    """``candidates``: event_id, stops, n_soft, key, cost_s; ``targets``: event_id, actual_stops, actual_key."""
    ev = candidates.merge(targets, on="event_id")
    if ev.empty:
        return {"stop_s": 0.0, "soft_stint_s": 0.0, "races": 0, "agreement": None}
    groups = [(g["cost_s"].to_numpy(), g["stops"].to_numpy(), g["n_soft"].to_numpy(), g["key"].to_numpy(),
               g["actual_stops"].iloc[0], g["actual_key"].iloc[0]) for _, g in ev.groupby("event_id")]
    best = (-1.0, 0.0, 0.0)
    for stop_s in GRID_S:
        for soft_s in GRID_S:
            score = 0.0
            for cost, stops, n_soft, key, a_stops, a_key in groups:
                i = int(np.argmin(cost + stop_s * stops + soft_s * n_soft))
                score += 0.5 * (stops[i] == a_stops) + 0.5 * (key[i] == a_key)
            score /= len(groups)
            if score > best[0] + 1e-12:
                best = (score, float(stop_s), float(soft_s))
    return {"stop_s": best[1], "soft_stint_s": best[2], "races": len(groups), "agreement": best[0]}
