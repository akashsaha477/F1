"""Local explanation payloads and deterministic narratives.

The narrative is generated from the payload only (no free text generation), so every number in it
can be traced to a field of the payload.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

FEATURE_LABELS = {
    "drv_form_pace": "Driver's recent race pace",
    "drv_form_n": "Number of recent races behind the driver's form",
    "drv_teammate_gap_form": "Driver's recent gap to team-mate",
    "drv_quali_form": "Driver's recent qualifying gap to pole",
    "drv_circuit_hist": "Driver's past pace at this circuit vs. form",
    "team_form_pace": "Team's recent race pace (car proxy)",
    "team_season_form": "Team's race pace this season",
    "team_season_events": "Races completed by the team this season",
    "team_quali_form": "Team's recent qualifying gap to pole",
    "evt_quali_gap": "Qualifying gap to pole at this event",
    "evt_team_quali_gap": "Team's qualifying gap to pole at this event",
    "circuit_length_km": "Circuit length",
    "circuit_turns": "Number of turns",
    "circuit_is_street": "Street circuit",
    "circuit_ref_lap_s": "Typical race lap at this circuit",
    "circuit_frac_slow": "Share of slow corners",
    "circuit_frac_fast": "Share of fast corners",
    "circuit_full_throttle_frac": "Full-throttle share of the lap",
    "compound": "Tyre compound",
    "compound_x_tyre_life": "Tyre age on this compound",
    "tyre_life_laps": "Tyre age",
    "fresh_tyre": "New tyre set",
    "stint": "Stint number",
    "track_temp_c": "Track temperature",
    "air_temp_c": "Air temperature",
    "humidity_pct": "Humidity",
    "rainfall": "Rain",
    "is_wet_compound": "Wet-weather tyre fitted",
    "race_progress": "Race phase (fuel-load proxy)",
    "lap_number": "Lap number",
    "is_sprint": "Sprint race",
    "historical_group": "Historical group median",
    "compound_x_race_phase": "Compound and race phase curve",
}


def label(f: str) -> str:
    return FEATURE_LABELS.get(f, f.replace("_", " "))


def contribution_rows(contrib: pd.Series, values: pd.Series, feature_group: dict, sec_per_pct: float | None) -> list[dict]:
    rows = []
    for f, c in contrib.items():
        v = values.get(f) if f in values.index else None
        if isinstance(v, (np.floating, np.integer)):
            v = v.item()
        if isinstance(v, float) and np.isnan(v):
            v = None
        rows.append({"feature": f, "label": label(f), "group": feature_group.get(f, "other"), "value": v,
                     "contribution_pct": float(c), "contribution_s": float(c * sec_per_pct) if sec_per_pct else None,
                     "direction": "faster" if c < 0 else "slower"})
    return sorted(rows, key=lambda r: -abs(r["contribution_pct"]))


def group_rows(rows: list[dict], sec_per_pct: float | None) -> list[dict]:
    agg: dict[str, float] = {}
    for r in rows:
        agg[r["group"]] = agg.get(r["group"], 0.0) + r["contribution_pct"]
    return sorted([{"group": g, "contribution_pct": v, "contribution_s": v * sec_per_pct if sec_per_pct else None,
                    "direction": "faster" if v < 0 else "slower"} for g, v in agg.items()],
                  key=lambda r: -abs(r["contribution_pct"]))


def fmt_pct(x: float) -> str:
    return f"{abs(x):.2f}%"


def lap_narrative(p: dict) -> str:
    pred = p["prediction"]
    v = pred["value_pct"]
    secs = pred.get("value_s")
    who = p["inputs"].get("driver_name") or p["inputs"]["driver_id"]
    side = "faster" if v < 0 else "slower"
    s = (f"For {who} at {p['inputs'].get('circuit_name') or p['inputs']['circuit_id']}, the model ({p['model']}, "
         f"{p['horizon'].replace('_', '-')} horizon) predicts a representative race lap {fmt_pct(v)} {side} than "
         f"the session reference")
    if secs is not None:
        s += f" (about {abs(secs):.2f} s per lap)"
    s += ". "
    iv = pred["interval"]
    s += (f"The {int(iv['level'] * 100)}% interval for a single lap is {iv['lo_pct']:+.2f}% to {iv['hi_pct']:+.2f}%; "
          f"it reflects lap-to-lap variation as well as model error. ")
    mu = pred.get("model_uncertainty")
    if mu:
        s += (f"Refitting the model on resampled races moves the expected value between {mu['lo_pct']:+.2f}% and "
              f"{mu['hi_pct']:+.2f}% (model uncertainty). ")
    top = [c for c in p["contributions"] if abs(c["contribution_pct"]) >= 0.02][:3]
    if top:
        parts = [f"{c['label'].lower()} ({c['contribution_pct']:+.2f}%)" for c in top]
        s += "Relative to the model's average output, the largest contributions are " + ", ".join(parts) + ". "
    if p.get("warnings"):
        s += "Caution: " + " ".join(p["warnings"]) + " "
    s += "Contributions describe how the model uses its inputs; they are associations, not causal effects."
    return s


def comparison_narrative(c: dict) -> str:
    a, b = c["drivers"]
    d = c["difference"]
    who_faster = a["name"] if d["value_pct"] < 0 else b["name"]
    s = (f"Under the selected conditions the model expects {who_faster} to be faster by about "
         f"{abs(d['value_pct']):.2f}% per representative lap")
    if d.get("value_s") is not None:
        s += f" ({abs(d['value_s']):.2f} s)"
    s += ". "
    mu = d.get("model_uncertainty")
    if mu:
        s += (f"Across {mu['n_models']} bootstrap refits the expected difference ranges from {mu['lo_pct']:+.2f}% to "
              f"{mu['hi_pct']:+.2f}% ({a['name']} minus {b['name']}). ")
        if mu["lo_pct"] < 0 < mu["hi_pct"]:
            s += "That range includes zero, so the ordering of the two drivers is not established. "
    if d.get("group_contributions"):
        g = d["group_contributions"][0]
        s += (f"The largest share of the difference comes from {g['group'].replace('_', ' ')} features "
              f"({g['contribution_pct']:+.2f}%). ")
    same = c.get("counterfactuals", {}).get("same_car")
    if same:
        s += (f"Giving both drivers the same team features changes the difference to {same['difference_pct']:+.2f}%, "
              f"which isolates the part the model associates with driver-specific inputs. ")
    if c.get("warnings"):
        s += "Caution: " + " ".join(c["warnings"]) + " "
    return s.strip()
