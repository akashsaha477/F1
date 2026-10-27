"""What actually happened in a past race: strategies, pit laps, results and disruptions."""

from __future__ import annotations

import numpy as np
import pandas as pd

from apexlens.strategy.calibration import plan_key
from apexlens.strategy.data import DRY, StrategyData
from apexlens.strategy.optimizer import label


def driver_strategy(data: StrategyData, event_id: str, driver_id: str) -> dict | None:
    s = data.stints[(data.stints["event_id"] == event_id) & (data.stints["driver_id"] == driver_id)].sort_values("stint")
    if s.empty:
        return None
    seq = [str(c) for c in s["compound"]]
    pit_laps = [int(x) for x in s["end_lap"].iloc[:-1]]
    known = all(c in DRY for c in seq)
    return {"sequence": seq, "label": label(tuple(seq)) if known and len(seq) > 1 else " - ".join(seq),
            "stops": len(seq) - 1, "pit_laps": pit_laps, "stint_laps": [int(x) for x in s["n_laps"]],
            "start_tyre_age": float(s["tyre_life_start"].iloc[0]) if pd.notna(s["tyre_life_start"].iloc[0]) else None,
            "dry_only": known}


def classified(data: StrategyData, event_id: str) -> pd.DataFrame:
    r = data.results[data.results["event_id"] == event_id].copy()
    r["position"] = pd.to_numeric(r["position"], errors="coerce")
    r["grid_position"] = pd.to_numeric(r["grid_position"], errors="coerce")
    return r.sort_values("position")


def race_summary(data: StrategyData, event_id: str, top_n: int = 10) -> dict | None:
    races = data.races.set_index("event_id")
    if event_id not in races.index:
        return None
    facts = races.loc[event_id]
    res = classified(data, event_id)
    fin = res[res["position"].notna()]
    top = []
    for r in fin.head(top_n).itertuples():
        st = driver_strategy(data, event_id, r.driver_id)
        if st:
            top.append({"position": int(r.position), "driver_id": r.driver_id, "constructor_id": r.constructor_id, **st})
    dry_top = [t for t in top if t["dry_only"]]
    stops = [t["stops"] for t in dry_top]
    modal_stops = int(pd.Series(stops).mode().min()) if stops else None
    starts = [t["sequence"][0] for t in dry_top]
    modal_start = str(pd.Series(starts).mode().iloc[0]) if starts else None
    first_stops = [t["pit_laps"][0] for t in dry_top if t["stops"] == modal_stops and t["pit_laps"]]
    keys = [plan_key(t["stops"], t["sequence"]) for t in dry_top]
    modal_key = str(pd.Series(keys).mode().iloc[0]) if keys else None
    return {
        "event_id": event_id, "laps": int(facts["laps_run"]), "safety_car": bool(facts["sc"]),
        "virtual_safety_car": bool(facts["vsc"]), "red_flag": bool(facts["red"]), "wet": bool(facts["wet"]),
        "winner": top[0] if top else None, "top": top,
        "top_modal_stops": modal_stops, "top_modal_start": modal_start, "top_modal_plan": modal_key,
        "top_first_stop_median": float(np.median(first_stops)) if first_stops else None,
        "top_first_stop_laps": first_stops,
    }


def driver_laps(data: StrategyData, event_id: str, driver_id: str) -> list[dict]:
    lap = data.laps[(data.laps["session_id"] == f"{event_id}-R") & (data.laps["driver_id"] == driver_id)]
    return [{"lap": int(r.lap_number), "lap_time_s": float(r.lap_time_s) if pd.notna(r.lap_time_s) else None,
             "compound": r.compound, "clean": bool(r.is_clean), "reason": r.exclusion_reason}
            for r in lap.itertuples()]


def driver_result(data: StrategyData, event_id: str, driver_id: str) -> dict | None:
    r = classified(data, event_id)
    r = r[r["driver_id"] == driver_id]
    if r.empty:
        return None
    x = r.iloc[0]
    return {"position": int(x["position"]) if pd.notna(x["position"]) else None, "position_text": x["position_text"],
            "grid": int(x["grid_position"]) if pd.notna(x["grid_position"]) else None,
            "time_s": float(x["time_s"]) if pd.notna(x["time_s"]) else None, "outcome": x["outcome_category"],
            "reason_retired": x["reason_retired"]}
