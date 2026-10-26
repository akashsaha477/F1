"""Geometry, segmentation and corner metrics on synthetic tracks with known shape."""

import numpy as np
import pandas as pd

from apexlens.features.corner_metrics import comparable_teammates, lap_corner_metrics
from apexlens.track_geometry.corners import (
    corner_definitions,
    infer_corners,
    markers_usable,
    validate_markers,
)
from apexlens.track_geometry.geometry import TrackReference


def stadium(straight=1000.0, radius=100.0, n=4000):
    """Two straights joined by two 180-degree hairpins (anticlockwise), sampled by arc length."""
    L = 2 * straight + 2 * np.pi * radius
    s = np.linspace(0, L, n, endpoint=False)
    x, y = np.zeros(n), np.zeros(n)
    for i, si in enumerate(s):
        if si < straight:
            x[i], y[i] = si, 0
        elif si < straight + np.pi * radius:
            a = (si - straight) / radius
            x[i], y[i] = straight + radius * np.sin(a), radius - radius * np.cos(a)
        elif si < 2 * straight + np.pi * radius:
            x[i], y[i] = straight - (si - straight - np.pi * radius), 2 * radius
        else:
            a = (si - 2 * straight - np.pi * radius) / radius
            x[i], y[i] = -radius * np.sin(a), radius + radius * np.cos(a)
    # start the lap in the middle of the first straight so no corner straddles the line
    k = int(n * (straight / 2) / L)
    return s, np.roll(x, -k), np.roll(y, -k), L


def lap_frame(s, x, y, L, slow=80.0, fast=300.0, radius=100.0, straight=1000.0, t_offset=0.0):
    """Speed drops to ``slow`` in the hairpins; time integrates distance / speed."""
    u = np.mod(s + straight / 2, L)  # undo the start offset applied in stadium()
    in_turn = ((u > straight) & (u < straight + np.pi * radius)) | (u > 2 * straight + np.pi * radius)
    v = np.where(in_turn, slow, fast).astype(float)
    v = np.convolve(v, np.ones(80) / 80, mode="same")
    v[:40], v[-40:] = fast, v[-41]
    ds = np.diff(s, append=L)
    t = np.r_[0, np.cumsum(ds[:-1] / (v[:-1] / 3.6))] + t_offset
    return pd.DataFrame({"x_m": x, "y_m": y, "distance_m": s, "speed_kph": v, "time_s": t,
                         "throttle_pct": np.where(v > 0.98 * fast, 100.0, 20.0), "brake": np.r_[np.diff(v) < -0.5, False],
                         "gear": np.where(v > 200, 8, 3)})


def test_reference_curvature_and_inferred_corners():
    s, x, y, L = stadium()
    ref = TrackReference.from_lap(lap_frame(s, x, y, L))
    assert abs(ref.length - L) / L < 0.01
    inner = (ref.s > 600) & (ref.s < 750)
    assert abs(np.median(ref.kappa[inner]) - 1 / 100) < 0.002  # radius 100 m
    inf = infer_corners(ref)
    assert len(inf) == 2
    assert np.allclose(np.abs(inf["heading_change_deg"]), 180, atol=12)


def test_corner_definitions_classify_hairpins_and_metrics():
    s, x, y, L = stadium()
    lap = lap_frame(s, x, y, L)
    ref = TrackReference.from_lap(lap)
    defs = corner_definitions(ref, None, infer_corners(ref))
    assert set(defs["category"]) == {"slow"}
    assert defs["is_hairpin"].all()
    assert (defs["method"] == "curvature").all()
    m = lap_corner_metrics(ref, defs, lap)
    assert len(m) == 2 and (m["quality"] == "ok").all()
    assert np.allclose(m["min_speed_kph"], 80, atol=2)
    # a slower lap in the same corners must produce a longer segment time
    slower = lap_frame(s, x, y, L, slow=70)
    m2 = lap_corner_metrics(ref, defs, slower)
    assert (m2["segment_time_s"].to_numpy() > m["segment_time_s"].to_numpy()).all()


def test_marker_validation_and_gating():
    s, x, y, L = stadium()
    ref = TrackReference.from_lap(lap_frame(s, x, y, L))
    inf = infer_corners(ref)
    good = pd.DataFrame({"x_m": [1100.0, -100.0], "y_m": [100.0, 100.0], "number": [1, 2], "letter": ["", ""]})
    assert markers_usable(ref, good)[0]
    far = good.assign(x_m=good["x_m"] + 500)
    assert not markers_usable(ref, far)[0]
    v = validate_markers(np.array([657.0, 1971.0]), inf, ref.length)
    assert v["recall"] == 1.0 and v["precision"] == 1.0


def test_guided_projection_handles_crossover():
    # figure-eight: the path crosses itself at the origin
    t = np.linspace(0, 2 * np.pi, 3000, endpoint=False)
    x, y = 500 * np.sin(t), 250 * np.sin(2 * t)
    seg = np.hypot(np.diff(x, append=x[0]), np.diff(y, append=y[0]))
    dist = np.r_[0, np.cumsum(seg[:-1])]
    lap = pd.DataFrame({"x_m": x, "y_m": y, "distance_m": dist})
    ref = TrackReference.from_lap(lap)
    s_guided, _ = ref.project_guided(x, y, dist)
    assert np.all(np.diff(s_guided) >= 0)
    assert np.max(np.abs(s_guided - dist * ref.length / dist[-1])) < 30


def test_teammate_comparability_rule():
    laps = pd.DataFrame({"constructor_id": ["a", "a", "b", "b", "c"], "lap_time_s": [90.0, 90.5, 90.0, 92.0, 91.0],
                         "session_time_end_s": [100.0, 400.0, 100.0, 200.0, 50.0], "quali_segment": [None] * 5})
    out = comparable_teammates(laps)
    assert out == {"a": True, "b": False, "c": False}
    laps.loc[1, "session_time_end_s"] = 2000.0
    assert comparable_teammates(laps)["a"] is False
