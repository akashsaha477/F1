"""Bounded per-lap telemetry ingestion.

Only a small, explicit selection of laps is downloaded: by default each driver's fastest clean lap
in each qualifying session (``laps_per_driver`` controls how many). Full-session telemetry is never
fetched by default.
"""

from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd

from apexlens.cleaning.parsing import series_to_float
from apexlens.cleaning.validation import summarize, validate_telemetry
from apexlens.data_sources.registry import ProvenanceRecord
from apexlens.ingestion.context import IngestionContext
from apexlens.storage.io import (
    read_json,
    read_partition,
    sha256_bytes,
    write_bytes,
    write_json,
    write_partition,
)

log = logging.getLogger(__name__)

TEL_KEYS = {"time": "time_s", "rpm": "rpm", "speed": "speed_kph", "gear": "gear", "throttle": "throttle_pct",
            "brake": "brake", "drs": "drs", "distance": "distance_m", "rel_distance": "rel_distance",
            "x": "x_m", "y": "y_m", "z": "z_m", "acc_x": "acc_x_derived", "acc_y": "acc_y_derived",
            "acc_z": "acc_z_derived", "DriverAhead": "driver_ahead", "DistanceToDriverAhead": "distance_to_ahead_m"}


def select_laps(laps: pd.DataFrame, laps_per_driver: int = 1) -> pd.DataFrame:
    """Fastest clean laps per driver; drivers without a clean lap fall back to their fastest valid lap."""
    base = laps[laps["lap_time_s"].notna() & laps["driver_id"].notna()]
    base = base[~base["deleted"].fillna(False).astype(bool)]
    clean = base[base["is_clean"]].sort_values("lap_time_s")
    picked = clean.groupby("driver_id").head(laps_per_driver).assign(selection="fastest_clean")
    missing = set(base["driver_id"]) - set(picked["driver_id"])
    if missing:
        fb = base[base["driver_id"].isin(missing) & ~base["is_pit_out_lap"] & ~base["is_pit_in_lap"]]
        fb = fb.sort_values("lap_time_s").groupby("driver_id").head(1).assign(selection="fastest_valid_fallback")
        picked = pd.concat([picked, fb])
    picked = picked.copy()
    picked["selection_rank"] = picked.groupby("driver_id")["lap_time_s"].rank(method="first").astype(int)
    return picked


def telemetry_frame(payload: dict) -> pd.DataFrame:
    tel = payload.get("tel", payload)
    n = len(tel.get("time", []))
    df = pd.DataFrame({TEL_KEYS[k]: v for k, v in tel.items() if k in TEL_KEYS and isinstance(v, list) and len(v) == n})
    for c in df.columns:
        if c == "driver_ahead":
            df[c] = df[c].astype(object).where(~df[c].astype(str).isin(["None", "nan", ""]), None)
        else:
            df[c] = series_to_float(df[c])
    for c in ("x_m", "y_m", "z_m"):
        if c in df.columns:
            df[c] = df[c] / 10.0  # FastF1 position units are 1/10 m
    if "brake" in df.columns:
        df["brake"] = df["brake"] > 0
    return df


def ingest_telemetry(ctx: IngestionContext, season: int, codes=("Q",), laps_per_driver: int = 1,
                     events: list[str] | None = None, max_events: int | None = None) -> dict:
    manifest = [r for r in read_json(ctx.paths.manifests / "sessions_ingested.json", default=[])
                if r.get("season") == season and r.get("session_code") in codes and r.get("n_laps")]
    if events:
        manifest = [r for r in manifest if r["event_id"] in events]
    manifest = sorted(manifest, key=lambda r: r["session_id"])
    if max_events:
        keep = sorted({r["event_id"] for r in manifest})[:max_events]
        manifest = [r for r in manifest if r["event_id"] in keep]
    idx = ctx.tracinginsights.discover(season)
    n_laps = n_missing = n_sessions = 0
    for row in manifest:
        sid = row["session_id"]
        laps = read_partition(ctx.paths.silver("laps"), sid)
        if laps.empty:
            continue
        chosen = select_laps(laps, laps_per_driver)
        sess_index = idx.sessions.get((row["source_event_name"], row["source_session_name"]))
        available = sess_index.telemetry if sess_index else {}
        reqs, meta = [], []
        for r in chosen.itertuples():
            lap = int(r.lap_number)
            if lap not in available.get(r.driver_abbr, set()):
                n_missing += 1
                ctx.registry.record(ProvenanceRecord(provider="tracinginsights", dataset="lap_telemetry", season=season,
                                                     event=row["event_id"], session=row["session_code"],
                                                     endpoint=f"{row['source_event_name']}/{row['source_session_name']}/{r.driver_abbr}/{lap}_tel.json",
                                                     status="missing", error="not listed in archive"))
                continue
            reqs.append((ctx.tracinginsights.url(season, row["source_event_name"], row["source_session_name"],
                                                 r.driver_abbr, f"{lap}_tel.json"), None))
            meta.append(r)
        results = ctx.http.fetch_many(reqs, max_workers=ctx.settings.http_max_concurrency)
        frames, lap_index = [], []
        for r, res in zip(meta, results, strict=True):
            lap = int(r.lap_number)
            rec = ProvenanceRecord(provider="tracinginsights", dataset="lap_telemetry", endpoint=res.url, season=season,
                                   event=row["event_id"], session=row["session_code"], retrieved_at=res.retrieved_at,
                                   from_cache=res.from_cache, params={"driver": r.driver_abbr, "lap": lap})
            if not res.ok:
                rec.status, rec.error = ("missing" if res.status == 404 else "error"), res.error
                ctx.registry.record(rec)
                n_missing += 1
                continue
            path = (ctx.paths.raw / "tracinginsights" / str(season) / row["event_id"] / row["session_code"] / "telemetry"
                    / f"{r.driver_abbr}_{lap}.json")
            if not (path.exists() and sha256_bytes(path.read_bytes()) == res.content_hash):
                write_bytes(path, res.content)
            rec.content_hash, rec.n_bytes = res.content_hash, len(res.content)
            rec.bronze_path = str(path.relative_to(ctx.paths.root))
            ctx.registry.record(rec)
            df = telemetry_frame(json.loads(res.content))
            df.insert(0, "sample_idx", np.arange(len(df)))
            df.insert(0, "lap_number", lap)
            df.insert(0, "driver_abbr", r.driver_abbr)
            df.insert(0, "constructor_id", r.constructor_id)
            df.insert(0, "driver_id", r.driver_id)
            df.insert(0, "session_id", sid)
            df["lap_key"] = f"{r.driver_id}:{lap}"
            frames.append(df)
            lap_index.append({"session_id": sid, "event_id": row["event_id"], "season": season,
                              "session_code": row["session_code"], "driver_id": r.driver_id,
                              "constructor_id": r.constructor_id, "driver_abbr": r.driver_abbr, "lap_number": lap,
                              "lap_time_s": r.lap_time_s, "compound": r.compound, "selection": r.selection,
                              "selection_rank": r.selection_rank, "n_samples": len(df)})
            n_laps += 1
        if not frames:
            continue
        tel = pd.concat(frames, ignore_index=True)
        quality = summarize(validate_telemetry(tel))
        write_json(ctx.paths.manifests / "quality" / f"telemetry_{sid}.json", quality)
        idx_df = pd.DataFrame(lap_index)
        idx_df["quality_status"] = quality["status"]
        write_partition(ctx.paths.silver("telemetry_samples"), sid, tel)
        write_partition(ctx.paths.silver("telemetry_laps"), sid, idx_df)
        n_sessions += 1
        log.info("telemetry %s: %d laps (%s)", sid, len(frames), quality["status"])
    return {"sessions": n_sessions, "laps": n_laps, "missing": n_missing}
