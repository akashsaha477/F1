"""Normalisation of lap timing to the silver ``laps`` schema and lap-validity flags.

Input is a *FastF1 lap frame*: FastF1 column names with durations in seconds. Both the FastF1
adapter and the TracingInsights archive are converted to this frame first.

No lap is ever deleted here. Laps that should not be used for representative-pace analysis keep
their original labels and receive ``is_clean = False`` plus an ``exclusion_reason``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from apexlens.cleaning.parsing import (
    WET_COMPOUNDS,
    normalize_compound,
    series_to_float,
    series_to_nullable_bool,
)

# TracingInsights compact keys -> FastF1 column names.
TI_LAP_KEYS = {
    "time": "LapTime", "lap": "LapNumber", "compound": "Compound", "stint": "Stint",
    "s1": "Sector1Time", "s2": "Sector2Time", "s3": "Sector3Time", "life": "TyreLife", "pos": "Position",
    "status": "TrackStatus", "pb": "IsPersonalBest", "sesT": "Time", "drv": "Driver", "dNum": "DriverNumber",
    "pout": "PitOutTime", "pin": "PitInTime", "s1T": "Sector1SessionTime", "s2T": "Sector2SessionTime",
    "s3T": "Sector3SessionTime", "vi1": "SpeedI1", "vi2": "SpeedI2", "vfl": "SpeedFL", "vst": "SpeedST",
    "fresh": "FreshTyre", "team": "Team", "lST": "LapStartTime", "lSD": "LapStartDate", "del": "Deleted",
    "delR": "DeletedReason", "ff1G": "FastF1Generated", "iacc": "IsAccurate", "qs": "QualifyingSession",
    "wT": "WeatherTime", "wAT": "AirTemp", "wH": "Humidity", "wP": "Pressure", "wR": "Rainfall",
    "wTT": "TrackTemp", "wWD": "WindDirection", "wWS": "WindSpeed",
}
TI_WEATHER_KEYS = {"wT": "Time", "wAT": "AirTemp", "wH": "Humidity", "wP": "Pressure", "wR": "Rainfall",
                   "wTT": "TrackTemp", "wWD": "WindDirection", "wWS": "WindSpeed"}

FLOAT_COLS = ["LapTime", "Sector1Time", "Sector2Time", "Sector3Time", "TyreLife", "Position", "Time", "PitOutTime",
              "PitInTime", "Sector1SessionTime", "Sector2SessionTime", "Sector3SessionTime", "SpeedI1", "SpeedI2",
              "SpeedFL", "SpeedST", "LapStartTime", "WeatherTime", "AirTemp", "Humidity", "Pressure", "TrackTemp",
              "WindDirection", "WindSpeed", "LapNumber", "Stint"]
BOOL_COLS = ["IsPersonalBest", "FreshTyre", "Deleted", "FastF1Generated", "IsAccurate", "Rainfall"]

SESSION_TYPES = {"FP1": "practice", "FP2": "practice", "FP3": "practice", "Q": "qualifying",
                 "SQ": "sprint_qualifying", "S": "sprint", "R": "race"}

# FastF1 TrackStatus codes.
TRACK_STATUS = {"1": "green", "2": "yellow", "3": "unknown_3", "4": "safety_car", "5": "red", "6": "vsc",
                "7": "vsc_ending"}


def columnar_to_frame(d: dict, key_map: dict[str, str]) -> pd.DataFrame:
    n = max((len(v) for v in d.values() if isinstance(v, list)), default=0)
    cols = {key_map.get(k, k): v for k, v in d.items() if isinstance(v, list) and len(v) == n}
    return pd.DataFrame(cols)


def tracinginsights_laps_to_frame(payload: dict) -> pd.DataFrame:
    df = columnar_to_frame(payload, TI_LAP_KEYS)
    for c in FLOAT_COLS:
        if c in df.columns:
            df[c] = series_to_float(df[c])
    for c in BOOL_COLS:
        if c in df.columns:
            df[c] = series_to_nullable_bool(df[c])
    for c in ["Driver", "DriverNumber", "Compound", "TrackStatus", "Team", "DeletedReason", "LapStartDate",
              "QualifyingSession"]:
        if c in df.columns:
            df[c] = df[c].astype(object).where(~df[c].astype(str).str.lower().isin(["none", "nan", ""]), None)
    return df


def tracinginsights_weather_to_frame(payload: dict) -> pd.DataFrame:
    df = columnar_to_frame(payload, TI_WEATHER_KEYS)
    for c in df.columns:
        if c == "Rainfall":
            df[c] = series_to_nullable_bool(df[c])
        else:
            df[c] = series_to_float(df[c])
    return df


def tracinginsights_rcm_to_frame(payload: dict) -> pd.DataFrame:
    df = columnar_to_frame(payload, {"time": "Time", "cat": "Category", "msg": "Message", "status": "Status",
                                     "flag": "Flag", "scope": "Scope", "sector": "Sector", "dNum": "RacingNumber",
                                     "lap": "Lap"})
    for c in df.columns:
        df[c] = df[c].astype(object).where(~df[c].astype(str).isin(["None", "nan", ""]), None)
    return df


CORNER_KEYS = {"CornerNumber": "Number", "X": "X", "Y": "Y", "Angle": "Angle", "Distance": "Distance",
               "CornerLetter": "Letter", "Letter": "Letter", "SectionType": "SectionType"}


def tracinginsights_corners_to_frame(payload: dict) -> tuple[pd.DataFrame, float | None]:
    """Corner markers. Newer files also carry longer arrays (track outline, marshal sectors), so only the
    arrays as long as ``CornerNumber`` are taken."""
    rotation = payload.get("Rotation")
    n = len(payload.get("CornerNumber", []))
    cols = {CORNER_KEYS[k]: v for k, v in payload.items() if k in CORNER_KEYS and isinstance(v, list) and len(v) == n}
    df = pd.DataFrame(cols)
    if "Letter" not in df.columns:
        df["Letter"] = ""
    return df, (float(rotation) if rotation is not None else None)


def track_status_flags(status) -> dict[str, bool]:
    s = "" if status is None or (isinstance(status, float) and np.isnan(status)) else str(status)
    s = s.replace(".0", "")
    return {
        "status_known": bool(s),
        "flag_green_only": bool(s) and set(s) <= {"1"},
        "flag_yellow": "2" in s,
        "flag_sc": "4" in s,
        "flag_red": "5" in s,
        "flag_vsc": ("6" in s) or ("7" in s),
    }


def lap_condition(compound: str, rainfall) -> str:
    if compound in WET_COMPOUNDS:
        return "wet"
    if compound in {"SOFT", "MEDIUM", "HARD", "LEGACY_SLICK"}:
        if rainfall is True:
            return "damp"
        if rainfall is False:
            return "dry"
        return "dry_unverified"
    return "unknown"


def normalize_laps(frame: pd.DataFrame, ctx: dict, resolver=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert a FastF1 lap frame to the silver ``laps`` schema.

    ``ctx`` keys: session_id, event_id, season, round, session_code, circuit_id, source.
    Returns (laps, mapping_report).
    """
    f = frame.copy()
    n = len(f)

    def col(name, default=np.nan):
        return f[name] if name in f.columns else pd.Series([default] * n, index=f.index)

    out = pd.DataFrame({
        "session_id": ctx["session_id"], "event_id": ctx["event_id"], "season": int(ctx["season"]),
        "round": int(ctx["round"]), "session_code": ctx["session_code"],
        "session_type": SESSION_TYPES.get(ctx["session_code"], "other"), "circuit_id": ctx.get("circuit_id"),
        "driver_abbr": col("Driver", None), "driver_number": col("DriverNumber", None).astype(object),
        "team_name": col("Team", None),
        "lap_number": pd.to_numeric(col("LapNumber"), errors="coerce").astype("Int64"),
        "lap_time_s": col("LapTime"), "sector1_s": col("Sector1Time"), "sector2_s": col("Sector2Time"),
        "sector3_s": col("Sector3Time"), "session_time_end_s": col("Time"), "lap_start_time_s": col("LapStartTime"),
        "lap_start_utc": pd.to_datetime(col("LapStartDate", None), errors="coerce", utc=True),
        "sector1_session_time_s": col("Sector1SessionTime"), "sector2_session_time_s": col("Sector2SessionTime"),
        "sector3_session_time_s": col("Sector3SessionTime"), "pit_in_time_s": col("PitInTime"),
        "pit_out_time_s": col("PitOutTime"), "speed_i1_kph": col("SpeedI1"), "speed_i2_kph": col("SpeedI2"),
        "speed_fl_kph": col("SpeedFL"), "speed_st_kph": col("SpeedST"),
        "compound_raw": col("Compound", None), "tyre_life_laps": col("TyreLife"),
        "fresh_tyre": col("FreshTyre", pd.NA).astype("boolean"),
        "stint": pd.to_numeric(col("Stint"), errors="coerce").astype("Int64"),
        "position": pd.to_numeric(col("Position"), errors="coerce").astype("Int64"),
        "track_status": col("TrackStatus", None),
        "is_personal_best": col("IsPersonalBest", pd.NA).astype("boolean"),
        "deleted": col("Deleted", pd.NA).astype("boolean"), "deleted_reason": col("DeletedReason", None),
        "fastf1_generated": col("FastF1Generated", pd.NA).astype("boolean"),
        "is_accurate": col("IsAccurate", pd.NA).astype("boolean"),
        "quali_segment": col("QualifyingSession", None),
        "weather_time_s": col("WeatherTime"), "air_temp_c": col("AirTemp"), "track_temp_c": col("TrackTemp"),
        "humidity_pct": col("Humidity"), "pressure_mbar": col("Pressure"),
        "rainfall": col("Rainfall", pd.NA).astype("boolean"), "wind_dir_deg": col("WindDirection"),
        "wind_speed_ms": col("WindSpeed"), "source": ctx.get("source"),
    })
    for c in ["lap_time_s", "sector1_s", "sector2_s", "sector3_s", "tyre_life_laps", "air_temp_c", "track_temp_c"]:
        out[c] = pd.to_numeric(out[c], errors="coerce").astype(float)
    out["compound"] = out["compound_raw"].map(normalize_compound)

    # identity resolution
    report_rows = []
    driver_ids, cons_ids, methods = [], [], []
    cache: dict[tuple, object] = {}
    for num, abbr in zip(out["driver_number"], out["driver_abbr"], strict=True):
        key = (num, abbr)
        if key not in cache:
            if resolver is None:
                cache[key] = None
            else:
                cache[key] = resolver.resolve(ctx["event_id"], int(ctx["season"]), ctx["session_code"], num, abbr)
                r = cache[key]
                report_rows.append({"session_id": ctx["session_id"], "driver_number": num, "driver_abbr": abbr,
                                    "driver_id": r.driver_id, "constructor_id": r.constructor_id, "method": r.method})
        r = cache[key]
        driver_ids.append(getattr(r, "driver_id", None))
        cons_ids.append(getattr(r, "constructor_id", None))
        methods.append(getattr(r, "method", "not_resolved"))
    out.insert(6, "driver_id", driver_ids)
    out.insert(7, "constructor_id", cons_ids)
    out["identity_method"] = methods

    out = add_lap_flags(out)
    return out, pd.DataFrame(report_rows)


def add_lap_flags(out: pd.DataFrame) -> pd.DataFrame:
    flags = pd.DataFrame([track_status_flags(s) for s in out["track_status"]], index=out.index)
    out = pd.concat([out.drop(columns=[c for c in flags.columns if c in out.columns]), flags], axis=1)
    out["is_pit_in_lap"] = out["pit_in_time_s"].notna()
    out["is_pit_out_lap"] = out["pit_out_time_s"].notna()
    out["is_first_lap"] = (out["lap_number"] == 1) & out["session_type"].isin(["race", "sprint"])
    out["is_wet_compound"] = out["compound"].isin(WET_COMPOUNDS)
    rain = out["rainfall"].astype(object).where(out["rainfall"].notna(), None)
    out["condition"] = [lap_condition(c, r) for c, r in zip(out["compound"], rain, strict=True)]

    reasons = pd.Series([None] * len(out), index=out.index, dtype=object)

    def mark(mask, reason):
        nonlocal reasons
        m = mask.fillna(False).astype(bool) & reasons.isna()
        reasons = reasons.mask(m, reason)

    mark(out["lap_time_s"].isna(), "no_lap_time")
    mark(out["lap_time_s"] <= 0, "non_positive_lap_time")
    mark(out["driver_id"].isna(), "unresolved_driver")
    mark(~out["status_known"], "unknown_track_status")
    mark(out["flag_red"], "red_flag")
    mark(out["flag_sc"], "safety_car")
    mark(out["flag_vsc"], "virtual_safety_car")
    mark(out["flag_yellow"], "yellow_flag")
    mark(out["is_pit_in_lap"], "pit_in_lap")
    mark(out["is_pit_out_lap"], "pit_out_lap")
    mark(out["is_first_lap"], "race_start_lap")
    mark(out["deleted"].fillna(False).astype(bool), "deleted")
    mark(out["fastf1_generated"].fillna(False).astype(bool), "fastf1_generated")
    mark(~out["is_accurate"].fillna(False).astype(bool), "not_accurate")
    mark(out["compound"].isin(["UNKNOWN"]), "unknown_compound")
    out["exclusion_reason"] = reasons
    out["is_clean"] = reasons.isna()
    return out
