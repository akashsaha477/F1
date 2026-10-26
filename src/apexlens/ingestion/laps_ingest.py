"""Lap-timing ingestion from the TracingInsights FastF1 export.

For each session: download the session-level files (bronze), resolve identities against F1DB,
normalise to silver tables (laps, weather, race control, corner markers, stints, participants),
run data-quality checks and record provenance. Re-running replaces the session's partitions, so the
job is idempotent; a failed download leaves previously stored data untouched.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import pandas as pd

from apexlens.cleaning.entity_mapping import DriverResolver, match_event
from apexlens.cleaning.laps import (
    normalize_laps,
    tracinginsights_corners_to_frame,
    tracinginsights_laps_to_frame,
    tracinginsights_rcm_to_frame,
    tracinginsights_weather_to_frame,
)
from apexlens.cleaning.validation import summarize, validate_laps, validate_weather
from apexlens.data_sources.http import utc_now_iso
from apexlens.data_sources.registry import ProvenanceRecord
from apexlens.data_sources.tracinginsights import SESSION_FILES, SeasonIndex, session_code_for
from apexlens.ingestion.context import IngestionContext
from apexlens.storage.io import read_json, read_table, sha256_bytes, write_bytes, write_json, write_partition

log = logging.getLogger(__name__)

ALL_SESSION_CODES = ("FP1", "FP2", "FP3", "Q", "SQ", "S", "R")


@dataclass
class SessionTask:
    season: int
    event_name: str
    session_dir: str
    session_code: str
    event_id: str
    circuit_id: str | None

    @property
    def session_id(self) -> str:
        return f"{self.event_id}-{self.session_code}"


def event_mapping(ctx: IngestionContext, season: int, idx: SeasonIndex) -> pd.DataFrame:
    events = read_table(ctx.paths.silver("events"), filters={"season": season})
    gps = read_table(ctx.paths.silver("grands_prix"))
    rows = []
    for name in idx.events():
        eid, method = match_event(name, events, gps)
        rows.append({"season": season, "source_event_name": name, "event_id": eid, "method": method})
    df = pd.DataFrame(rows)
    dupes = df.dropna(subset=["event_id"]).duplicated("event_id", keep=False)
    if dupes.any():
        log.warning("ambiguous event mapping in %s: %s", season, df[dupes].to_dict("records"))
        df.loc[dupes[dupes].index, "event_id"] = None
        df.loc[dupes[dupes].index, "method"] = "ambiguous"
    write_json(ctx.paths.manifests / "event_mapping" / f"{season}.json", df.to_dict("records"))
    return df


def plan_sessions(ctx: IngestionContext, season: int, idx: SeasonIndex, codes=ALL_SESSION_CODES,
                  events: list[str] | None = None) -> list[SessionTask]:
    emap = event_mapping(ctx, season, idx).dropna(subset=["event_id"]).set_index("source_event_name")["event_id"]
    ev = read_table(ctx.paths.silver("events"), filters={"season": season}).set_index("event_id")
    tasks = []
    for (event_name, sdir) in sorted(idx.sessions):
        if event_name not in emap.index:
            continue
        eid = emap[event_name]
        if events and eid not in events and event_name not in events:
            continue
        code = session_code_for(sdir, season)
        if code == "S_LEGACY":
            # 2021-22 "Sprint Qualifying" folder holds the sprint; only use it when no "Sprint" folder exists.
            if (event_name, "Sprint") in idx.sessions:
                continue
            code = "S"
        if code not in codes:
            continue
        tasks.append(SessionTask(season, event_name, sdir, code, eid, ev.loc[eid, "circuit_id"] if eid in ev.index else None))
    return tasks


def _store_bronze(ctx: IngestionContext, task: SessionTask, filename: str, res) -> ProvenanceRecord:
    rec = ProvenanceRecord(provider="tracinginsights", dataset=filename.replace(".json", ""), endpoint=res.url,
                           season=task.season, event=task.event_id, session=task.session_code,
                           retrieved_at=res.retrieved_at, from_cache=res.from_cache)
    if res.ok:
        path = ctx.paths.raw / "tracinginsights" / str(task.season) / task.event_id / task.session_code / filename
        if not (path.exists() and sha256_bytes(path.read_bytes()) == res.content_hash):
            write_bytes(path, res.content)
        rec.content_hash, rec.n_bytes = res.content_hash, len(res.content)
        rec.bronze_path = str(path.relative_to(ctx.paths.root))
    elif res.status == 404:
        rec.status, rec.error = "missing", "not found"
    else:
        rec.status, rec.error = "error", res.error
    ctx.registry.record(rec)
    return rec


def build_stints(laps: pd.DataFrame) -> pd.DataFrame:
    if laps.empty:
        return pd.DataFrame()
    g = laps.dropna(subset=["stint"]).groupby(["session_id", "driver_id", "driver_number", "stint"], dropna=False)
    st = g.agg(compound=("compound", lambda s: s.mode().iloc[0] if len(s.mode()) else "UNKNOWN"),
               n_compounds=("compound", "nunique"), start_lap=("lap_number", "min"), end_lap=("lap_number", "max"),
               n_laps=("lap_number", "count"), n_clean_laps=("is_clean", "sum"),
               tyre_life_start=("tyre_life_laps", "min"), tyre_life_end=("tyre_life_laps", "max"),
               fresh_tyre=("fresh_tyre", "first")).reset_index()
    for c in ["event_id", "season", "round", "session_code", "constructor_id"]:
        st[c] = st["session_id"].map(laps.drop_duplicates("session_id").set_index("session_id")[c]) if c != "constructor_id" \
            else st["driver_id"].map(laps.drop_duplicates("driver_id").set_index("driver_id")["constructor_id"])
    return st


def ingest_session(ctx: IngestionContext, task: SessionTask, resolver: DriverResolver) -> dict:
    ti = ctx.tracinginsights
    results = ctx.http.fetch_many(
        [(ti.url(task.season, task.event_name, task.session_dir, f), None) for f in SESSION_FILES],
        max_workers=ctx.settings.http_max_concurrency,
    )
    payload = {}
    for fname, res in zip(SESSION_FILES, results, strict=True):
        rec = _store_bronze(ctx, task, fname, res)
        if rec.status == "ok":
            payload[fname] = json.loads(res.content)
    status = {"session_id": task.session_id, "event_id": task.event_id, "season": task.season,
              "session_code": task.session_code, "source": "tracinginsights", "source_event_name": task.event_name,
              "source_session_name": task.session_dir, "ingested_at": utc_now_iso(),
              "files": sorted(payload.keys())}
    if "session_laptimes.json" not in payload:
        status.update({"quality_status": "missing", "n_laps": 0})
        return status

    ctxd = {"session_id": task.session_id, "event_id": task.event_id, "season": task.season,
            "round": int(task.event_id.split("-")[1]), "session_code": task.session_code,
            "circuit_id": task.circuit_id, "source": "tracinginsights"}
    frame = tracinginsights_laps_to_frame(payload["session_laptimes.json"])
    laps, mapping = normalize_laps(frame, ctxd, resolver)
    checks = validate_laps(laps)
    weather = pd.DataFrame()
    if "weather.json" in payload:
        w = tracinginsights_weather_to_frame(payload["weather.json"])
        weather = pd.DataFrame({
            "session_id": task.session_id, "event_id": task.event_id, "season": task.season,
            "session_time_s": w.get("Time"), "air_temp_c": w.get("AirTemp"), "track_temp_c": w.get("TrackTemp"),
            "humidity_pct": w.get("Humidity"), "pressure_mbar": w.get("Pressure"),
            "rainfall": w.get("Rainfall"), "wind_dir_deg": w.get("WindDirection"), "wind_speed_ms": w.get("WindSpeed"),
        })
        checks += validate_weather(weather)
    quality = summarize(checks)
    write_json(ctx.paths.manifests / "quality" / f"{task.session_id}.json", quality)

    write_partition(ctx.paths.silver("laps"), task.session_id, laps)
    write_partition(ctx.paths.silver("stints"), task.session_id, build_stints(laps))
    if len(mapping):
        write_partition(ctx.paths.manifests / "identity_mapping", task.session_id, mapping)
    if len(weather):
        write_partition(ctx.paths.silver("weather_observations"), task.session_id, weather)
    if "rcm.json" in payload:
        rcm = tracinginsights_rcm_to_frame(payload["rcm.json"])
        rc = pd.DataFrame({
            "session_id": task.session_id, "event_id": task.event_id, "season": task.season,
            "time_utc": pd.to_datetime(rcm.get("Time"), errors="coerce", utc=True), "lap": pd.to_numeric(rcm.get("Lap"), errors="coerce"),
            "category": rcm.get("Category"), "message": rcm.get("Message"), "status": rcm.get("Status"),
            "flag": rcm.get("Flag"), "scope": rcm.get("Scope"),
            "sector": pd.to_numeric(rcm.get("Sector"), errors="coerce"),
            "racing_number": rcm.get("RacingNumber"),
        })
        write_partition(ctx.paths.silver("race_control_events"), task.session_id, rc)
        ts = rc[rc["category"].isin(["Flag", "SafetyCar"]) | rc["flag"].notna()].copy()
        write_partition(ctx.paths.silver("track_status_events"), task.session_id, ts)
    if "corners.json" in payload:
        corners, rotation = tracinginsights_corners_to_frame(payload["corners.json"])
        cm = pd.DataFrame({
            "session_id": task.session_id, "event_id": task.event_id, "season": task.season,
            "circuit_id": task.circuit_id, "number": corners.get("Number"), "letter": corners.get("Letter"),
            "x_m": pd.to_numeric(corners.get("X"), errors="coerce") / 10.0,
            "y_m": pd.to_numeric(corners.get("Y"), errors="coerce") / 10.0,
            "angle_deg": pd.to_numeric(corners.get("Angle"), errors="coerce"),
            "distance_m": pd.to_numeric(corners.get("Distance"), errors="coerce"), "rotation_deg": rotation,
            "source": "fastf1_circuit_info",
        })
        write_partition(ctx.paths.silver("corner_markers"), task.session_id, cm)
    if "drivers.json" in payload:
        d = pd.DataFrame(payload["drivers.json"].get("drivers", []))
        if len(d):
            d = d.rename(columns={"driver": "driver_abbr", "dn": "driver_number", "fn": "first_name", "ln": "last_name",
                                  "tc": "team_colour"})
            d = d[[c for c in ["driver_abbr", "driver_number", "team", "first_name", "last_name", "team_colour"] if c in d.columns]]
            d.insert(0, "session_id", task.session_id)
            write_partition(ctx.paths.silver("session_drivers"), task.session_id, d)

    status.update({"quality_status": quality["status"], "fatal": quality["fatal"], "warnings": quality["warnings"],
                   "n_laps": int(len(laps)), "n_clean_laps": int(laps["is_clean"].sum()),
                   "n_drivers": int(laps["driver_number"].nunique()),
                   "n_unresolved_laps": int(laps["driver_id"].isna().sum())})
    return status


def ingest_lap_timing(ctx: IngestionContext, season: int, codes=ALL_SESSION_CODES, events: list[str] | None = None,
                      refresh_index: bool = False) -> list[dict]:
    idx = ctx.tracinginsights.discover(season, refresh=refresh_index)
    tasks = plan_sessions(ctx, season, idx, codes=codes, events=events)
    participants = read_table(ctx.paths.silver("session_participants"))
    drivers = read_table(ctx.paths.silver("drivers"))
    resolver = DriverResolver(participants, drivers)
    statuses = []
    for i, task in enumerate(tasks, 1):
        try:
            st = ingest_session(ctx, task, resolver)
        except Exception as exc:  # noqa: BLE001 - one bad session must not abort the season
            log.exception("session %s failed", task.session_id)
            st = {"session_id": task.session_id, "event_id": task.event_id, "season": season,
                  "session_code": task.session_code, "quality_status": "error", "error": str(exc),
                  "ingested_at": utc_now_iso()}
        statuses.append(st)
        log.info("[%d/%d] %s %s laps=%s quality=%s", i, len(tasks), task.session_id, task.event_name,
                 st.get("n_laps"), st.get("quality_status"))
    # merge into the session ingestion manifest
    path = ctx.paths.manifests / "sessions_ingested.json"
    existing = {r["session_id"]: r for r in read_json(path, default=[])}
    existing.update({s["session_id"]: s for s in statuses})
    write_json(path, sorted(existing.values(), key=lambda r: r["session_id"]))
    return statuses
