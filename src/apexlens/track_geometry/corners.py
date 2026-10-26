"""Corner segmentation, classification and validation.

Two independent methods:

* **marker**: FastF1 ``CircuitInfo`` corner markers (numbered corners from the official track map,
  as provided by FastF1), projected onto the reference path. Markers within ``COMPLEX_GAP_M`` of
  each other are analysed as one complex (e.g. a chicane).
* **curvature**: corners inferred from the smoothed heading of the reference path (|curvature| above
  1/``MAX_RADIUS_M``), independent of markers and of speed traces.

The curvature method is used to *validate* the marker positions (precision/recall per session) and
as the fallback when markers are missing; segments from it are labelled ``S1, S2, ...`` and never
presented as official corner numbers.

Category rules are explicit and adjustable (``CORNER_RULES``). They are ApexLens conventions, not
FIA classifications.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from apexlens.track_geometry.geometry import GRID_STEP_M, TrackReference

MAX_RADIUS_M = 350.0
MIN_HEADING_DEG = 15.0
MATCH_TOLERANCE_M = 80.0
COMPLEX_GAP_M = 120.0
WINDOW_MAX_M = 350.0

CORNER_RULES = {
    "slow_max_kph": 125.0,
    "fast_min_kph": 200.0,
    "flat_out_min_throttle": 95.0,      # throttle never drops below this in the window
    "flat_out_speed_ratio": 0.97,       # and min speed >= 97% of entry speed
    "chicane_max_speed_kph": 150.0,     # alternating-direction complex taken slowly
    "chicane_max_length_m": 300.0,
    "hairpin_min_heading_deg": 130.0,
    "hairpin_max_speed_kph": 110.0,
    "sweeper_min_heading_deg": 80.0,
    "sweeper_min_length_m": 250.0,
    "sweeper_min_speed_kph": 150.0,
}


def infer_corners(ref: TrackReference) -> pd.DataFrame:
    """Curvature-based corner candidates on the reference path."""
    k = ref.kappa
    thr = 1.0 / MAX_RADIUS_M
    active = np.abs(k) > thr / 2
    rows = []
    n = len(k)
    i = 0
    while i < n:
        if not active[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and active[j + 1] and np.sign(k[j + 1]) == np.sign(k[i]):
            j += 1
        seg = slice(i, j + 1)
        peak = i + int(np.argmax(np.abs(k[seg])))
        turn = float(np.degrees(np.sum(k[seg]) * GRID_STEP_M))
        if np.abs(k[peak]) > thr and abs(turn) >= MIN_HEADING_DEG:
            # curvature-weighted centre: stable for constant-radius arcs, where the argmax is arbitrary
            w = np.abs(k[seg])
            apex = float(np.sum(ref.s[seg] * w) / np.sum(w))
            rows.append({"start_s": float(ref.s[i]), "apex_s": apex, "end_s": float(ref.s[j]),
                         "heading_change_deg": turn, "max_curvature": float(np.abs(k[peak]))})
        i = j + 1
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # merge same-direction pieces separated by short gaps (one corner with a varying radius)
    merged = [df.iloc[0].to_dict()]
    for r in df.iloc[1:].to_dict("records"):
        last = merged[-1]
        if r["start_s"] - last["end_s"] < 30 and np.sign(r["heading_change_deg"]) == np.sign(last["heading_change_deg"]):
            last["end_s"] = r["end_s"]
            last["heading_change_deg"] += r["heading_change_deg"]
            if r["max_curvature"] > last["max_curvature"]:
                last["apex_s"], last["max_curvature"] = r["apex_s"], r["max_curvature"]
        else:
            merged.append(r)
    out = pd.DataFrame(merged)
    out["segment_id"] = [f"S{i + 1}" for i in range(len(out))]
    return out


def validate_markers(markers_s: np.ndarray, inferred: pd.DataFrame, length: float) -> dict:
    if inferred.empty or len(markers_s) == 0:
        return {"precision": None, "recall": None, "n_markers": int(len(markers_s)), "n_inferred": int(len(inferred))}
    apex = inferred["apex_s"].to_numpy()

    def circ_dist(a, b):
        d = np.abs(a - b)
        return np.minimum(d, length - d)

    marker_hit = np.array([circ_dist(apex, m).min() <= MATCH_TOLERANCE_M for m in markers_s])
    inferred_hit = np.array([circ_dist(markers_s, a).min() <= MATCH_TOLERANCE_M for a in apex])
    return {"precision": float(inferred_hit.mean()), "recall": float(marker_hit.mean()),
            "n_markers": int(len(markers_s)), "n_inferred": int(len(inferred)),
            "median_apex_error_m": float(np.median([circ_dist(apex, m).min() for m in markers_s]))}


MAX_MARKER_OFFSET_M = 30.0


def markers_usable(ref: TrackReference, markers: pd.DataFrame | None) -> tuple[bool, float | None]:
    """Markers must lie on the driven path; some sessions carry marker sets in another frame."""
    if markers is None or markers.empty or markers[["x_m", "y_m"]].isna().any().any():
        return False, None
    _, lateral = ref.project(markers["x_m"].to_numpy(), markers["y_m"].to_numpy())
    med = float(np.median(lateral))
    return med <= MAX_MARKER_OFFSET_M, med


def project_markers(ref: TrackReference, markers: pd.DataFrame) -> np.ndarray:
    """Marker positions on the reference path. FastF1's own marker distance guides the search so a marker
    near a crossover (e.g. Suzuka) snaps to the right branch."""
    x, y = markers["x_m"].to_numpy(), markers["y_m"].to_numpy()
    if "distance_m" in markers and markers["distance_m"].notna().all():
        guide = np.clip(markers["distance_m"].to_numpy(dtype=float), 0, ref.length)
        s, _ = ref.project_guided(x, y, guide, window_m=200.0, total=ref.length, monotonic=False)
    else:
        s, _ = ref.project(x, y)
    return np.mod(s, ref.length)


def _local_direction(ref: TrackReference, s0: float, half: float = 40.0) -> float:
    m = (ref.s >= s0 - half) & (ref.s <= s0 + half)
    return float(np.sign(np.sum(ref.kappa[m]))) if m.any() else 0.0


def corner_definitions(ref: TrackReference, markers: pd.DataFrame | None, inferred: pd.DataFrame) -> pd.DataFrame:
    """Analysis windows (entry, characteristic minimum-speed point, exit) for each corner or complex."""
    if markers is not None and len(markers) and markers_usable(ref, markers)[0]:
        s_m = project_markers(ref, markers)
        labels = [f"T{int(n)}{(letter or '').strip()}" for n, letter in zip(markers["number"], markers["letter"], strict=True)]
        base = pd.DataFrame({"label": labels, "anchor_s": s_m}).sort_values("anchor_s")
        method = "marker"
    else:
        base = pd.DataFrame({"label": inferred["segment_id"], "anchor_s": inferred["apex_s"]})
        method = "curvature"
    base = base.reset_index(drop=True)
    base["direction"] = [_local_direction(ref, a) for a in base["anchor_s"]]
    # group close anchors into complexes
    groups, cur = [], [0]
    for i in range(1, len(base)):
        if base.loc[i, "anchor_s"] - base.loc[i - 1, "anchor_s"] <= COMPLEX_GAP_M:
            cur.append(i)
        else:
            groups.append(cur)
            cur = [i]
    groups.append(cur)
    speed = ref.speed if ref.speed is not None else np.full_like(ref.s, np.nan)
    throttle = ref.throttle if ref.throttle is not None else np.full_like(ref.s, np.nan)
    anchors = [(base.loc[g[0], "anchor_s"], base.loc[g[-1], "anchor_s"]) for g in groups]
    rows = []
    for gi, g in enumerate(groups):
        first, last = anchors[gi]
        prev_last = anchors[gi - 1][1] if gi > 0 else first - WINDOW_MAX_M
        next_first = anchors[gi + 1][0] if gi + 1 < len(groups) else last + WINDOW_MAX_M
        lo_bound = max(first - WINDOW_MAX_M, (prev_last + first) / 2, 0.0)
        hi_bound = min(last + WINDOW_MAX_M, (last + next_first) / 2, float(ref.s[-1]))
        core = (ref.s >= first - 60) & (ref.s <= last + 60)
        apex_idx = np.flatnonzero(core)[np.argmin(speed[core])] if core.any() and np.isfinite(speed[core]).any() else None
        apex_s = float(ref.s[apex_idx]) if apex_idx is not None else float(first)
        before = (ref.s >= lo_bound) & (ref.s <= apex_s)
        after = (ref.s >= apex_s) & (ref.s <= hi_bound)
        entry_s = float(ref.s[before][np.argmax(speed[before])]) if before.any() else lo_bound
        exit_s = float(ref.s[after][np.argmax(speed[after])]) if after.any() else hi_bound
        if exit_s - apex_s < 20:
            exit_s = min(hi_bound, apex_s + 20)
        win = (ref.s >= entry_s) & (ref.s <= exit_s)
        min_speed = float(np.nanmin(speed[win])) if win.any() else np.nan
        entry_speed = float(np.interp(entry_s, ref.s, speed))
        # total direction change across the analysis window (straight parts contribute ~0)
        heading = float(np.degrees(np.sum(ref.kappa[win]) * GRID_STEP_M)) if win.any() else 0.0
        dirs = [base.loc[i, "direction"] for i in g]
        alternating = len(g) > 1 and any(dirs[i] * dirs[i + 1] < 0 for i in range(len(dirs) - 1))
        rows.append({
            "corner_id": "-".join(base.loc[i, "label"] for i in g) if len(g) > 1 else base.loc[g[0], "label"],
            "labels": [base.loc[i, "label"] for i in g], "method": method, "n_markers": len(g),
            "entry_s": entry_s, "apex_s": apex_s, "exit_s": exit_s, "length_m": exit_s - entry_s,
            "anchor_s": float(first), "heading_change_deg": heading,
            "direction": "left" if heading > 0 else "right", "alternating": alternating,
            "entry_speed_ref": entry_speed, "min_speed_ref": min_speed,
            "exit_speed_ref": float(np.interp(exit_s, ref.s, speed)),
            "min_throttle_ref": float(np.nanmin(throttle[win])) if win.any() else np.nan,
            "x": float(np.interp(apex_s, ref.s, ref.x)), "y": float(np.interp(apex_s, ref.s, ref.y)),
        })
    defs = pd.DataFrame(rows)
    # marker sets occasionally repeat a label (seen at the Hungaroring); IDs must be unique per session
    dup = defs.groupby("corner_id").cumcount()
    defs["corner_id"] = np.where(dup > 0, defs["corner_id"] + "#" + (dup + 1).astype(str), defs["corner_id"])
    return classify(defs)


def classify(defs: pd.DataFrame, rules: dict | None = None) -> pd.DataFrame:
    r = {**CORNER_RULES, **(rules or {})}
    d = defs.copy()
    flat = (d["min_throttle_ref"] >= r["flat_out_min_throttle"]) & (
        d["min_speed_ref"] >= r["flat_out_speed_ratio"] * d["entry_speed_ref"])
    d["category"] = np.select(
        [flat, d["min_speed_ref"] < r["slow_max_kph"], d["min_speed_ref"] < r["fast_min_kph"]],
        ["flat_out", "slow", "medium"], default="fast")
    d["is_hairpin"] = (d["heading_change_deg"].abs() >= r["hairpin_min_heading_deg"]) & (d["min_speed_ref"] < r["hairpin_max_speed_kph"])
    d["is_chicane"] = d["alternating"] & (d["min_speed_ref"] < r["chicane_max_speed_kph"]) & (d["length_m"] <= r["chicane_max_length_m"])
    d["is_esses"] = d["alternating"] & ~d["is_chicane"]
    d["is_sweeper"] = (d["heading_change_deg"].abs() >= r["sweeper_min_heading_deg"]) & (d["length_m"] >= r["sweeper_min_length_m"]) \
        & (d["min_speed_ref"] >= r["sweeper_min_speed_kph"])
    d["is_sequence"] = (d["n_markers"] > 1) & ~d["alternating"]
    d["approx_radius_m"] = d["length_m"] / np.maximum(np.radians(d["heading_change_deg"].abs()), 1e-3)
    return d


def full_throttle_zones(ref: TrackReference, min_length_m: float = 300.0, throttle: float = 98.0) -> pd.DataFrame:
    if ref.throttle is None:
        return pd.DataFrame()
    on = ref.throttle >= throttle
    rows, i, n = [], 0, len(on)
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and on[j + 1]:
            j += 1
        length = float(ref.s[j] - ref.s[i])
        if length >= min_length_m:
            rows.append({"start_s": float(ref.s[i]), "end_s": float(ref.s[j]), "length_m": length,
                         "max_speed_ref": float(np.max(ref.speed[i:j + 1])) if ref.speed is not None else np.nan})
        i = j + 1
    return pd.DataFrame(rows)
