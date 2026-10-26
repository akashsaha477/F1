"""F1DB ingestion: bronze JSON snapshots and silver entity/result tables.

Bronze snapshots are keyed by the F1DB git commit, so re-running against the same commit rewrites
identical files (idempotent) and a newer commit is stored alongside, never overwriting history.
Silver tables are partitioned by season and replaced wholesale per season.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Any

import pandas as pd

from apexlens.cleaning.parsing import parse_duration_s, to_float
from apexlens.cleaning.results import classify_retirement, position_value
from apexlens.config.eras import era_for
from apexlens.data_sources.registry import ProvenanceRecord
from apexlens.ingestion.context import IngestionContext
from apexlens.storage.io import read_json, sha256_bytes, write_bytes, write_json, write_partition, write_table

log = logging.getLogger(__name__)

SESSION_FIELDS = [
    ("FP1", "freePractice1Date", "freePractice1Time"),
    ("FP2", "freePractice2Date", "freePractice2Time"),
    ("FP3", "freePractice3Date", "freePractice3Time"),
    ("FP4", "freePractice4Date", "freePractice4Time"),
    ("Q", "qualifyingDate", "qualifyingTime"),
    ("SQ", "sprintQualifyingDate", "sprintQualifyingTime"),
    ("S", "sprintRaceDate", "sprintRaceTime"),
    ("R", "date", "time"),
]


def _json_default(o: Any):
    if isinstance(o, (date, datetime)):
        return o.isoformat()
    raise TypeError(type(o))


def _write_bronze(ctx: IngestionContext, rel: str, obj: Any, record: ProvenanceRecord) -> None:
    data = json.dumps(obj, default=_json_default, ensure_ascii=False, sort_keys=True).encode()
    path = ctx.paths.raw / "f1db" / rel
    h = sha256_bytes(data)
    if not (path.exists() and sha256_bytes(path.read_bytes()) == h):
        write_bytes(path, data)
    record.content_hash = h
    record.n_bytes = len(data)
    record.bronze_path = str(path.relative_to(ctx.paths.root))
    ctx.registry.record(record)


def _event_id(season: int, round_: int) -> str:
    return f"{season}-{int(round_):02d}"


def _session_id(event_id: str, code: str) -> str:
    return f"{event_id}-{code}"


def entity_tables(f1db_entities: dict[str, list[dict]]) -> dict[str, pd.DataFrame]:
    drivers = pd.DataFrame([{
        "driver_id": d["id"], "name": d.get("name"), "first_name": d.get("firstName"), "last_name": d.get("lastName"),
        "full_name": d.get("fullName"), "abbreviation": d.get("abbreviation"),
        "permanent_number": str(d["permanentNumber"]) if d.get("permanentNumber") is not None else None,
        "gender": d.get("gender"), "date_of_birth": str(d.get("dateOfBirth")) if d.get("dateOfBirth") else None,
        "nationality_country_id": d.get("nationalityCountryId"), "country_of_birth_id": d.get("countryOfBirthCountryId"),
    } for d in f1db_entities["drivers"]])
    constructors = pd.DataFrame([{
        "constructor_id": c["id"], "name": c.get("name"), "full_name": c.get("fullName"),
        "country_id": c.get("countryId"),
    } for c in f1db_entities["constructors"]])
    circuits, layouts = [], []
    for c in f1db_entities["circuits"]:
        circuits.append({
            "circuit_id": c["id"], "name": c.get("name"), "full_name": c.get("fullName"), "type": c.get("type"),
            "direction": c.get("direction"), "place_name": c.get("placeName"), "country_id": c.get("countryId"),
            "latitude": to_float(c.get("latitude")), "longitude": to_float(c.get("longitude")),
            "length_km": to_float(c.get("length")), "turns": c.get("turns"),
        })
        for lay in c.get("layouts") or []:
            layouts.append({"circuit_id": c["id"], "layout_id": lay.get("id"), "length_km": to_float(lay.get("length")),
                            "turns": lay.get("turns"), "effective": bool(lay.get("effective", False))})
    grands_prix = pd.DataFrame([{
        "grand_prix_id": g["id"], "name": g.get("name"), "full_name": g.get("fullName"),
        "short_name": g.get("shortName"), "abbreviation": g.get("abbreviation"), "country_id": g.get("countryId"),
    } for g in f1db_entities["grands-prix"]])
    countries = pd.DataFrame([{"country_id": c["id"], "name": c.get("name"), "alpha3": c.get("alpha3Code")}
                              for c in f1db_entities.get("countries", [])])
    return {"drivers": drivers, "constructors": constructors, "circuits": pd.DataFrame(circuits),
            "circuit_layouts": pd.DataFrame(layouts), "grands_prix": grands_prix, "countries": countries}


def _session_start(d, t) -> str | None:
    if d is None:
        return None
    if t is None:
        return f"{d}"
    return f"{d}T{t}:00Z" if len(str(t)) == 5 else f"{d}T{t}Z"


def season_tables(season: int, races: list[dict]) -> dict[str, pd.DataFrame]:
    events, sessions, results, quali, grids, pits, fastest, practice, dstand, cstand, parts = ([] for _ in range(11))
    for r in races:
        info = r.get("race") or {}
        rnd = int(info.get("round"))
        eid = _event_id(season, rnd)
        is_sprint = bool(info.get("sprintRaceDate"))
        events.append({
            "event_id": eid, "f1db_race_id": info.get("id"), "season": season, "round": rnd, "slug": r["slug"],
            "date": str(info.get("date")) if info.get("date") else None, "grand_prix_id": info.get("grandPrixId"),
            "official_name": info.get("officialName"), "circuit_id": info.get("circuitId"),
            "circuit_layout_id": info.get("circuitLayoutId"), "circuit_type": info.get("circuitType"),
            "direction": info.get("direction"), "course_length_km": to_float(info.get("courseLength")),
            "turns": info.get("turns"), "laps": info.get("laps"), "distance_km": to_float(info.get("distance")),
            "sprint_laps": info.get("sprintRaceLaps"),
            "qualifying_format": info.get("qualifyingFormat"), "sprint_qualifying_format": info.get("sprintQualifyingFormat"),
            "is_sprint_weekend": is_sprint, "era": era_for(season),
        })
        for code, df_, tf_ in SESSION_FIELDS:
            d = info.get(df_)
            if d is None:
                continue
            sessions.append({"session_id": _session_id(eid, code), "event_id": eid, "season": season, "round": rnd,
                             "session_code": code, "date": str(d), "start_utc": _session_start(d, info.get(tf_))})

        def add_results(rows, code, eid=eid, rnd=rnd):
            for x in rows or []:
                pos, ptext = position_value(x.get("position"))
                results.append({
                    "event_id": eid, "season": season, "round": rnd, "session_code": code, "position": pos,
                    "position_text": ptext, "driver_id": x.get("driverId"), "constructor_id": x.get("constructorId"),
                    "driver_number": str(x.get("driverNumber")) if x.get("driverNumber") is not None else None,
                    "laps": x.get("laps"), "time_s": parse_duration_s(x.get("time")),
                    "gap_s": parse_duration_s(x.get("gap")), "time_penalty_s": parse_duration_s(x.get("timePenalty")),
                    "points": to_float(x.get("points")),
                    "grid_position": position_value(x.get("gridPosition"))[0],
                    "grid_text": position_value(x.get("gridPosition"))[1],
                    "reason_retired": x.get("reasonRetired"),
                    "outcome_category": classify_retirement(x.get("reasonRetired"), ptext),
                })
                parts.append({"event_id": eid, "season": season, "session_code": code, "driver_id": x.get("driverId"),
                              "constructor_id": x.get("constructorId"), "driver_number": x.get("driverNumber")})

        add_results(r.get("race_results"), "R")
        add_results(r.get("sprint_results"), "S")

        def add_quali(rows, code, eid=eid, rnd=rnd):
            for x in rows or []:
                pos, ptext = position_value(x.get("position"))
                q1, q2, q3 = (parse_duration_s(x.get(k)) for k in ("q1", "q2", "q3"))
                single = parse_duration_s(x.get("time"))
                best = pd.Series([q1, q2, q3, single]).min(skipna=True)
                quali.append({"event_id": eid, "season": season, "round": rnd, "session_code": code, "position": pos,
                              "position_text": ptext, "driver_id": x.get("driverId"),
                              "constructor_id": x.get("constructorId"),
                              "driver_number": str(x.get("driverNumber")) if x.get("driverNumber") is not None else None,
                              "q1_s": q1, "q2_s": q2, "q3_s": q3, "best_s": best, "laps": x.get("laps")})
                parts.append({"event_id": eid, "season": season, "session_code": code, "driver_id": x.get("driverId"),
                              "constructor_id": x.get("constructorId"), "driver_number": x.get("driverNumber")})

        add_quali(r.get("qualifying_results"), "Q")
        add_quali(r.get("sprint_qualifying_results"), "SQ")

        for key, code in (("starting_grid", "R"), ("sprint_starting_grid", "S")):
            for x in r.get(key) or []:
                pos, ptext = position_value(x.get("position"))
                grids.append({"event_id": eid, "season": season, "round": rnd, "session_code": code, "position": pos,
                              "position_text": ptext, "driver_id": x.get("driverId"),
                              "constructor_id": x.get("constructorId"), "grid_penalty": x.get("gridPenalty"),
                              "qualifying_time_s": parse_duration_s(x.get("time"))})
        for x in r.get("pit_stops") or []:
            pits.append({"event_id": eid, "season": season, "round": rnd, "driver_id": x.get("driverId"),
                         "constructor_id": x.get("constructorId"), "stop": x.get("stop"), "lap": x.get("lap"),
                         "duration_s": parse_duration_s(x.get("time"))})
        for x in r.get("fastest_laps") or []:
            pos, _ = position_value(x.get("position"))
            fastest.append({"event_id": eid, "season": season, "round": rnd, "position": pos,
                            "driver_id": x.get("driverId"), "constructor_id": x.get("constructorId"), "lap": x.get("lap"),
                            "time_s": parse_duration_s(x.get("time"))})
        for key, code in (("fp1_results", "FP1"), ("fp2_results", "FP2"), ("fp3_results", "FP3"), ("fp4_results", "FP4")):
            for x in r.get(key) or []:
                pos, _ = position_value(x.get("position"))
                practice.append({"event_id": eid, "season": season, "round": rnd, "session_code": code,
                                 "position": pos, "driver_id": x.get("driverId"), "constructor_id": x.get("constructorId"),
                                 "driver_number": str(x.get("driverNumber")) if x.get("driverNumber") is not None else None,
                                 "time_s": parse_duration_s(x.get("time")), "laps": x.get("laps")})
                parts.append({"event_id": eid, "season": season, "session_code": code, "driver_id": x.get("driverId"),
                              "constructor_id": x.get("constructorId"), "driver_number": x.get("driverNumber")})
        for x in r.get("driver_standings") or []:
            pos, _ = position_value(x.get("position"))
            dstand.append({"event_id": eid, "season": season, "round": rnd, "position": pos,
                           "driver_id": x.get("driverId"), "points": to_float(x.get("points"))})
        for x in r.get("constructor_standings") or []:
            pos, _ = position_value(x.get("position"))
            cstand.append({"event_id": eid, "season": season, "round": rnd, "position": pos,
                           "constructor_id": x.get("constructorId"), "points": to_float(x.get("points"))})

    # F1DB only records session dates from 2024 on; earlier sessions are inferred from result files.
    have = {(x["event_id"], x["session_code"]) for x in sessions}
    for x in parts:
        key = (x["event_id"], x["session_code"])
        if key not in have:
            have.add(key)
            sessions.append({"session_id": _session_id(x["event_id"], x["session_code"]), "event_id": x["event_id"],
                             "season": season, "round": int(x["event_id"].split("-")[1]),
                             "session_code": x["session_code"], "date": None, "start_utc": None})
    for x in sessions:
        x.setdefault("date_source", "f1db_schedule" if x.get("date") else "inferred_from_results")
    part_df = pd.DataFrame(parts)
    if len(part_df):
        part_df["driver_number"] = pd.to_numeric(part_df["driver_number"], errors="coerce").astype("Int64")
        part_df = part_df.drop_duplicates()
    return {
        "events": pd.DataFrame(events), "sessions": pd.DataFrame(sessions), "race_results": pd.DataFrame(results),
        "qualifying_results": pd.DataFrame(quali), "starting_grids": pd.DataFrame(grids),
        "pit_stops": pd.DataFrame(pits), "fastest_laps": pd.DataFrame(fastest),
        "practice_results": pd.DataFrame(practice), "driver_standings": pd.DataFrame(dstand),
        "constructor_standings": pd.DataFrame(cstand), "session_participants": part_df,
    }


def ingest_f1db(ctx: IngestionContext, seasons: list[int] | None = None) -> dict:
    src = ctx.f1db
    src.ensure_checkout()
    commit = src.commit() or "unknown"
    log.info("F1DB checkout at commit %s", commit)

    entities = {}
    for kind in ["drivers", "constructors", "circuits", "grands-prix", "countries"]:
        entities[kind] = src.entities(kind)
        _write_bronze(ctx, f"{commit}/entities/{kind}.json", entities[kind],
                      ProvenanceRecord(provider="f1db", dataset=f"entities/{kind}",
                                       endpoint=f"{src.repo_url}/tree/{commit}/src/data/{kind}",
                                       params={"commit": commit}))
    for name, df in entity_tables(entities).items():
        write_table(ctx.paths.silver(name), df)

    available = src.seasons()
    seasons = [s for s in (seasons or available) if s in available]
    counts = {}
    for season in seasons:
        races = src.season_races(season)
        _write_bronze(ctx, f"{commit}/seasons/{season}.json", races,
                      ProvenanceRecord(provider="f1db", dataset="season_races", season=season,
                                       endpoint=f"{src.repo_url}/tree/{commit}/src/data/seasons/{season}",
                                       params={"commit": commit}))
        tables = season_tables(season, races)
        for name, df in tables.items():
            write_partition(ctx.paths.silver(name), f"season={season}", df)
        counts[season] = {k: len(v) for k, v in tables.items()}
    seasons_df = pd.DataFrame([{"season": s, "era": era_for(s), "n_events": counts[s]["events"]} for s in seasons])
    existing = read_json(ctx.paths.manifests / "f1db_seasons.json", default=[])
    merged = {int(r["season"]): r for r in existing}
    merged.update({int(r["season"]): r for r in seasons_df.to_dict("records")})
    write_table(ctx.paths.silver("seasons"), pd.DataFrame(sorted(merged.values(), key=lambda r: r["season"])))
    write_json(ctx.paths.manifests / "f1db_seasons.json", sorted(merged.values(), key=lambda r: r["season"]))
    return {"commit": commit, "seasons": seasons, "counts": counts}
