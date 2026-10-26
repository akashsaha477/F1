"""Gold corner tables from qualifying telemetry (Phase 4).

Per session: reference path from the fastest telemetry lap, corner definitions (markers, validated
against curvature-inferred corners), and per-lap corner metrics. Per circuit: a static profile used
as track descriptors. Per driver-season: corner-category performance relative to the team-mate.

Measured vs derived (stated in the API):
* measured channels: speed, throttle, brake (on/off), gear, position;
* derived: segment times (interpolated at window boundaries), braking point/duration (from the
  on/off brake channel), time from minimum speed to full throttle, deceleration proxy (dv/dt).
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from apexlens.storage.io import (
    read_json,
    read_partition,
    read_table,
    write_json,
    write_partition,
    write_table,
)
from apexlens.storage.paths import DataPaths
from apexlens.track_geometry.corners import (
    corner_definitions,
    full_throttle_zones,
    infer_corners,
    markers_usable,
    project_markers,
    validate_markers,
)
from apexlens.track_geometry.geometry import TrackReference

log = logging.getLogger(__name__)

MAX_GAP_S = 0.5
MAX_LATERAL_M = 25.0


TEAMMATE_MAX_LAPTIME_GAP = 0.015   # fraction of lap time
TEAMMATE_MAX_SESSION_GAP_S = 900.0  # laps set more than 15 min apart are usually different segments


def comparable_teammates(tlaps: pd.DataFrame) -> dict[str, bool]:
    """Team-mate laps are compared only when set in the same part of qualifying under similar conditions."""
    out = {}
    for team, g in tlaps.groupby("constructor_id"):
        if len(g) != 2:
            out[team] = False
            continue
        a, b = g.iloc[0], g.iloc[1]
        same_seg = True
        if pd.notna(a.get("quali_segment")) and pd.notna(b.get("quali_segment")):
            same_seg = a["quali_segment"] == b["quali_segment"]
        close_time = (pd.isna(a.get("session_time_end_s")) or pd.isna(b.get("session_time_end_s"))
                      or abs(a["session_time_end_s"] - b["session_time_end_s"]) <= TEAMMATE_MAX_SESSION_GAP_S)
        close_pace = abs(a["lap_time_s"] - b["lap_time_s"]) / min(a["lap_time_s"], b["lap_time_s"]) <= TEAMMATE_MAX_LAPTIME_GAP
        out[team] = bool(same_seg and close_time and close_pace)
    return out


def lap_corner_metrics(ref: TrackReference, defs: pd.DataFrame, lap: pd.DataFrame) -> pd.DataFrame:
    s, lateral = ref.project_guided(lap["x_m"].to_numpy(), lap["y_m"].to_numpy(), lap["distance_m"].to_numpy())
    t = lap["time_s"].to_numpy(dtype=float)
    v = lap["speed_kph"].to_numpy(dtype=float)
    thr = lap["throttle_pct"].to_numpy(dtype=float)
    brk = lap["brake"].to_numpy().astype(bool)
    gear = lap["gear"].to_numpy(dtype=float)
    # interpolation needs strictly increasing s
    su, first_idx = np.unique(s, return_index=True)
    tu, vu = t[first_idx], v[first_idx]
    rows = []
    for c in defs.itertuples():
        if c.entry_s < su[0] or c.exit_s > su[-1]:
            continue
        m = (s >= c.entry_s) & (s <= c.exit_s)
        t_in, t_out = np.interp(c.entry_s, su, tu), np.interp(c.exit_s, su, tu)
        gaps = np.diff(t[m]) if m.sum() > 1 else np.array([np.inf])
        ok = m.sum() >= 3 and gaps.max() <= MAX_GAP_S and np.nanmax(lateral[m]) <= MAX_LATERAL_M
        vm = v[m]
        imin = np.flatnonzero(m)[np.argmin(vm)] if m.any() else None
        before = m & (s <= (s[imin] if imin is not None else c.apex_s))
        b_idx = np.flatnonzero(before & brk)
        brake_s = float(s[b_idx[0]]) if len(b_idx) else np.nan
        brake_dur = float(np.sum(np.diff(t)[np.clip(b_idx, 0, len(t) - 2)])) if len(b_idx) else 0.0
        after = m & (s >= (s[imin] if imin is not None else c.apex_s))
        f_idx = np.flatnonzero(after & (thr >= 98))
        full_s = float(s[f_idx[0]]) if len(f_idx) else np.nan
        full_delay = float(t[f_idx[0]] - t[imin]) if len(f_idx) and imin is not None else np.nan
        dv = np.diff(vu / 3.6) / np.maximum(np.diff(tu), 1e-3)
        mid = (su[:-1] + su[1:]) / 2
        win_dv = dv[(mid >= c.entry_s) & (mid <= c.exit_s)]
        rows.append({
            "corner_id": c.corner_id, "segment_time_s": float(t_out - t_in),
            "entry_speed_kph": float(np.interp(c.entry_s, su, vu)), "min_speed_kph": float(vm.min()) if len(vm) else np.nan,
            "exit_speed_kph": float(np.interp(c.exit_s, su, vu)),
            "min_speed_s": float(s[imin]) if imin is not None else np.nan,
            "brake_onset_before_apex_m": float(c.apex_s - brake_s) if np.isfinite(brake_s) else np.nan,
            "braking_duration_s": brake_dur,
            "full_throttle_delay_s": full_delay,
            "full_throttle_after_apex_m": float(full_s - c.apex_s) if np.isfinite(full_s) else np.nan,
            "min_gear": float(np.nanmin(gear[m])) if m.any() else np.nan,
            "gear_changes": int(np.sum(np.diff(gear[m]) != 0)) if m.sum() > 1 else 0,
            "max_decel_proxy_ms2": float(-np.min(win_dv)) if len(win_dv) else np.nan,
            "n_samples": int(m.sum()), "max_sample_gap_s": float(gaps.max()) if np.isfinite(gaps.max()) else np.nan,
            "quality": "ok" if ok else "low",
        })
    return pd.DataFrame(rows)


def session_corner_tables(paths: DataPaths, session_id: str) -> dict | None:
    tel = read_partition(paths.silver("telemetry_samples"), session_id)
    tlaps = read_partition(paths.silver("telemetry_laps"), session_id)
    if tel.empty or tlaps.empty:
        return None
    markers = read_partition(paths.silver("corner_markers"), session_id)
    best = tlaps.sort_values("lap_time_s").iloc[0]
    ref_lap = tel[(tel["driver_id"] == best["driver_id"]) & (tel["lap_number"] == best["lap_number"])].sort_values("time_s")
    if len(ref_lap) < 100 or ref_lap[["x_m", "y_m"]].isna().any().any():
        return None
    ref = TrackReference.from_lap(ref_lap)
    inferred = infer_corners(ref)
    defs = corner_definitions(ref, markers if len(markers) else None, inferred)
    validation = {}
    usable, offset = markers_usable(ref, markers if len(markers) else None)
    if usable:
        validation = validate_markers(project_markers(ref, markers), inferred, ref.length)
        validation["status"] = "markers_used"
    elif len(markers):
        validation = {"status": "markers_rejected_off_path", "median_marker_offset_m": offset,
                      "n_markers": int(len(markers)), "n_inferred": int(len(inferred))}
    else:
        validation = {"status": "no_markers", "n_inferred": int(len(inferred))}
    validation["median_marker_offset_m"] = offset
    # when each telemetry lap was set, to compare team-mates only on comparable runs
    laps = read_partition(paths.silver("laps"), session_id)[["driver_id", "lap_number", "session_time_end_s", "quali_segment",
                                                             "sector1_s", "sector2_s"]]
    tlaps = tlaps.merge(laps, on=["driver_id", "lap_number"], how="left")
    meta = tlaps.iloc[0]
    ctx = {"session_id": session_id, "event_id": meta["event_id"], "season": int(meta["season"]),
           "session_code": meta["session_code"]}
    rows, align, bounds = [], [], []
    for lap in tlaps.itertuples():
        d = tel[(tel["driver_id"] == lap.driver_id) & (tel["lap_number"] == lap.lap_number)].sort_values("time_s")
        if len(d) < 50 or d[["x_m", "y_m"]].isna().any().any():
            continue
        cm = lap_corner_metrics(ref, defs, d)
        if cm.empty:
            continue
        cm = cm.assign(driver_id=lap.driver_id, constructor_id=lap.constructor_id, lap_number=lap.lap_number,
                       lap_time_s=lap.lap_time_s, compound=lap.compound, lap_session_time_s=lap.session_time_end_s,
                       quali_segment=lap.quali_segment, **ctx)
        rows.append(cm)
        s, lateral = ref.project_guided(d["x_m"].to_numpy(), d["y_m"].to_numpy(), d["distance_m"].to_numpy())
        if pd.notna(lap.sector1_s) and pd.notna(lap.sector2_s):
            tt = d["time_s"].to_numpy(dtype=float)
            bounds.append((float(np.interp(lap.sector1_s, tt, s)), float(np.interp(lap.sector1_s + lap.sector2_s, tt, s))))
        align.append({"driver_id": lap.driver_id, "lap_number": lap.lap_number,
                      "projected_length_m": float(s.max() - s.min()), "telemetry_distance_m": float(d["distance_m"].max()),
                      "median_lateral_m": float(np.median(lateral)), "max_lateral_m": float(np.max(lateral))})
    metrics = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    if len(metrics):
        # plausibility: a segment time far from the corner's median signals a projection/data problem
        med = metrics.groupby("corner_id")["segment_time_s"].transform("median")
        bad = (metrics["segment_time_s"] < 0.7 * med) | (metrics["segment_time_s"] > 1.3 * med)
        metrics.loc[bad, "quality"] = "implausible"
        ok = metrics["quality"] == "ok"
        best_t = metrics[ok].groupby("corner_id")["segment_time_s"].min()
        metrics["delta_to_best_s"] = metrics["segment_time_s"] - metrics["corner_id"].map(best_t)
        comparable = comparable_teammates(tlaps)
        metrics["teammate_comparable"] = metrics["constructor_id"].map(comparable).fillna(False).astype(bool)
        tmp = metrics.assign(_seg=metrics["segment_time_s"].where(ok), _vmin=metrics["min_speed_kph"].where(ok))
        g = tmp.groupby(["corner_id", "constructor_id"])
        tot, cnt = g["_seg"].transform("sum"), g["_seg"].transform("count")
        pair = (cnt == 2) & metrics["teammate_comparable"] & ok
        metrics["delta_to_teammate_s"] = np.where(pair, metrics["segment_time_s"] - (tot - metrics["segment_time_s"]), np.nan)
        vt = g["_vmin"].transform("sum")
        metrics["min_speed_delta_to_teammate_kph"] = np.where(pair, metrics["min_speed_kph"] - (vt - metrics["min_speed_kph"]), np.nan)
        metrics = metrics.merge(defs[["corner_id", "category", "is_hairpin", "is_chicane", "is_sweeper", "method"]],
                                on="corner_id", how="left")
    b1, b2 = (float(np.median([b[0] for b in bounds])), float(np.median([b[1] for b in bounds]))) if bounds else (np.nan, np.nan)
    defs["sector"] = np.where(defs["apex_s"] < b1, 1, np.where(defs["apex_s"] < b2, 2, 3)) if bounds else np.nan
    if len(metrics):
        metrics = metrics.merge(defs[["corner_id", "sector"]], on="corner_id", how="left")
    sectors = []
    if bounds:
        edges = [0.0, b1, b2, ref.length]
        for k in range(3):
            dk = defs[defs["sector"] == k + 1]
            real = dk[dk["category"] != "flat_out"]
            n = max(len(real), 1)
            m_s = (ref.s >= edges[k]) & (ref.s < edges[k + 1])
            sectors.append({**ctx, "sector": k + 1, "start_s": edges[k], "end_s": edges[k + 1], "length_m": edges[k + 1] - edges[k],
                            "n_corners": int(len(dk)), "frac_slow": float((real["category"] == "slow").sum() / n),
                            "frac_medium": float((real["category"] == "medium").sum() / n),
                            "frac_fast": float((real["category"] == "fast").sum() / n),
                            "full_throttle_frac": float(np.mean(ref.throttle[m_s] >= 98)) if ref.throttle is not None and m_s.any() else np.nan,
                            "boundary_laps": len(bounds)})
    zones = full_throttle_zones(ref)
    ft_frac = float(np.mean(ref.throttle >= 98)) if ref.throttle is not None else np.nan
    defs = defs.assign(**ctx)
    track = pd.DataFrame({"s": ref.s[::5], "x": ref.x[::5], "y": ref.y[::5],
                          "speed_ref": ref.speed[::5] if ref.speed is not None else np.nan,
                          "throttle_ref": ref.throttle[::5] if ref.throttle is not None else np.nan}).assign(**ctx)
    summary = {**ctx, "reference_driver": best["driver_id"], "reference_lap": int(best["lap_number"]),
               "reference_lap_time_s": float(best["lap_time_s"]), "length_m": ref.length,
               "rotation_deg": float(markers["rotation_deg"].iloc[0]) if len(markers) and pd.notna(markers["rotation_deg"].iloc[0]) else 0.0,
               "n_corners": int(len(defs)), "n_inferred": int(len(inferred)), "full_throttle_frac": ft_frac,
               "n_full_throttle_zones": int(len(zones)), "segmentation_method": defs["method"].iloc[0] if len(defs) else None,
               "marker_validation": validation, "alignment": align}
    summary["sector_bounds_m"] = [b1, b2] if bounds else None
    return {"defs": defs, "metrics": metrics, "track": track, "summary": summary, "inferred": inferred.assign(**ctx),
            "sectors": pd.DataFrame(sectors)}


def build_corner_tables(paths: DataPaths) -> dict:
    tl = read_table(paths.silver("telemetry_laps"), columns=["session_id", "session_code"])
    sessions = sorted(tl[tl["session_code"] == "Q"]["session_id"].unique()) if len(tl) else []
    events = read_table(paths.silver("events"))[["event_id", "circuit_id", "circuit_layout_id", "date"]]
    summaries = []
    for sid in sessions:
        try:
            res = session_corner_tables(paths, sid)
        except Exception:  # noqa: BLE001 - a malformed session must not stop the build
            log.exception("corner analysis failed for %s", sid)
            continue
        if res is None:
            continue
        write_partition(paths.gold("corner_definitions"), sid, res["defs"])
        write_partition(paths.gold("corner_metrics"), sid, res["metrics"])
        write_partition(paths.gold("track_maps"), sid, res["track"])
        write_partition(paths.gold("inferred_segments"), sid, res["inferred"])
        if len(res["sectors"]):
            write_partition(paths.gold("sector_profiles"), sid, res["sectors"])
        summaries.append(res["summary"])
        log.info("corners %s: %d corners, %d laps", sid, res["summary"]["n_corners"],
                 res["metrics"]["driver_id"].nunique() if len(res["metrics"]) else 0)
    summ = pd.DataFrame(summaries).merge(events, on="event_id", how="left")
    write_json(paths.gold("corner_definitions") / "sessions.json", summ.to_dict("records"))
    prof = circuit_profiles(paths, summ)
    dcp = driver_corner_profiles(paths)
    return {"sessions": len(summ), "circuit_profiles": len(prof), "driver_corner_profiles": len(dcp)}


def circuit_profiles(paths: DataPaths, summ: pd.DataFrame) -> pd.DataFrame:
    defs = read_table(paths.gold("corner_definitions"))
    if defs.empty:
        return pd.DataFrame()
    rows = []
    for (circuit, layout), g in summ.sort_values("date").groupby(["circuit_id", "circuit_layout_id"]):
        latest = g.iloc[-1]
        d = defs[defs["session_id"] == latest["session_id"]]
        real = d[d["category"] != "flat_out"]
        n = max(len(real), 1)
        rows.append({
            "circuit_id": circuit, "circuit_layout_id": layout, "reference_session": latest["session_id"],
            "n_sessions": int(len(g)), "n_corners": int(len(d)), "n_flat_out": int((d["category"] == "flat_out").sum()),
            "circuit_frac_slow": float((real["category"] == "slow").sum() / n),
            "circuit_frac_medium": float((real["category"] == "medium").sum() / n),
            "circuit_frac_fast": float((real["category"] == "fast").sum() / n),
            "circuit_full_throttle_frac": float(g["full_throttle_frac"].median()),
            "mean_min_speed_kph": float(real["min_speed_ref"].mean()) if len(real) else np.nan,
            "length_m": float(latest["length_m"]),
            "marker_precision": latest["marker_validation"].get("precision") if isinstance(latest["marker_validation"], dict) else None,
            "marker_recall": latest["marker_validation"].get("recall") if isinstance(latest["marker_validation"], dict) else None,
        })
    prof = pd.DataFrame(rows)
    # one row per circuit for model features: the most recent layout
    latest_layout = summ.sort_values("date").groupby("circuit_id")["circuit_layout_id"].last()
    prof = prof[prof.apply(lambda r: latest_layout.get(r["circuit_id"]) == r["circuit_layout_id"], axis=1)]
    write_table(paths.gold("circuit_profiles"), prof)
    return prof


def driver_corner_profiles(paths: DataPaths, n_boot: int = 400, seed: int = 0) -> pd.DataFrame:
    """Per driver-season and corner category: segment-time delta to the team-mate (% of segment time)."""
    m = read_table(paths.gold("corner_metrics"))
    if m.empty:
        return pd.DataFrame()
    m = m[(m["quality"] == "ok") & m["delta_to_teammate_s"].notna() & (m["category"] != "flat_out")].copy()
    m["delta_pct"] = 100 * m["delta_to_teammate_s"] / (m["segment_time_s"] - m["delta_to_teammate_s"] / 2)
    # per session and category first (corners within a lap are not independent)
    sess = m.groupby(["driver_id", "season", "session_id", "category"]).agg(
        delta_pct=("delta_pct", "mean"), min_speed_delta=("min_speed_delta_to_teammate_kph", "mean"),
        n_corners=("corner_id", "count")).reset_index()
    rng = np.random.default_rng(seed)
    rows = []
    for (d, s, cat), g in sess.groupby(["driver_id", "season", "category"]):
        v = g["delta_pct"].to_numpy()
        boots = [np.mean(rng.choice(v, len(v))) for _ in range(n_boot)] if len(v) >= 3 else []
        rows.append({"driver_id": d, "season": s, "category": cat, "delta_pct": float(np.mean(v)),
                     "ci_lo": float(np.quantile(boots, 0.05)) if boots else np.nan,
                     "ci_hi": float(np.quantile(boots, 0.95)) if boots else np.nan,
                     "min_speed_delta_kph": float(g["min_speed_delta"].mean()), "n_sessions": int(len(g)),
                     "n_corners": int(g["n_corners"].sum())})
    out = pd.DataFrame(rows)
    write_table(paths.gold("driver_corner_profiles"), out)
    write_table(paths.gold("driver_corner_sessions"), sess)
    return out


def specialisation_reliability(paths: DataPaths, min_sessions: int = 8, n_perm: int = 2000, seed: int = 0) -> dict:
    """Split-half test: is a driver's slow-vs-fast corner specialisation (relative to the team-mate) repeatable?

    Sessions of each driver-season are split into odd and even rounds. For each half the specialisation
    score is mean(slow delta) - mean(fast delta). The across-driver correlation between halves is
    compared with a permutation null. The same is done for the overall team-mate delta as a benchmark.
    """
    sess = read_table(paths.gold("driver_corner_sessions"))
    if sess.empty:
        return {}
    sess["round"] = sess["session_id"].str.split("-").str[1].astype(int)
    sess["half"] = np.where(sess["round"] % 2 == 0, "even", "odd")
    piv = sess.pivot_table(index=["driver_id", "season", "half"], columns="category", values="delta_pct", aggfunc="mean")
    cnt = sess.groupby(["driver_id", "season"])["session_id"].nunique()
    piv = piv.reset_index()
    piv = piv[piv.set_index(["driver_id", "season"]).index.isin(cnt[cnt >= min_sessions].index)]
    piv["special"] = piv.get("slow") - piv.get("fast")
    piv["overall"] = piv[[c for c in ["slow", "medium", "fast"] if c in piv]].mean(axis=1)
    rng = np.random.default_rng(seed)
    out = {"min_sessions": min_sessions}
    for metric in ["special", "overall"]:
        w = piv.pivot_table(index=["driver_id", "season"], columns="half", values=metric).dropna()
        if len(w) < 5:
            out[metric] = {"n_driver_seasons": int(len(w))}
            continue
        r = float(np.corrcoef(w["odd"], w["even"])[0, 1])
        null = [np.corrcoef(w["odd"], rng.permutation(w["even"].to_numpy()))[0, 1] for _ in range(n_perm)]
        out[metric] = {"n_driver_seasons": int(len(w)), "split_half_r": r,
                       "spearman_brown_reliability": float(2 * r / (1 + r)) if r > -1 else None,
                       "permutation_p": float((np.sum(np.abs(null) >= abs(r)) + 1) / (n_perm + 1))}
    meta = read_json(paths.gold("corner_definitions") / "sessions.json", default=[])
    out["n_sessions_with_corners"] = len(meta)
    return out
