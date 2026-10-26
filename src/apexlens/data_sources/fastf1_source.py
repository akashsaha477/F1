"""FastF1 adapter (https://docs.fastf1.dev/).

Loads a session through the FastF1 library and converts it to the *FastF1 lap frame* used across
ApexLens: FastF1 column names with all durations expressed in seconds. The TracingInsights archive
is converted to the same frame, so both sources share one normaliser.

FastF1 is an optional dependency (``pip install apexlens[fastf1]``). Its backend
(livetiming.formula1.com) must be reachable for this adapter to fetch data.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

LAP_DURATION_COLUMNS = [
    "Time", "LapTime", "PitOutTime", "PitInTime", "Sector1Time", "Sector2Time", "Sector3Time",
    "Sector1SessionTime", "Sector2SessionTime", "Sector3SessionTime", "LapStartTime",
]
LAP_COLUMNS = LAP_DURATION_COLUMNS + [
    "Driver", "DriverNumber", "LapNumber", "Stint", "SpeedI1", "SpeedI2", "SpeedFL", "SpeedST",
    "IsPersonalBest", "Compound", "TyreLife", "FreshTyre", "Team", "LapStartDate", "TrackStatus",
    "Position", "Deleted", "DeletedReason", "FastF1Generated", "IsAccurate",
]
WEATHER_COLUMNS = ["AirTemp", "Humidity", "Pressure", "Rainfall", "TrackTemp", "WindDirection", "WindSpeed"]

SESSION_NAMES = {"FP1": "Practice 1", "FP2": "Practice 2", "FP3": "Practice 3", "Q": "Qualifying",
                 "SQ": "Sprint Qualifying", "S": "Sprint", "R": "Race"}


@dataclass
class SessionPayload:
    """Source-independent representation of one session in FastF1 conventions (seconds)."""

    laps: pd.DataFrame
    weather: pd.DataFrame
    messages: pd.DataFrame
    corners: pd.DataFrame | None = None
    rotation: float | None = None
    drivers: list[dict] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


def timedelta_columns_to_seconds(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in columns:
        if c in df.columns and pd.api.types.is_timedelta64_dtype(df[c]):
            df[c] = df[c].dt.total_seconds()
    return df


class FastF1Source:
    provider = "fastf1"

    def __init__(self, cache_dir: Path, fastf1_module: Any = None):
        self.cache_dir = Path(cache_dir)
        self._ff1 = fastf1_module

    @property
    def ff1(self):
        if self._ff1 is None:
            try:
                import fastf1  # noqa: PLC0415
            except ImportError as exc:  # pragma: no cover - depends on environment
                raise RuntimeError("FastF1 is not installed: pip install 'apexlens[fastf1]'") from exc
            (self.cache_dir / "fastf1").mkdir(parents=True, exist_ok=True)
            fastf1.Cache.enable_cache(str(self.cache_dir / "fastf1"))
            self._ff1 = fastf1
        return self._ff1

    def load_session(self, season: int, event: str | int, session_code: str, telemetry: bool = False) -> SessionPayload:
        session = self.ff1.get_session(season, event, SESSION_NAMES.get(session_code, session_code))
        session.load(laps=True, telemetry=telemetry, weather=True, messages=True)
        laps = session.laps
        weather_per_lap = None
        try:
            weather_per_lap = laps.get_weather_data()
        except Exception as exc:  # noqa: BLE001 - FastF1 raises several error types for missing data
            log.warning("no per-lap weather for %s %s %s: %s", season, event, session_code, exc)
        lap_df = pd.DataFrame(laps)
        lap_df = timedelta_columns_to_seconds(lap_df, LAP_DURATION_COLUMNS)
        keep = [c for c in LAP_COLUMNS if c in lap_df.columns]
        lap_df = lap_df[keep].copy()
        if weather_per_lap is not None and len(weather_per_lap) == len(lap_df):
            w = pd.DataFrame(weather_per_lap).reset_index(drop=True)
            w = timedelta_columns_to_seconds(w, ["Time"])
            lap_df = lap_df.reset_index(drop=True)
            lap_df["WeatherTime"] = w.get("Time")
            for c in WEATHER_COLUMNS:
                if c in w.columns:
                    lap_df[c] = w[c].to_numpy()

        weather = timedelta_columns_to_seconds(pd.DataFrame(session.weather_data), ["Time"])
        messages = pd.DataFrame(getattr(session, "race_control_messages", pd.DataFrame()))
        corners, rotation = None, None
        try:
            ci = session.get_circuit_info()
            corners = pd.DataFrame(ci.corners)
            rotation = float(ci.rotation)
        except Exception as exc:  # noqa: BLE001
            log.warning("no circuit info for %s %s: %s", season, event, exc)
        drivers = []
        results = getattr(session, "results", None)
        if results is not None and len(results):
            for _, r in pd.DataFrame(results).iterrows():
                drivers.append({"driver": r.get("Abbreviation"), "dn": str(r.get("DriverNumber")),
                                "team": r.get("TeamName"), "fn": r.get("FirstName"), "ln": r.get("LastName")})
        try:
            event_name = str(session.event["EventName"])
        except (KeyError, TypeError, AttributeError):
            event_name = None
        return SessionPayload(laps=lap_df, weather=weather, messages=messages, corners=corners,
                              rotation=rotation, drivers=drivers, meta={"event_name": event_name})

    def lap_telemetry(self, session: Any, driver: str, lap_number: int) -> pd.DataFrame:
        lap = session.laps.pick_drivers(driver).pick_laps(lap_number).iloc[0]
        tel = lap.get_telemetry()
        df = pd.DataFrame(tel)
        if "SessionTime" in df.columns:
            df = timedelta_columns_to_seconds(df, ["SessionTime", "Time"])
        df = df.rename(columns={"Time": "time", "Speed": "speed", "RPM": "rpm", "nGear": "gear", "Throttle": "throttle",
                                "Brake": "brake", "DRS": "drs", "Distance": "distance", "X": "x", "Y": "y", "Z": "z"})
        if "brake" in df.columns:
            df["brake"] = df["brake"].astype(float)
        cols = [c for c in ["time", "rpm", "speed", "gear", "throttle", "brake", "drs", "distance", "x", "y", "z"]
                if c in df.columns]
        return df[cols].replace({np.inf: np.nan})
