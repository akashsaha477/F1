"""Data-quality checks with configurable thresholds.

Each check returns a :class:`CheckResult`. ``fatal`` failures mark a partition as unusable for
modelling (downstream stages skip it); ``warning`` failures are reported but the data is kept.
Extreme values are flagged, never silently deleted — an extreme lap can be a genuine incident.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np
import pandas as pd

DEFAULT_THRESHOLDS = {
    "lap_time_min_s": 40.0,
    "lap_time_max_s": 600.0,
    "sector_sum_tolerance_s": 0.5,
    "max_unresolved_driver_frac": 0.02,
    "speed_max_kph": 400.0,
    "throttle_max": 100.0,
    "throttle_tolerance": 5.0,
    "gear_max": 8,
    "max_sample_gap_s": 1.0,
    "max_coordinate_jump_m": 60.0,
    "track_temp_range_c": (-10.0, 75.0),
    "air_temp_range_c": (-15.0, 55.0),
}


@dataclass
class CheckResult:
    name: str
    severity: str  # "fatal" | "warning"
    n_failed: int
    n_total: int
    passed: bool
    detail: str = ""
    examples: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _result(name, severity, mask, n_total, detail="", examples_df=None, allowed=0) -> CheckResult:
    n_failed = int(np.asarray(mask, dtype=bool).sum()) if mask is not None else 0
    ex = []
    if examples_df is not None and n_failed:
        ex = examples_df[np.asarray(mask, dtype=bool)].head(3).astype(str).to_dict("records")
    return CheckResult(name, severity, n_failed, int(n_total), n_failed <= allowed, detail, ex)


def validate_laps(df: pd.DataFrame, thresholds: dict | None = None) -> list[CheckResult]:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    n = len(df)
    res: list[CheckResult] = []
    key = ["session_id", "driver_number", "lap_number"]
    dup = df.duplicated(key, keep=False) & df["lap_number"].notna()
    res.append(_result("duplicate_laps", "fatal", dup, n, "same session/car/lap appears more than once", df[key]))
    res.append(_result("non_positive_lap_time", "fatal", df["lap_time_s"] <= 0, n, "", df[key + ["lap_time_s"]]))
    lt = df["lap_time_s"]
    implaus = lt.notna() & ((lt < t["lap_time_min_s"]) | (lt > t["lap_time_max_s"]))
    res.append(_result("implausible_lap_time", "warning", implaus, n,
                       f"outside [{t['lap_time_min_s']}, {t['lap_time_max_s']}] s", df[key + ["lap_time_s"]]))
    ssum = df["sector1_s"] + df["sector2_s"] + df["sector3_s"]
    mism = ssum.notna() & lt.notna() & ((ssum - lt).abs() > t["sector_sum_tolerance_s"])
    res.append(_result("sector_sum_mismatch", "warning", mism, n, "", df[key + ["lap_time_s"]]))
    srt = df.sort_values(["session_id", "driver_number", "lap_number"])
    dec = srt.groupby(["session_id", "driver_number", "stint"], dropna=True)["tyre_life_laps"].diff() < 0
    res.append(_result("tyre_life_decreasing_in_stint", "warning", dec.reindex(df.index).fillna(False), n))
    tdiff = srt.groupby(["session_id", "driver_number"])["session_time_end_s"].diff() <= 0
    res.append(_result("session_time_not_increasing", "warning", tdiff.reindex(df.index).fillna(False), n))
    unresolved = df["driver_id"].isna()
    allowed = int(np.floor(t["max_unresolved_driver_frac"] * n))
    res.append(_result("unresolved_driver_identity", "fatal", unresolved, n,
                       f"allowed up to {t['max_unresolved_driver_frac']:.0%}", df[["driver_number", "driver_abbr"]],
                       allowed=allowed))
    multi_team = df.groupby(["session_id", "driver_id"])["constructor_id"].transform("nunique") > 1
    res.append(_result("driver_with_multiple_constructors_in_session", "fatal", multi_team, n))
    res.append(_result("missing_lap_start_timestamp", "warning", df["lap_start_utc"].isna(), n))
    for c in ["speed_i1_kph", "speed_i2_kph", "speed_fl_kph", "speed_st_kph"]:
        v = df[c]
        res.append(_result(f"implausible_{c}", "warning", v.notna() & ((v < 0) | (v > t["speed_max_kph"])), n))
    pos = df["position"].astype(float)
    res.append(_result("position_out_of_range", "warning", pos.notna() & ((pos < 1) | (pos > 30)), n))
    lo, hi = t["track_temp_range_c"]
    tt = df["track_temp_c"]
    res.append(_result("implausible_track_temp", "warning", tt.notna() & ((tt < lo) | (tt > hi)), n))
    if "session_id" in df.columns:
        res.append(_result("mixed_sessions_in_partition", "fatal",
                           np.zeros(n, dtype=bool) if df["session_id"].nunique() <= 1 else np.ones(n, dtype=bool), n))
    return res


def validate_weather(df: pd.DataFrame, thresholds: dict | None = None) -> list[CheckResult]:
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    n = len(df)
    lo, hi = t["air_temp_range_c"]
    res = [
        _result("implausible_air_temp", "warning", df["air_temp_c"].notna() & ((df["air_temp_c"] < lo) | (df["air_temp_c"] > hi)), n),
        _result("humidity_out_of_range", "warning", df["humidity_pct"].notna() & ((df["humidity_pct"] < 0) | (df["humidity_pct"] > 100)), n),
        _result("weather_time_not_increasing", "warning", df["session_time_s"].diff() <= 0, n),
    ]
    return res


def validate_telemetry(df: pd.DataFrame, thresholds: dict | None = None) -> list[CheckResult]:
    """Checks for silver telemetry (one or several laps identified by ``lap_key``)."""
    t = {**DEFAULT_THRESHOLDS, **(thresholds or {})}
    n = len(df)
    res = []
    gear = df["gear"]
    res.append(_result("invalid_gear", "warning", gear.notna() & ((gear < 0) | (gear > t["gear_max"])), n))
    thr = df["throttle_pct"]
    res.append(_result("throttle_out_of_range", "warning",
                       thr.notna() & ((thr < 0) | (thr > t["throttle_max"] + t["throttle_tolerance"])), n))
    sp = df["speed_kph"]
    res.append(_result("implausible_speed", "warning", sp.notna() & ((sp < 0) | (sp > t["speed_max_kph"])), n))
    group = df["lap_key"] if "lap_key" in df.columns else pd.Series(0, index=df.index)
    dt = df.groupby(group)["time_s"].diff()
    res.append(_result("time_not_increasing", "fatal", dt < 0, n))
    res.append(_result("sample_gap", "warning", dt > t["max_sample_gap_s"], n, f"> {t['max_sample_gap_s']} s"))
    if {"x_m", "y_m"}.issubset(df.columns):
        step = np.hypot(df.groupby(group)["x_m"].diff(), df.groupby(group)["y_m"].diff())
        expected = (sp / 3.6) * dt.fillna(0)
        jump = step > (expected * 3 + t["max_coordinate_jump_m"])
        res.append(_result("coordinate_discontinuity", "warning", jump.fillna(False), n))
        res.append(_result("missing_position", "warning", df[["x_m", "y_m"]].isna().any(axis=1), n))
    else:
        res.append(_result("missing_position", "warning", np.ones(n, dtype=bool), n, "no position channels"))
    return res


def summarize(results: list[CheckResult]) -> dict:
    fatal = [r.name for r in results if r.severity == "fatal" and not r.passed]
    warnings = [r.name for r in results if r.severity == "warning" and not r.passed]
    return {"status": "failed" if fatal else ("warning" if warnings else "ok"), "fatal": fatal, "warnings": warnings,
            "checks": [r.to_dict() for r in results]}
