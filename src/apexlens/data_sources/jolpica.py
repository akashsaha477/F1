"""Jolpica-F1 adapter (Ergast-compatible API, https://github.com/jolpica/jolpica-f1).

Handles ``limit``/``offset`` pagination using ``MRData.total`` and converts responses to tidy
DataFrames. Rate limiting is enforced by the shared HttpClient's RateLimiter; the defaults in
:func:`jolpica_rate_limiter` follow the provider's published guidance (burst of a few requests per
second, a few hundred per hour) and should be re-checked against the current documentation.
"""

from __future__ import annotations

import pandas as pd

from apexlens.data_sources.http import HttpClient, RateLimiter

PAGE_LIMIT = 100


def jolpica_rate_limiter() -> RateLimiter:
    return RateLimiter(min_interval_s=0.25, max_per_window=500, window_s=3600.0)


class JolpicaSource:
    provider = "jolpica"

    def __init__(self, http: HttpClient, base_url: str):
        self.http = http
        self.base = base_url.rstrip("/")

    def _pages(self, path: str, table_key: str, list_key: str) -> list[dict]:
        out: list[dict] = []
        offset = 0
        while True:
            res = self.http.get(f"{self.base}/{path.strip('/')}/", params={"limit": PAGE_LIMIT, "offset": offset})
            if not res.ok:
                raise RuntimeError(f"Jolpica request failed for {path}: {res.error}")
            mr = res.json()["MRData"]
            table = mr.get(table_key, {})
            items = table.get(list_key, [])
            out.extend(items)
            total = int(mr.get("total", 0))
            offset += int(mr.get("limit", PAGE_LIMIT))
            if offset >= total or not items:
                return out

    def races(self, season: int) -> pd.DataFrame:
        races = self._pages(f"{season}/races", "RaceTable", "Races")
        return pd.DataFrame([{
            "season": int(r["season"]), "round": int(r["round"]), "race_name": r["raceName"],
            "circuit_ref": r["Circuit"]["circuitId"], "date": r.get("date"), "time": r.get("time"),
        } for r in races])

    def results(self, season: int, round_: int | None = None) -> pd.DataFrame:
        path = f"{season}/{round_}/results" if round_ else f"{season}/results"
        races = self._pages(path, "RaceTable", "Races")
        rows = []
        for r in races:
            for res in r.get("Results", []):
                rows.append({
                    "season": int(r["season"]), "round": int(r["round"]),
                    "driver_ref": res["Driver"]["driverId"], "driver_code": res["Driver"].get("code"),
                    "driver_number": res.get("number"), "constructor_ref": res["Constructor"]["constructorId"],
                    "position_text": res.get("positionText"),
                    "position": int(res["position"]) if str(res.get("position", "")).isdigit() else None,
                    "grid": int(res["grid"]) if str(res.get("grid", "")).isdigit() else None,
                    "laps": int(res["laps"]) if str(res.get("laps", "")).isdigit() else None,
                    "status": res.get("status"), "points": float(res.get("points", 0)),
                    "family_name": res["Driver"].get("familyName"),
                    "date_of_birth": res["Driver"].get("dateOfBirth"),
                })
        return pd.DataFrame(rows)

    def pit_stops(self, season: int, round_: int) -> pd.DataFrame:
        races = self._pages(f"{season}/{round_}/pitstops", "RaceTable", "Races")
        rows = []
        for r in races:
            for p in r.get("PitStops", []):
                rows.append({"season": season, "round": round_, "driver_ref": p["driverId"], "stop": int(p["stop"]),
                             "lap": int(p["lap"]), "duration": p.get("duration")})
        return pd.DataFrame(rows)

    def drivers(self, season: int) -> pd.DataFrame:
        drivers = self._pages(f"{season}/drivers", "DriverTable", "Drivers")
        return pd.DataFrame([{
            "driver_ref": d["driverId"], "code": d.get("code"), "permanent_number": d.get("permanentNumber"),
            "given_name": d.get("givenName"), "family_name": d.get("familyName"), "date_of_birth": d.get("dateOfBirth"),
        } for d in drivers])
