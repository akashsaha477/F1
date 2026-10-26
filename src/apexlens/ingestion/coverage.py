"""Data coverage report: what was ingested, what is missing, and which analyses it supports."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd

from apexlens.data_sources.http import utc_now_iso
from apexlens.data_sources.registry import SOURCE_CATALOG
from apexlens.ingestion.context import IngestionContext
from apexlens.storage.io import read_json, read_table, write_json

LAP_SESSION_CODES = ["FP1", "FP2", "FP3", "Q", "SQ", "S", "R"]
LAP_COLUMNS = ["session_id", "season", "session_code", "driver_id", "circuit_id", "compound", "tyre_life_laps",
               "track_temp_c", "lap_start_utc", "is_clean", "condition", "rainfall", "lap_time_s"]


def _pct(a, b) -> float | None:
    return round(100.0 * a / b, 1) if b else None


def build_coverage_report(ctx: IngestionContext) -> dict:
    p = ctx.paths
    seasons = read_table(p.silver("seasons"))
    f1db_sessions = read_table(p.silver("sessions"))
    ingested = pd.DataFrame(read_json(p.manifests / "sessions_ingested.json", default=[]))
    laps = read_table(p.silver("laps"), columns=LAP_COLUMNS)
    tel = read_table(p.silver("telemetry_laps"))
    weather = read_table(p.silver("weather_observations"), columns=["session_id"])
    prov = ctx.registry.latest()
    ident = read_table(p.manifests / "identity_mapping")

    lap_seasons = sorted(ingested["season"].unique().tolist()) if len(ingested) else []
    rep: dict = {"generated_at": utc_now_iso(), "sources": {}}
    rep["sources"]["f1db"] = {
        "seasons": [int(seasons["season"].min()), int(seasons["season"].max())] if len(seasons) else [],
        "n_seasons": int(len(seasons)), "licence": SOURCE_CATALOG["f1db"]["licence"]}
    rep["sources"]["tracinginsights"] = {"seasons": [int(s) for s in lap_seasons],
                                         "licence": SOURCE_CATALOG["tracinginsights"]["licence"]}
    for name in ("fastf1", "jolpica", "openf1"):
        rep["sources"][name] = {"seasons": [], "status": "adapter implemented; host unreachable from build environment"}

    per_season = []
    for season in lap_seasons:
        fs = f1db_sessions[(f1db_sessions.season == season) & f1db_sessions.session_code.isin(LAP_SESSION_CODES)]
        ing = ingested[(ingested.season == season) & (ingested.get("n_laps", 0).fillna(0) > 0)]
        ls = laps[laps.season == season]
        ts = tel[tel.season == season] if len(tel) else tel
        q_sessions = ing[ing.session_code.isin(["Q", "SQ"])]
        valid_tyre = ls["compound"].isin(["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]) & ls["tyre_life_laps"].notna()
        per_season.append({
            "season": int(season),
            "f1db_sessions": int(len(fs)),
            "sessions_with_timing": int(len(ing)),
            "pct_sessions_with_timing": _pct(len(ing), len(fs)),
            "sessions_by_code": {k: int(v) for k, v in Counter(ing["session_code"]).items()},
            "quali_sessions_with_telemetry": int(ts["session_id"].nunique()) if len(ts) else 0,
            "pct_quali_sessions_with_telemetry": _pct(ts["session_id"].nunique() if len(ts) else 0, len(q_sessions)),
            "telemetry_laps": int(len(ts)),
            "laps": int(len(ls)),
            "clean_laps": int(ls["is_clean"].sum()),
            "pct_laps_valid_tyre_info": _pct(int(valid_tyre.sum()), len(ls)),
            "pct_laps_with_weather": _pct(int(ls["track_temp_c"].notna().sum()), len(ls)),
            "sessions_with_weather_series": int(weather[weather.session_id.isin(ing.session_id)]["session_id"].nunique())
            if len(weather) else 0,
            "pct_laps_missing_start_timestamp": _pct(int(ls["lap_start_utc"].isna().sum()), len(ls)),
            "wet_laps": int((ls["condition"] == "wet").sum()),
            "wet_clean_laps": int(((ls["condition"] == "wet") & ls["is_clean"]).sum()),
            "sessions_with_wet_running": int(ls[ls["condition"] == "wet"]["session_id"].nunique()),
            "damp_laps": int((ls["condition"] == "damp").sum()),
        })
    rep["per_season"] = per_season

    # quality manifests
    qdir = p.manifests / "quality"
    fail_counts: Counter = Counter()
    fatal_sessions = []
    for f in sorted(qdir.glob("*.json")) if qdir.exists() else []:
        q = read_json(f)
        for c in q["checks"]:
            if not c["passed"]:
                fail_counts[(c["name"], c["severity"])] += c["n_failed"]
        if q["status"] == "failed":
            fatal_sessions.append({"partition": f.stem, "fatal": q["fatal"]})
    rep["quality"] = {
        "failed_checks": [{"check": k[0], "severity": k[1], "n_rows": v} for k, v in sorted(fail_counts.items())],
        "partitions_with_fatal_failures": fatal_sessions,
    }
    rep["duplicates"] = {"duplicate_lap_rows": int(fail_counts.get(("duplicate_laps", "fatal"), 0))}
    unresolved = ident[ident["method"] == "unresolved"] if len(ident) else ident
    rep["entity_mapping"] = {
        "driver_session_pairs": int(len(ident)),
        "methods": {k: int(v) for k, v in Counter(ident["method"]).items()} if len(ident) else {},
        "unresolved": unresolved.to_dict("records") if len(unresolved) else [],
        "unresolved_events": [r for s in lap_seasons for r in read_json(p.manifests / "event_mapping" / f"{s}.json", [])
                              if not r.get("event_id")],
    }
    if len(prov):
        errs = prov[prov["status"] == "error"]
        miss = prov[prov["status"] == "missing"]
        rep["requests"] = {
            "n_items": int(len(prov)), "n_errors": int(len(errs)), "n_missing": int(len(miss)),
            "errors": errs[["provider", "dataset", "endpoint", "error"]].head(50).to_dict("records"),
            "missing_by_dataset": {k: int(v) for k, v in Counter(miss["dataset"]).items()},
        }

    # driver x circuit x condition coverage (race + sprint clean laps)
    rl = laps[laps.session_code.isin(["R", "S"]) & laps["is_clean"]]
    if len(rl):
        g = rl.groupby(["season", "driver_id", "circuit_id", "condition"]).size().unstack(fill_value=0)
        dry = g.get("dry", pd.Series(0, index=g.index)) + g.get("dry_unverified", pd.Series(0, index=g.index))
        wet = g.get("wet", pd.Series(0, index=g.index))
        dw = pd.DataFrame({"dry": dry, "wet": wet}).reset_index()
        per_driver = dw.groupby(["season", "driver_id"]).agg(circuits=("circuit_id", "nunique"),
                                                               circuits_with_wet=("wet", lambda s: int((s > 0).sum())),
                                                               wet_laps=("wet", "sum")).reset_index()
        rep["condition_coverage"] = {
            "driver_circuit_pairs": int(len(dw)),
            "pairs_with_clean_dry_race_laps": int((dw["dry"] > 0).sum()),
            "pairs_with_clean_wet_race_laps": int((dw["wet"] > 0).sum()),
            "driver_seasons_without_wet_race_laps": int((per_driver["wet_laps"] == 0).sum()),
            "driver_seasons": int(len(per_driver)),
        }

    tot = {k: sum(s[k] for s in per_season) for k in ("laps", "clean_laps", "telemetry_laps", "wet_clean_laps",
                                                       "sessions_with_timing")}
    analyses = [
        {"analysis": "Historical results-only driver profiles", "supported": bool(len(seasons)),
         "evidence": f"F1DB seasons {rep['sources']['f1db']['seasons']}"},
        {"analysis": "Lap-time / relative pace modelling", "supported": tot["clean_laps"] > 1000,
         "evidence": f"{tot['clean_laps']} clean laps in {tot['sessions_with_timing']} sessions"},
        {"analysis": "Tyre degradation (compound, tyre age, stints)", "supported": tot["clean_laps"] > 1000,
         "evidence": "compound and tyre age per lap available"},
        {"analysis": "Wet-weather performance", "supported": tot["wet_clean_laps"] > 0,
         "evidence": f"{tot['wet_clean_laps']} clean laps on intermediate/wet tyres; sparse and confounded",
         "limitation": "Evidence is sparse; estimates are shrunk and many drivers return insufficient evidence."},
        {"analysis": "Corner-level telemetry analysis", "supported": tot["telemetry_laps"] > 0,
         "evidence": f"{tot['telemetry_laps']} telemetry laps (bounded: fastest qualifying laps)",
         "limitation": "Race-lap telemetry is not ingested by default; corner metrics describe qualifying laps."},
        {"analysis": "Overtakes", "supported": False,
         "evidence": "Only OpenF1 provides overtakes; host unreachable from the build environment",
         "limitation": "Position changes are derived from grid vs. finish and lap positions instead."},
        {"analysis": "Steering / brake pressure / tyre force", "supported": False,
         "evidence": "Not present in any source (brake is on/off only)"},
    ]
    rep["analyses"] = analyses
    rep["summary"] = {"lap_seasons": lap_seasons, **tot,
                      "f1db_seasons": rep["sources"]["f1db"]["seasons"],
                      "fatal_partitions": len(fatal_sessions),
                      "unresolved_driver_pairs": len(rep["entity_mapping"]["unresolved"])}
    write_json(p.manifests / "coverage_report.json", rep)
    write_markdown(rep, Path(ctx.settings.reports_dir) / "coverage_report.md")
    return rep


def write_markdown(rep: dict, path: Path) -> None:
    lines = ["# Data coverage report", "", f"Generated: {rep['generated_at']} (by `apexlens coverage`)", "",
             "## Sources", "", "| Source | Seasons | Licence / status |", "|---|---|---|"]
    for k, v in rep["sources"].items():
        lines.append(f"| {k} | {v.get('seasons')} | {v.get('licence') or v.get('status', '')} |")
    lines += ["", "## Per season (lap-level sources)", "",
              "| Season | F1DB sessions | Sessions with timing | % | Laps | Clean laps | % valid tyre | % weather | "
              "Q/SQ sessions w/ telemetry | Telemetry laps | Wet clean laps | Sessions w/ wet running |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in rep["per_season"]:
        lines.append(f"| {s['season']} | {s['f1db_sessions']} | {s['sessions_with_timing']} | {s['pct_sessions_with_timing']} | "
                     f"{s['laps']} | {s['clean_laps']} | {s['pct_laps_valid_tyre_info']} | {s['pct_laps_with_weather']} | "
                     f"{s['quali_sessions_with_telemetry']} ({s['pct_quali_sessions_with_telemetry']}%) | {s['telemetry_laps']} | {s['wet_clean_laps']} | "
                     f"{s['sessions_with_wet_running']} |")
    lines += ["", "## Supported analyses", "", "| Analysis | Supported | Evidence | Limitation |", "|---|---|---|---|"]
    for a in rep["analyses"]:
        lines.append(f"| {a['analysis']} | {'yes' if a['supported'] else 'no'} | {a['evidence']} | {a.get('limitation', '')} |")
    lines += ["", "## Data quality", "", "| Check | Severity | Rows flagged |", "|---|---|---|"]
    for c in rep["quality"]["failed_checks"]:
        lines.append(f"| {c['check']} | {c['severity']} | {c['n_rows']} |")
    lines += ["", f"Partitions with fatal failures: {len(rep['quality']['partitions_with_fatal_failures'])}"]
    for f in rep["quality"]["partitions_with_fatal_failures"]:
        lines.append(f"- `{f['partition']}`: {', '.join(f['fatal'])}")
    em = rep["entity_mapping"]
    lines += ["", "## Entity mapping", "", f"Driver-session pairs resolved: {em['driver_session_pairs']}; methods: {em['methods']}",
              f"Unresolved driver pairs: {len(em['unresolved'])}; unresolved events: {len(em['unresolved_events'])}"]
    if "requests" in rep:
        r = rep["requests"]
        lines += ["", "## Requests", "", f"Items: {r['n_items']}, errors: {r['n_errors']}, missing (404): {r['n_missing']}",
                  f"Missing by dataset: {r['missing_by_dataset']}"]
    if "condition_coverage" in rep:
        c = rep["condition_coverage"]
        lines += ["", "## Driver × circuit × condition coverage (clean race/sprint laps)", "",
                  f"- Driver-circuit pairs: {c['driver_circuit_pairs']}",
                  f"- With clean dry laps: {c['pairs_with_clean_dry_race_laps']}",
                  f"- With clean wet laps: {c['pairs_with_clean_wet_race_laps']}",
                  f"- Driver-seasons without any clean wet race lap: {c['driver_seasons_without_wet_race_laps']} of {c['driver_seasons']}"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")
