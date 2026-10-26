"""Track representation: a smoothed centre-line with a distance axis, heading and curvature.

The reference path of a session is built from its fastest telemetry lap (FastF1 position data, in
metres). Every other lap is aligned to it by projecting its samples onto the path (nearest point),
which avoids relying on per-lap integrated distance — that drifts between laps and data streams.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.signal import savgol_filter
from scipy.spatial import cKDTree

GRID_STEP_M = 2.0


def resample_closed(x: np.ndarray, y: np.ndarray, step: float = GRID_STEP_M) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Uniformly resample a lap path by arc length."""
    pts = np.column_stack([x, y]).astype(float)
    keep = np.r_[True, np.hypot(*np.diff(pts, axis=0).T) > 1e-6]
    pts = pts[keep]
    seg = np.hypot(*np.diff(pts, axis=0).T)
    s = np.r_[0.0, np.cumsum(seg)]
    grid = np.arange(0.0, s[-1], step)
    return grid, np.interp(grid, s, pts[:, 0]), np.interp(grid, s, pts[:, 1])


def smooth_closed(v: np.ndarray, window_m: float, step: float = GRID_STEP_M, order: int = 3) -> np.ndarray:
    w = int(round(window_m / step)) | 1
    w = max(w, order + 2 | 1)
    return savgol_filter(v, w, order, mode="wrap")


def heading_and_curvature(x: np.ndarray, y: np.ndarray, step: float = GRID_STEP_M) -> tuple[np.ndarray, np.ndarray]:
    dx, dy = np.gradient(x, step), np.gradient(y, step)
    heading = np.unwrap(np.arctan2(dy, dx))
    kappa = np.gradient(heading, step)
    return heading, kappa


@dataclass
class TrackReference:
    s: np.ndarray
    x: np.ndarray
    y: np.ndarray
    heading: np.ndarray
    kappa: np.ndarray
    length: float
    speed: np.ndarray | None = None
    throttle: np.ndarray | None = None
    brake: np.ndarray | None = None
    gear: np.ndarray | None = None
    time: np.ndarray | None = None

    @classmethod
    def from_lap(cls, lap, smooth_window_m: float = 40.0, curvature_window_m: float = 60.0) -> TrackReference:
        """``lap``: DataFrame with x_m, y_m (and optionally speed_kph, throttle_pct, brake, gear, time_s)."""
        s, x, y = resample_closed(lap["x_m"].to_numpy(), lap["y_m"].to_numpy())
        xs, ys = smooth_closed(x, smooth_window_m), smooth_closed(y, smooth_window_m)
        heading, _ = heading_and_curvature(xs, ys)
        kappa = smooth_closed(np.gradient(heading, GRID_STEP_M), curvature_window_m, order=2)
        ref = cls(s=s, x=xs, y=ys, heading=heading, kappa=kappa, length=float(s[-1] + GRID_STEP_M))
        tree = cKDTree(np.column_stack([xs, ys]))
        ref._tree = tree  # type: ignore[attr-defined]
        if "speed_kph" in lap:
            s_lap, _ = ref.project(lap["x_m"].to_numpy(), lap["y_m"].to_numpy())
            for name, col in (("speed", "speed_kph"), ("throttle", "throttle_pct"), ("brake", "brake"), ("gear", "gear"),
                              ("time", "time_s")):
                if col in lap:
                    vals = lap[col].to_numpy(dtype=float)
                    setattr(ref, name, np.interp(s, s_lap, vals))
        return ref

    def tree(self) -> cKDTree:
        t = getattr(self, "_tree", None)
        if t is None:
            t = cKDTree(np.column_stack([self.x, self.y]))
            self._tree = t
        return t

    def project(self, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Distance along the reference for each sample of one lap (in lap order) and the lateral offset.

        Start/finish wrap is resolved: samples at the very start that snap to the end of the path are
        shifted by -length and vice versa, then the result is made non-decreasing.
        """
        d, idx = self.tree().query(np.column_stack([x, y]))
        s = self.s[idx].astype(float)
        n = len(s)
        head, tail = slice(0, max(1, n // 10)), slice(n - max(1, n // 10), n)
        s[head] = np.where(s[head] > 0.8 * self.length, s[head] - self.length, s[head])
        s[tail] = np.where(s[tail] < 0.2 * self.length, s[tail] + self.length, s[tail])
        s = np.maximum.accumulate(s)
        return s, d

    def project_guided(self, x: np.ndarray, y: np.ndarray, distance: np.ndarray, window_m: float = 150.0,
                       total: float | None = None, monotonic: bool = True) -> tuple[np.ndarray, np.ndarray]:
        """Projection constrained to +-window_m around the lap's own (rescaled) integrated distance.

        Plain nearest-point snapping jumps between branches where a circuit crosses itself or runs
        close to itself (e.g. Suzuka's crossover). The integrated distance drifts by ~1% at most, so it
        is a reliable guide for *where* to look, while the snapping supplies the precise position.
        """
        dist = np.asarray(distance, dtype=float)
        if total is not None:
            guess = dist * (self.length / total)
        else:
            span = dist[-1] - dist[0]
            guess = (dist - dist[0]) * (self.length / span) if span > 0 else dist
        step = self.s[1] - self.s[0]
        n_grid = len(self.s)
        w = int(window_m / step)
        offsets = np.arange(-w, w + 1)
        gi = np.rint(guess / step).astype(int)
        cand = (gi[:, None] + offsets[None, :])
        cand_wrapped = np.mod(cand, n_grid)
        dx = self.x[cand_wrapped] - np.asarray(x)[:, None]
        dy = self.y[cand_wrapped] - np.asarray(y)[:, None]
        d2 = dx * dx + dy * dy
        best = np.argmin(d2, axis=1)
        idx = cand[np.arange(len(gi)), best]
        s = (idx * step).astype(float)  # may be slightly negative / beyond length near the line: keeps lap order
        if monotonic:
            s = np.maximum.accumulate(s)
        return s, np.sqrt(d2[np.arange(len(gi)), best])

    def at(self, s_query: np.ndarray | float, attr: str) -> np.ndarray:
        arr = getattr(self, attr)
        return np.interp(np.mod(s_query, self.length), self.s, arr)
