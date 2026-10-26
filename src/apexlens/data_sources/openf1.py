"""OpenF1 adapter (https://openf1.org/docs/).

OpenF1 exposes flat JSON arrays filtered by query parameters (``session_key``, ``driver_number``,
...). Responses are cached by the shared HttpClient, so repeated requests for the same historical
session do not hit the provider again. OpenF1 is an independent, unofficial provider; review its
current terms before public or commercial deployment.
"""

from __future__ import annotations

import pandas as pd

from apexlens.data_sources.http import HttpClient, RateLimiter

ENDPOINTS = {
    "sessions", "meetings", "drivers", "laps", "stints", "weather", "pit", "race_control",
    "position", "intervals", "overtakes", "car_data", "location", "session_result", "starting_grid",
}


def openf1_rate_limiter() -> RateLimiter:
    return RateLimiter(min_interval_s=0.34, max_per_window=None)


class OpenF1Source:
    provider = "openf1"

    def __init__(self, http: HttpClient, base_url: str):
        self.http = http
        self.base = base_url.rstrip("/")

    def get(self, endpoint: str, **params) -> pd.DataFrame:
        if endpoint not in ENDPOINTS:
            raise ValueError(f"unsupported OpenF1 endpoint: {endpoint}")
        clean = {k: v for k, v in params.items() if v is not None}
        res = self.http.get(f"{self.base}/{endpoint}", params=clean or None)
        if res.status == 404:
            return pd.DataFrame()
        if not res.ok:
            raise RuntimeError(f"OpenF1 request failed for {endpoint}: {res.error}")
        data = res.json()
        if isinstance(data, dict):  # error payloads are objects, data payloads are arrays
            raise RuntimeError(f"OpenF1 returned an error for {endpoint}: {data}")
        return pd.DataFrame(data)

    def sessions(self, year: int, session_type: str | None = None) -> pd.DataFrame:
        return self.get("sessions", year=year, session_type=session_type)

    def overtakes(self, session_key: int) -> pd.DataFrame:
        return self.get("overtakes", session_key=session_key)

    def stints(self, session_key: int) -> pd.DataFrame:
        return self.get("stints", session_key=session_key)

    def laps(self, session_key: int, driver_number: int | None = None) -> pd.DataFrame:
        return self.get("laps", session_key=session_key, driver_number=driver_number)

    def weather(self, session_key: int) -> pd.DataFrame:
        return self.get("weather", session_key=session_key)

    def race_control(self, session_key: int) -> pd.DataFrame:
        return self.get("race_control", session_key=session_key)
