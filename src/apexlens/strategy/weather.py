"""Race-week weather: what was measured during the weekend, what is normal at the circuit, and (for upcoming
races) the provider forecast. The planner's scenario uses, in order of preference: user values, the forecast,
the weekend's sessions before the race, the circuit's history.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from apexlens.strategy.data import StrategyData

RAIN_RISK_HIGH = 0.5


def _summary(obs: pd.DataFrame) -> dict:
    if obs.empty:
        return {}
    rain = obs["rainfall"].astype("boolean").fillna(False).astype(bool)
    return {"air_temp_c": float(obs["air_temp_c"].mean()), "track_temp_c": float(obs["track_temp_c"].mean()),
            "humidity_pct": float(obs["humidity_pct"].mean()), "rain_share": float(rain.mean()), "samples": int(len(obs))}


def weekend_sessions(data: StrategyData, event_id: str) -> list[dict]:
    """Every session of the weekend before the race, with its measured weather."""
    s = data.sessions[(data.sessions["event_id"] == event_id) & (data.sessions["session_code"] != "R")].sort_values("start")
    out = []
    for r in s.itertuples():
        w = _summary(data.weather[data.weather["session_id"] == r.session_id])
        out.append({"session_id": r.session_id, "session_code": r.session_code,
                    "start_utc": r.start.isoformat() if pd.notna(r.start) else None, **w})
    return out


def race_weather(data: StrategyData, event_id: str) -> dict:
    return _summary(data.weather[data.weather["session_id"] == f"{event_id}-R"])


def climatology(data: StrategyData, circuit_id: str, before: pd.Timestamp) -> dict:
    races = data.races[(data.races["circuit_id"] == circuit_id) & (data.races["date"] < before)]
    rows = [race_weather(data, e) | {"season": int(s)} for e, s in zip(races["event_id"], races["season"], strict=True)]
    rows = [r for r in rows if "air_temp_c" in r]
    if not rows:
        return {"races": 0}
    df = pd.DataFrame(rows)
    return {"races": int(len(df)), "seasons": sorted(df["season"].tolist()),
            "air_temp_c": float(df["air_temp_c"].median()), "track_temp_c": float(df["track_temp_c"].median()),
            "track_temp_range_c": [float(df["track_temp_c"].min()), float(df["track_temp_c"].max())],
            "humidity_pct": float(df["humidity_pct"].median()),
            "rain_race_share": float((df["rain_share"] > 0.05).mean()),
            "track_minus_air_c": float((df["track_temp_c"] - df["air_temp_c"]).median())}


def scenario(weekend: list[dict], clim: dict, forecast: dict | None, overrides: dict) -> dict:
    """Weather assumed for the race, with the source of each value."""
    measured = [w for w in weekend if "air_temp_c" in w]
    out, source = {}, {}
    for key in ("track_temp_c", "air_temp_c", "humidity_pct"):
        if overrides.get(key) is not None:
            out[key], source[key] = float(overrides[key]), "your input"
        elif forecast and forecast.get("air_temp_c") is not None and key != "track_temp_c" and forecast.get(key) is not None:
            out[key], source[key] = float(forecast[key]), "forecast"
        elif forecast and forecast.get("air_temp_c") is not None and key == "track_temp_c" and "track_minus_air_c" in clim:
            out[key], source[key] = float(forecast["air_temp_c"] + clim["track_minus_air_c"]), \
                "forecast air temperature + the circuit's usual track-air difference"
        elif measured:
            out[key], source[key] = float(np.mean([w[key] for w in measured])), "mean of this weekend's sessions"
        elif key in clim:
            out[key], source[key] = float(clim[key]), "circuit history (earlier races)"
    if overrides.get("rain") is not None:
        risk, rsrc = (1.0 if overrides["rain"] else 0.0), "your input"
    elif forecast and forecast.get("rain_probability_pct") is not None:
        risk, rsrc = forecast["rain_probability_pct"] / 100, "forecast precipitation probability"
    elif measured:
        risk = float(max(w["rain_share"] for w in measured) > 0.05)
        risk = max(risk, 0.5 * clim.get("rain_race_share", 0.0))
        rsrc = "rain in this weekend's sessions / circuit history"
    else:
        risk, rsrc = float(clim.get("rain_race_share", 0.0)), "share of earlier races here with rain"
    out["rain_risk"] = float(risk)
    source["rain_risk"] = rsrc
    out["wet_race_likely"] = bool(risk >= RAIN_RISK_HIGH)
    return {"values": out, "source": source}
