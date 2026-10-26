"""Read-only query layer used by the API. Never exposes file paths or arbitrary query execution."""

from __future__ import annotations

import math
from functools import cached_property

import numpy as np
import pandas as pd

from apexlens.data_sources.registry import SOURCE_CATALOG, ProvenanceRegistry
from apexlens.features.definitions import FEATURES
from apexlens.storage.duckdb_store import DuckStore
from apexlens.storage.io import read_json, read_partition, read_table
from apexlens.storage.paths import DataPaths


def clean_value(v):
    if v is None:
        return None
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    if isinstance(v, (pd.Timestamp,)):
        return None if pd.isna(v) else v.isoformat()
    if v is pd.NA or v is pd.NaT:
        return None
    if isinstance(v, (list, tuple)):
        return [clean_value(x) for x in v]
    if isinstance(v, np.ndarray):
        return [clean_value(x) for x in v.tolist()]
    if isinstance(v, dict):
        return {k: clean_value(x) for k, x in v.items()}
    return v


def records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    return [{k: clean_value(v) for k, v in r.items()} for r in df.to_dict("records")]


def page(df: pd.DataFrame, limit: int, offset: int) -> dict:
    total = int(len(df))
    return {"items": records(df.iloc[offset: offset + limit]), "total": total, "limit": limit, "offset": offset}


class NotFound(LookupError):
    pass


class DataService:
    def __init__(self, paths: DataPaths):
        self.paths = paths
        self.duck = DuckStore(paths)

    # -- cached tables ---------------------------------------------------------------------
    @cached_property
    def events(self) -> pd.DataFrame:
        return read_table(self.paths.silver("events"))

    @cached_property
    def sessions(self) -> pd.DataFrame:
        return read_table(self.paths.silver("sessions"))

    @cached_property
    def drivers_tbl(self) -> pd.DataFrame:
        return read_table(self.paths.silver("drivers"))

    @cached_property
    def constructors_tbl(self) -> pd.DataFrame:
        return read_table(self.paths.silver("constructors"))

    @cached_property
    def circuits_tbl(self) -> pd.DataFrame:
        return read_table(self.paths.silver("circuits"))

    @cached_property
    def results(self) -> pd.DataFrame:
        return read_table(self.paths.silver("race_results"))

    @cached_property
    def quali(self) -> pd.DataFrame:
        return read_table(self.paths.silver("qualifying_results"))

    @cached_property
    def ingested(self) -> pd.DataFrame:
        return pd.DataFrame(read_json(self.paths.manifests / "sessions_ingested.json", default=[]))

    @cached_property
    def summary(self) -> pd.DataFrame:
        return read_table(self.paths.gold("driver_session_summary"))

    @cached_property
    def form(self) -> pd.DataFrame:
        return read_table(self.paths.gold("driver_event_form"))

    @cached_property
    def lap_seasons(self) -> list[int]:
        return sorted(int(s) for s in self.ingested["season"].unique()) if len(self.ingested) else []

    @cached_property
    def driver_index(self) -> pd.DataFrame:
        """One row per driver with career span and lap-data availability."""
        r = self.results[self.results["session_code"] == "R"]
        r = r.merge(self.events[["event_id", "date"]], on="event_id", how="left")
        g = r.sort_values("date").groupby("driver_id")
        idx = pd.DataFrame({
            "first_season": g["season"].min(), "last_season": g["season"].max(), "races": g.size(),
            "wins": g["position"].apply(lambda s: int((s == 1).sum())),
            "latest_constructor_id": g["constructor_id"].last(),
        }).reset_index()
        lap_drivers = set(self.summary["driver_id"].unique()) if "driver_id" in self.summary else set()
        idx["has_lap_data"] = idx["driver_id"].isin(lap_drivers)
        d = self.drivers_tbl[["driver_id", "name", "full_name", "abbreviation", "nationality_country_id", "date_of_birth",
                              "permanent_number"]]
        return idx.merge(d, on="driver_id", how="left")

    # -- catalogue -------------------------------------------------------------------------
    def seasons(self) -> list[dict]:
        ev = self.events.groupby("season").agg(events=("event_id", "count"), era=("era", "first")).reset_index()
        ev["has_lap_data"] = ev["season"].isin(self.lap_seasons)
        if len(self.ingested):
            ing = self.ingested.groupby("season").agg(lap_sessions=("session_id", "count"),
                                                       laps=("n_laps", "sum")).reset_index()
            ev = ev.merge(ing, on="season", how="left")
        return records(ev.sort_values("season", ascending=False))

    def events_list(self, season: int | None = None) -> list[dict]:
        ev = self.events if season is None else self.events[self.events["season"] == season]
        circ = self.circuits_tbl.set_index("circuit_id")["name"]
        ev = ev.assign(circuit_name=ev["circuit_id"].map(circ))
        if len(self.ingested):
            n = self.ingested.groupby("event_id")["session_id"].count()
            ev = ev.assign(lap_sessions=ev["event_id"].map(n).fillna(0).astype(int))
        winners = self.results[(self.results["session_code"] == "R") & (self.results["position"] == 1)].set_index("event_id")["driver_id"]
        ev = ev.assign(winner_id=ev["event_id"].map(winners))
        cols = ["event_id", "season", "round", "date", "grand_prix_id", "official_name", "circuit_id", "circuit_name",
                "circuit_type", "laps", "is_sprint_weekend", "era", "winner_id"] + (["lap_sessions"] if "lap_sessions" in ev else [])
        return records(ev.sort_values(["season", "round"])[cols])

    def circuits(self) -> list[dict]:
        c = self.circuits_tbl.copy()
        cnt = self.events.groupby("circuit_id").agg(events=("event_id", "count"), first_season=("season", "min"),
                                                    last_season=("season", "max"))
        c = c.merge(cnt, left_on="circuit_id", right_index=True, how="left")
        lap_circ = set(self.summary["circuit_id"].unique()) if "circuit_id" in self.summary else set()
        c["has_lap_data"] = c["circuit_id"].isin(lap_circ)
        return records(c.sort_values(["has_lap_data", "last_season"], ascending=False))

    def drivers(self, season: int | None = None, constructor_id: str | None = None, q: str | None = None,
                scope: str = "lap", limit: int = 100, offset: int = 0) -> dict:
        d = self.driver_index
        if scope == "lap":
            d = d[d["has_lap_data"]]
        if season is not None or constructor_id:
            r = self.results[self.results["session_code"] == "R"]
            if season is not None:
                r = r[r["season"] == season]
            if constructor_id:
                r = r[r["constructor_id"] == constructor_id]
            season_team = r.groupby("driver_id")["constructor_id"].agg(lambda s: sorted(set(s)))
            d = d[d["driver_id"].isin(season_team.index)].copy()
            d["constructors"] = d["driver_id"].map(season_team)
        if q:
            ql = q.lower()
            d = d[d["name"].fillna("").str.lower().str.contains(ql, regex=False)
                  | d["driver_id"].str.contains(ql, regex=False)
                  | d["abbreviation"].fillna("").str.lower().eq(ql)]
        d = d.sort_values(["last_season", "races"], ascending=False)
        return page(d, limit, offset)

    def constructors(self, season: int | None = None) -> list[dict]:
        r = self.results if season is None else self.results[self.results["season"] == season]
        ids = r["constructor_id"].unique()
        c = self.constructors_tbl[self.constructors_tbl["constructor_id"].isin(ids)]
        return records(c.sort_values("name"))

    def sessions_list(self, event_id: str | None = None, season: int | None = None) -> list[dict]:
        s = self.sessions
        if event_id:
            s = s[s["event_id"] == event_id]
        if season is not None:
            s = s[s["season"] == season]
        if len(self.ingested):
            cols = [c for c in ["session_id", "quality_status", "n_laps", "n_clean_laps", "n_drivers", "warnings", "fatal"]
                    if c in self.ingested.columns]
            s = s.merge(self.ingested[cols], on="session_id", how="left")
        tel = read_table(self.paths.silver("telemetry_laps"), columns=["session_id"])
        tel_counts = tel.groupby("session_id").size() if "session_id" in tel and len(tel) else pd.Series(dtype=int)
        s = s.assign(telemetry_laps=s["session_id"].map(tel_counts).fillna(0).astype(int))
        order = {"FP1": 0, "FP2": 1, "FP3": 2, "SQ": 3, "S": 4, "Q": 5, "R": 6, "FP4": 2.5}
        s = s.assign(_o=s["session_code"].map(order)).sort_values(["season", "round", "_o"]).drop(columns="_o")
        return records(s)

    # -- coverage / sources ----------------------------------------------------------------
    def coverage(self) -> dict:
        rep = read_json(self.paths.manifests / "coverage_report.json", default=None)
        if rep is None:
            raise NotFound("coverage report not generated; run `apexlens coverage`")
        return clean_value(rep)

    def sources(self) -> dict:
        reg = ProvenanceRegistry(self.paths.manifests)
        return {"catalog": SOURCE_CATALOG, "retrievals": clean_value(reg.summary())}

    def features(self) -> dict:
        return FEATURES

    # -- sessions ----------------------------------------------------------------------------
    def _require_session(self, session_id: str) -> None:
        if session_id not in set(self.sessions["session_id"]):
            raise NotFound(f"unknown session {session_id}")

    def session_laps(self, session_id: str, driver_id: str | None = None) -> dict:
        self._require_session(session_id)
        laps = read_partition(self.paths.silver("laps"), session_id)
        if laps.empty:
            raise NotFound(f"no lap timing ingested for {session_id}")
        if driver_id:
            laps = laps[laps["driver_id"] == driver_id]
        cols = ["driver_id", "driver_abbr", "constructor_id", "lap_number", "lap_time_s", "sector1_s", "sector2_s",
                "sector3_s", "compound", "tyre_life_laps", "stint", "position", "track_status", "is_clean",
                "exclusion_reason", "condition", "is_pit_in_lap", "is_pit_out_lap", "deleted", "is_personal_best",
                "speed_st_kph", "track_temp_c", "rainfall", "quali_segment"]
        laps = laps[[c for c in cols if c in laps.columns]].sort_values(["driver_id", "lap_number"])
        status = self.ingested.set_index("session_id").loc[session_id].to_dict() if session_id in set(self.ingested.get("session_id", [])) else {}
        return {"session_id": session_id, "quality": clean_value({k: status.get(k) for k in ("quality_status", "warnings", "fatal")}),
                "laps": records(laps)}

    def session_weather(self, session_id: str) -> list[dict]:
        self._require_session(session_id)
        return records(read_partition(self.paths.silver("weather_observations"), session_id))

    def session_stints(self, session_id: str) -> list[dict]:
        self._require_session(session_id)
        return records(read_partition(self.paths.silver("stints"), session_id))

    def session_results(self, session_id: str) -> list[dict]:
        self._require_session(session_id)
        ev, code = session_id.rsplit("-", 1)
        if code in ("R", "S"):
            r = self.results[(self.results["event_id"] == ev) & (self.results["session_code"] == code)]
        elif code in ("Q", "SQ"):
            r = self.quali[(self.quali["event_id"] == ev) & (self.quali["session_code"] == code)]
        else:
            r = read_table(self.paths.silver("practice_results"))
            r = r[(r["event_id"] == ev) & (r["session_code"] == code)]
        return records(r.sort_values("position", na_position="last"))

    def session_race_control(self, session_id: str) -> list[dict]:
        self._require_session(session_id)
        return records(read_partition(self.paths.silver("race_control_events"), session_id))

    def session_telemetry(self, session_id: str, driver_id: str | None = None, lap_number: int | None = None,
                          max_points: int = 2000) -> dict:
        self._require_session(session_id)
        laps = read_partition(self.paths.silver("telemetry_laps"), session_id)
        if laps.empty:
            return {"session_id": session_id, "available_laps": [], "samples": [],
                    "note": "No telemetry ingested for this session (bounded ingestion: fastest qualifying laps only)."}
        out = {"session_id": session_id, "available_laps": records(laps)}
        if driver_id:
            tel = read_partition(self.paths.silver("telemetry_samples"), session_id)
            tel = tel[tel["driver_id"] == driver_id]
            if lap_number is not None:
                tel = tel[tel["lap_number"] == lap_number]
            if len(tel) > max_points:
                tel = tel.iloc[:: int(np.ceil(len(tel) / max_points))]
            cols = ["driver_id", "lap_number", "time_s", "distance_m", "speed_kph", "throttle_pct", "brake", "gear", "rpm",
                    "drs", "x_m", "y_m"]
            out["samples"] = records(tel[[c for c in cols if c in tel.columns]])
            out["channels"] = {"measured": ["speed_kph", "throttle_pct", "brake (on/off)", "gear", "rpm", "drs", "x_m", "y_m"],
                               "derived": ["distance_m (integrated from speed by FastF1)"],
                               "unavailable": ["brake pressure", "steering angle", "tyre temperatures"]}
        return out

    # -- drivers ----------------------------------------------------------------------------
    def driver(self, driver_id: str) -> dict:
        d = self.driver_index[self.driver_index["driver_id"] == driver_id]
        if d.empty:
            raise NotFound(f"unknown driver {driver_id}")
        return records(d)[0]

    def driver_results_summary(self, driver_id: str) -> dict:
        r = self.results[(self.results["driver_id"] == driver_id) & (self.results["session_code"] == "R")]
        q = self.quali[(self.quali["driver_id"] == driver_id) & (self.quali["session_code"] == "Q")]
        cats = r["outcome_category"].value_counts().to_dict()
        moved = (r["grid_position"] - r["position"]).dropna()
        return {
            "starts": int(len(r)), "wins": int((r["position"] == 1).sum()), "podiums": int((r["position"] <= 3).sum()),
            "points": float(r["points"].fillna(0).sum()), "poles": int((q["position"] == 1).sum()),
            "outcomes": {k: int(v) for k, v in cats.items()},
            "mean_positions_gained": float(moved.mean()) if len(moved) else None,
            "positions_gained_n": int(len(moved)),
            "seasons": sorted(int(s) for s in r["season"].unique()),
            "note": "Retirement categories describe the recorded reason only; they do not assign blame.",
        }

    def driver_performance(self, driver_id: str, season: int | None = None) -> dict:
        self.driver(driver_id)
        r = self.results[(self.results["driver_id"] == driver_id) & (self.results["session_code"] == "R")]
        if season is not None:
            r = r[r["season"] == season]
        q = self.quali[(self.quali["driver_id"] == driver_id) & (self.quali["session_code"] == "Q")][
            ["event_id", "position", "best_s"]].rename(columns={"position": "quali_position", "best_s": "quali_best_s"})
        ev = self.events[["event_id", "date", "circuit_id", "grand_prix_id"]]
        rows = r[["event_id", "season", "round", "constructor_id", "position", "position_text", "grid_position", "points",
                  "outcome_category", "reason_retired"]].merge(ev, on="event_id", how="left").merge(q, on="event_id", how="left")
        s = self.summary[(self.summary["driver_id"] == driver_id) & (self.summary["session_code"] == "R")] \
            if "driver_id" in self.summary else pd.DataFrame()
        if len(s):
            rows = rows.merge(s[["event_id", "med_rel_pace", "n_laps", "teammate_gap", "robust_sd", "is_wet_session"]],
                              on="event_id", how="left")
        return {"driver": self.driver(driver_id), "results_summary": self.driver_results_summary(driver_id),
                "events": records(rows.sort_values(["season", "round"]))}

    # -- overview ---------------------------------------------------------------------------
    def overview(self) -> dict:
        cov = read_json(self.paths.manifests / "coverage_report.json", default={})
        recent = self.events[self.events["season"].isin(self.lap_seasons)].sort_values(["season", "round"]).tail(6)
        res = self.results[self.results["session_code"] == "R"]
        races = []
        for e in recent.itertuples():
            podium = res[(res["event_id"] == e.event_id) & (res["position"] <= 3)].sort_values("position")
            pole = self.quali[(self.quali["event_id"] == e.event_id) & (self.quali["position"] == 1) & (self.quali["session_code"] == "Q")]
            wet = (self.summary[(self.summary["event_id"] == e.event_id) & (self.summary["session_code"] == "R")]
                   ["is_wet_session"].any() if "event_id" in self.summary else False)
            races.append({"event_id": e.event_id, "season": e.season, "round": e.round, "date": e.date,
                          "circuit_id": e.circuit_id, "official_name": e.official_name,
                          "podium": records(podium[["position", "driver_id", "constructor_id"]]),
                          "pole_driver_id": pole["driver_id"].iloc[0] if len(pole) else None, "wet_race": bool(wet)})
        return {"summary": clean_value(cov.get("summary", {})), "per_season": clean_value(cov.get("per_season", [])),
                "analyses": clean_value(cov.get("analyses", [])), "recent_races": races,
                "seasons_with_lap_data": self.lap_seasons,
                "results_seasons": [int(self.events["season"].min()), int(self.events["season"].max())]}
