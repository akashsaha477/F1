"""Open-Meteo weather forecast adapter (https://open-meteo.com/en/docs), used for upcoming race weeks.

No API key; data licensed CC BY 4.0 (attribution: Open-Meteo.com). Forecasts are never cached (they change),
and only race starts within the provider's 16-day horizon are requested. The provider gives air
temperature, humidity and precipitation; track temperature is not forecast and is estimated by the caller.
"""

from __future__ import annotations

import pandas as pd

from apexlens.data_sources.http import HttpClient

HOURLY = "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation"
HORIZON_DAYS = 15


class OpenMeteoSource:
    provider = "open-meteo"

    def __init__(self, http: HttpClient, base_url: str):
        self.http = http
        self.base = base_url

    def race_forecast(self, latitude: float, longitude: float, start_utc: pd.Timestamp, duration_h: int = 2) -> dict:
        """Mean conditions over the race window, or ``{"error": ...}``."""
        start = pd.Timestamp(start_utc).tz_convert("UTC") if pd.Timestamp(start_utc).tzinfo else pd.Timestamp(start_utc, tz="UTC")
        now = pd.Timestamp.now(tz="UTC")
        if start < now - pd.Timedelta(hours=3) or start > now + pd.Timedelta(days=HORIZON_DAYS):
            return {"error": f"race start {start.date()} is outside the forecast horizon"}
        params = {"latitude": latitude, "longitude": longitude, "hourly": HOURLY, "timezone": "UTC",
                  "start_date": str(start.date()), "end_date": str((start + pd.Timedelta(hours=duration_h)).date())}
        res = self.http.get(self.base, params=params, use_cache=False)
        if not res.ok:
            return {"error": f"forecast unavailable ({res.error or res.status})"}
        h = res.json().get("hourly") or {}
        df = pd.DataFrame(h)
        if df.empty or "time" not in df:
            return {"error": "forecast response without hourly data"}
        df["time"] = pd.to_datetime(df["time"], utc=True)
        win = df[(df["time"] >= start.floor("h")) & (df["time"] <= start + pd.Timedelta(hours=duration_h))]
        if win.empty:
            return {"error": "forecast does not cover the race window"}
        return {
            "source": "Open-Meteo forecast", "retrieved_at": now.isoformat(timespec="minutes"),
            "air_temp_c": float(win["temperature_2m"].mean()),
            "humidity_pct": float(win["relative_humidity_2m"].mean()) if "relative_humidity_2m" in win else None,
            "rain_probability_pct": float(win["precipitation_probability"].max()) if "precipitation_probability" in win else None,
            "precipitation_mm": float(win["precipitation"].sum()) if "precipitation" in win else None,
        }
