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
        # early championship races can credit several drivers (shared drives) with the win
        winners = (self.results[(self.results["session_code"] == "R") & (self.results["position"] == 1)]
                   .drop_duplicates("event_id").set_index("event_id")["driver_id"])
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


class ProfileService:
    """Driver fingerprints (gold ``driver_profiles``, ``driver_condition_effects``)."""

    def __init__(self, paths: DataPaths):
        self.paths = paths

    @cached_property
    def profiles(self) -> pd.DataFrame:
        return read_table(self.paths.gold("driver_profiles"))

    @cached_property
    def conditions(self) -> pd.DataFrame:
        return read_table(self.paths.gold("driver_condition_effects"))

    @cached_property
    def adjusted(self) -> pd.DataFrame:
        return read_table(self.paths.gold("driver_session_adjusted"))

    @cached_property
    def meta(self) -> dict:
        return read_json(self.paths.gold("driver_profiles") / "meta.json", default={})

    def _require(self) -> None:
        if self.profiles.empty:
            raise NotFound("driver profiles not built; run scripts/build_features.py")

    def driver_profile(self, driver_id: str) -> dict:
        self._require()
        p = self.profiles[self.profiles["driver_id"] == driver_id].sort_values("season")
        if p.empty:
            raise NotFound(f"no lap-timing profile for {driver_id} (results-only driver or no dry races)")
        c = self.conditions[self.conditions["driver_id"] == driver_id] if len(self.conditions) else pd.DataFrame()
        tyre = read_table(self.paths.gold("driver_tyre_effects"))
        tyre = tyre[tyre["driver_id"] == driver_id] if len(tyre) else tyre
        return {"driver_id": driver_id, "seasons": records(p), "conditions": records(c), "tyre_effects": records(tyre),
                "meta": clean_value(self.meta)}

    def conditions_by_dimension(self, dimension: str) -> dict:
        self._require()
        c = self.conditions[self.conditions["dimension"] == dimension] if len(self.conditions) else pd.DataFrame()
        if c.empty:
            raise NotFound(f"no condition estimates for {dimension}")
        defs = (self.meta or {}).get("condition_definitions", {})
        return {"dimension": dimension, "definition": defs.get(dimension), "rows": records(c.sort_values("posterior_mean")),
                "tau": float(c["tau"].iloc[0]), "thresholds": clean_value((self.meta or {}).get("thresholds"))}

    def clusters(self) -> dict:
        pts = read_table(self.paths.gold("driver_clusters"))
        meta = read_json(self.paths.gold("driver_clusters") / "meta.json")
        if meta is None:
            raise NotFound("driver clusters not built; run scripts/build_features.py")
        return {"points": records(pts), "meta": clean_value(meta)}

    def season_effects(self, season: int) -> dict:
        self._require()
        p = self.profiles[self.profiles["season"] == season].sort_values("race_pace_adj")
        if p.empty:
            raise NotFound(f"no driver profiles for season {season}")
        return {"season": season, "drivers": records(p), "meta": clean_value(self.meta)}

    def compare(self, a: str, b: str, season: int | None = None) -> dict:
        self._require()
        out = {"drivers": [a, b], "profiles": {}, "conditions": {}}
        for d in (a, b):
            p = self.profiles[self.profiles["driver_id"] == d]
            if season is not None:
                p = p[p["season"] == season]
            out["profiles"][d] = records(p.sort_values("season"))
            out["conditions"][d] = records(self.conditions[self.conditions["driver_id"] == d]) if len(self.conditions) else []
        adj = self.adjusted
        if season is not None:
            adj = adj[adj["season"] == season]
        pa = adj[adj["driver_id"] == a].set_index("session_id")
        pb = adj[adj["driver_id"] == b].set_index("session_id")
        common = pa.index.intersection(pb.index)
        h2h = []
        for sid in common:
            ra, rb = pa.loc[sid], pb.loc[sid]
            h2h.append({"session_id": sid, "season": int(ra["season"]), "condition": ra["condition"],
                        "same_team": ra["constructor_id"] == rb["constructor_id"],
                        "diff": float(ra["adj_pace"] - rb["adj_pace"]),
                        "se": float(np.sqrt(ra["se"] ** 2 + rb["se"] ** 2))})
        h = pd.DataFrame(h2h)
        summary = None
        if len(h):
            dry = h[h["condition"] == "dry"]
            vals = dry["diff"].to_numpy()
            rng = np.random.default_rng(0)
            boots = [np.median(rng.choice(vals, len(vals))) for _ in range(500)] if len(vals) >= 3 else []
            summary = {"n_sessions": int(len(dry)), "n_same_team": int(dry["same_team"].sum()),
                       "median_diff": float(np.median(vals)) if len(vals) else None,
                       "ci90": [float(np.quantile(boots, 0.05)), float(np.quantile(boots, 0.95))] if boots else None,
                       "a_faster_share": float(np.mean(vals < 0)) if len(vals) else None,
                       "note": ("Raw head-to-head of condition-adjusted race pace in shared sessions. Unless the drivers "
                                "were team-mates, the difference includes the car.")}
        out["head_to_head"] = {"sessions": records(h), "summary": summary}
        out["meta"] = clean_value(self.meta)
        return out


class TrackService:
    """Track maps, corner definitions and corner-level driver metrics (gold tables from Phase 4)."""

    def __init__(self, paths: DataPaths):
        self.paths = paths

    @cached_property
    def sessions(self) -> pd.DataFrame:
        rows = read_json(self.paths.gold("corner_definitions") / "sessions.json", default=[])
        df = pd.DataFrame(rows)
        if len(df):
            df["date"] = pd.to_datetime(df["date"])
        return df

    def _sessions_for(self, circuit_id: str) -> pd.DataFrame:
        if self.sessions.empty:
            raise NotFound("corner analysis not built; run scripts/build_features.py")
        s = self.sessions[self.sessions["circuit_id"] == circuit_id].sort_values("date")
        if s.empty:
            raise NotFound(f"no telemetry-based track analysis for circuit {circuit_id}")
        return s

    def _pick(self, circuit_id: str, session_id: str | None) -> pd.Series:
        s = self._sessions_for(circuit_id)
        if session_id:
            hit = s[s["session_id"] == session_id]
            if hit.empty:
                raise NotFound(f"session {session_id} has no track analysis at {circuit_id}")
            return hit.iloc[0]
        return s.iloc[-1]

    def layout(self, circuit_id: str, session_id: str | None = None) -> dict:
        row = self._pick(circuit_id, session_id)
        sid = row["session_id"]
        track = read_partition(self.paths.gold("track_maps"), sid)
        defs = read_partition(self.paths.gold("corner_definitions"), sid)
        inferred = read_partition(self.paths.gold("inferred_segments"), sid)
        sectors = read_partition(self.paths.gold("sector_profiles"), sid)
        avail = self._sessions_for(circuit_id)[["session_id", "season", "circuit_layout_id", "reference_driver", "reference_lap_time_s"]]
        defs = defs.drop(columns=[c for c in ("labels",) if c in defs.columns])
        return {
            "circuit_id": circuit_id, "session_id": sid, "season": int(row["season"]), "layout_id": row.get("circuit_layout_id"),
            "rotation_deg": float(row.get("rotation_deg") or 0.0), "length_m": float(row["length_m"]),
            "reference": {"driver_id": row["reference_driver"], "lap": int(row["reference_lap"]),
                          "lap_time_s": float(row["reference_lap_time_s"])},
            "segmentation_method": row.get("segmentation_method"),
            "marker_validation": clean_value(row.get("marker_validation")),
            "alignment": clean_value(pd.DataFrame(row.get("alignment") or []).describe().to_dict()) if row.get("alignment") else None,
            "sector_bounds_m": clean_value(row.get("sector_bounds_m")),
            "track": records(track[["s", "x", "y", "speed_ref", "throttle_ref"]]),
            "corners": records(defs), "inferred_segments": records(inferred), "sectors": records(sectors),
            "available_sessions": records(avail),
            "category_rules": __import__("apexlens.track_geometry.corners", fromlist=["CORNER_RULES"]).CORNER_RULES,
            "notes": ["Numbered corners come from FastF1 circuit markers; S-labelled segments are inferred from path "
                      "curvature and are not official corner numbers.",
                      "Corner categories are ApexLens conventions based on the reference lap's minimum speed, not FIA "
                      "classifications."],
        }

    def performance(self, circuit_id: str, session_id: str | None = None, corner_id: str | None = None) -> dict:
        row = self._pick(circuit_id, session_id)
        sid = row["session_id"]
        m = read_partition(self.paths.gold("corner_metrics"), sid)
        if corner_id:
            m = m[m["corner_id"] == corner_id]
        cols = ["driver_id", "constructor_id", "lap_number", "lap_time_s", "corner_id", "category", "sector", "segment_time_s",
                "delta_to_best_s", "delta_to_teammate_s", "teammate_comparable", "entry_speed_kph", "min_speed_kph",
                "exit_speed_kph", "brake_onset_before_apex_m", "braking_duration_s", "full_throttle_delay_s",
                "full_throttle_after_apex_m", "min_gear", "max_decel_proxy_ms2", "quality", "compound"]
        m = m[[c for c in cols if c in m.columns]]
        # across all analysed sessions at this circuit: who gains relative to the team-mate in each corner?
        all_m = pd.concat([read_partition(self.paths.gold("corner_metrics"), s)
                           for s in self._sessions_for(circuit_id)["session_id"]], ignore_index=True)
        if corner_id:
            all_m = all_m[all_m["corner_id"] == corner_id]
        tm = all_m[all_m["delta_to_teammate_s"].notna()]
        hist = (tm.groupby("driver_id").agg(mean_delta_to_teammate_s=("delta_to_teammate_s", "mean"),
                                            n_corner_laps=("delta_to_teammate_s", "size"),
                                            n_sessions=("session_id", "nunique")).reset_index()
                .sort_values("mean_delta_to_teammate_s"))
        return {"circuit_id": circuit_id, "session_id": sid, "corner_id": corner_id, "metrics": records(m),
                "teammate_relative_history": records(hist),
                "measured_vs_derived": {
                    "measured": ["speed", "throttle", "brake on/off", "gear", "position"],
                    "derived": ["segment time (interpolated at window boundaries)", "braking onset and duration (on/off brake channel)",
                                "minimum-speed-to-full-throttle time", "deceleration proxy dv/dt (not a force measurement)"]},
                "notes": ["Fastest qualifying lap per driver only (bounded ingestion).",
                          "Team-mate deltas only when both laps were set in the same part of qualifying with lap times within 1.5%."]}

    def driver_corner_profile(self, driver_id: str) -> dict:
        p = read_table(self.paths.gold("driver_corner_profiles"))
        p = p[p["driver_id"] == driver_id] if len(p) else p
        exp = read_json(self.paths.models / "evaluation_runs" / "corner_experiments.json", default={})
        return {"driver_id": driver_id, "profile": records(p), "reliability": clean_value(exp.get("specialisation_reliability")),
                "note": "Team-mate-relative qualifying segment-time deltas per corner category (negative = faster than team-mate)."}

    def summary(self) -> dict:
        exp = read_json(self.paths.models / "evaluation_runs" / "corner_experiments.json", default={})
        s = self.sessions
        val = pd.json_normalize(s["marker_validation"].tolist()) if len(s) else pd.DataFrame()
        return {"n_sessions": int(len(s)), "circuits": sorted(s["circuit_id"].dropna().unique().tolist()) if len(s) else [],
                "marker_validation": clean_value(val.describe().to_dict()) if len(val) else None,
                "experiments": clean_value(exp)}


class TyreService:
    """Model C outputs: degradation summaries, driver deviations, stints and degradation curves."""

    def __init__(self, paths: DataPaths):
        self.paths = paths

    @cached_property
    def stints(self) -> pd.DataFrame:
        return read_table(self.paths.gold("tyre_stints"))

    def _t(self, name: str) -> pd.DataFrame:
        return read_table(self.paths.gold(name))

    def degradation(self, season: int | None = None, circuit_id: str | None = None, compound: str | None = None,
                    driver_id: str | None = None) -> dict:
        if self.stints.empty:
            raise NotFound("tyre tables not built; run scripts/build_features.py")
        comp = self._t("tyre_degradation")
        circ = self._t("tyre_degradation_circuit")
        drv = self._t("driver_tyre_effects")
        st = self.stints
        if season is not None:
            comp, st = comp[comp["season"] == season], st[st["season"] == season]
            drv = drv[drv["season"] == season]
        if circuit_id:
            circ, st = circ[circ["circuit_id"] == circuit_id], st[st["circuit_id"] == circuit_id]
        if compound:
            comp, circ, st, drv = (d[d["compound"] == compound] for d in (comp, circ, st, drv))
        if driver_id:
            st, drv = st[st["driver_id"] == driver_id], drv[drv["driver_id"] == driver_id]
        ev = read_json(self.paths.models / "evaluation_runs" / "tyre_degradation.json", default={})
        return {
            "by_compound": records(comp), "by_circuit": records(circ), "temperature": records(self._t("tyre_temperature")),
            "session_points": records(self._t("tyre_session_points")) if circuit_id is None and driver_id is None else [],
            "driver_effects": records(drv),
            "stints": records(st[["session_id", "event_id", "season", "driver_id", "constructor_id", "stint", "compound", "n_laps",
                                  "age_min", "age_max", "slope_pct", "slope_se", "track_temp_c", "circuit_id"]].sort_values(
                                      ["season", "session_id"]).tail(400)),
            "evaluation": clean_value(ev),
            "definitions": {
                "slope_pct": "Fuel-corrected change in lap time per lap of tyre age, % of the session reference lap",
                "fuel_correction": "lap-number slope of the session's stage-1 model (identified via pit stops)",
                "driver_effect": "driver's stint slope minus other drivers' slopes on the same compound in the same session, "
                                 "shrunk by empirical Bayes",
            },
            "limitations": ["Lap-time increases also come from traffic, tyre management, damage and track evolution.",
                            "SOFT/MEDIUM/HARD are relative names: the Pirelli C-number differs by event.",
                            "Temperature associations are descriptive; temperature is confounded with circuit and season."],
        }

    def curve(self, compound: str, circuit_id: str | None, driver_id: str | None, max_age: int) -> dict:
        comp = self._t("tyre_degradation")
        if comp.empty:
            raise NotFound("tyre tables not built")
        latest = comp[comp["compound"] == compound].sort_values("season").tail(1)
        if latest.empty:
            raise NotFound(f"no degradation estimate for {compound}")
        base = latest.iloc[0]
        slope, lo, hi = float(base["slope_pct"]), float(base["ci_lo"]), float(base["ci_hi"])
        assumptions = [f"{compound} slope from {int(base['season'])} ({int(base['n_stints'])} stints)."]
        if circuit_id:
            c = self._t("tyre_degradation_circuit")
            c = c[(c["circuit_id"] == circuit_id) & (c["compound"] == compound)]
            if len(c) and c.iloc[0]["n_stints"] >= 5:
                n = float(c.iloc[0]["n_stints"])
                w = n / (n + 20)
                cr = c.iloc[0]
                slope = w * float(cr["slope_pct"]) + (1 - w) * slope
                if pd.notna(cr["ci_lo"]) and pd.notna(cr["ci_hi"]):
                    lo, hi = w * float(cr["ci_lo"]) + (1 - w) * lo, w * float(cr["ci_hi"]) + (1 - w) * hi
                assumptions.append(f"Circuit estimate ({int(n)} stints) blended with the season value (weight {w:.2f}).")
            else:
                assumptions.append("Too few stints at this circuit; season-wide value used.")
        dev = None
        if driver_id:
            d = self._t("driver_tyre_effects")
            d = d[(d["driver_id"] == driver_id) & (d["compound"] == compound)].sort_values("season").tail(1)
            if len(d):
                dev = d.iloc[0].to_dict()
                if dev["status"] == "supported":
                    slope += float(dev["posterior_mean"])
                    lo += float(dev["posterior_mean"])
                    hi += float(dev["posterior_mean"])
                    assumptions.append("Driver-specific deviation applied (supported by data).")
                else:
                    assumptions.append(f"Driver deviation not applied: {dev['status'].replace('_', ' ')}.")
        ages = np.arange(1, max_age + 1)
        ref = float(self.stints["session_ref_s"].median()) if len(self.stints) else None
        return {"compound": compound, "circuit_id": circuit_id, "driver_id": driver_id, "slope_pct_per_lap": slope,
                "season_ci": [lo, hi], "points": [{"tyre_age": int(a), "delta_pct": slope * (a - 1),
                                                    "lo_pct": lo * (a - 1), "hi_pct": hi * (a - 1)} for a in ages],
                "reference_lap_s": ref, "driver_effect": clean_value(dev), "assumptions": assumptions,
                "slope_ci": [lo, hi],
                "note": "Linear fuel-corrected degradation; the band is the 90% interval of the slope (session-cluster "
                        "bootstrap), blended like the point estimate."}
