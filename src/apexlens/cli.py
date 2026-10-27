"""Command-line entry point: ``apexlens <command> [options]``.

Commands are bounded by default: nothing downloads full-history telemetry unless explicitly asked.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from apexlens.ingestion.context import IngestionContext, configure_logging

log = logging.getLogger("apexlens.cli")


def _seasons(arg: str | None, ctx: IngestionContext) -> list[int]:
    if not arg:
        return ctx.settings.seasons
    out: list[int] = []
    for part in arg.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part.strip():
            out.append(int(part))
    return out


def cmd_ingest_f1db(args, ctx):
    from apexlens.ingestion.f1db_ingest import ingest_f1db

    seasons = None if args.all_history else _seasons(args.seasons, ctx)
    res = ingest_f1db(ctx, seasons)
    print(json.dumps({"commit": res["commit"], "seasons": len(res["seasons"])}))


def cmd_ingest_laps(args, ctx):
    from apexlens.ingestion.laps_ingest import ALL_SESSION_CODES, ingest_lap_timing

    codes = tuple(args.sessions.split(",")) if args.sessions else ALL_SESSION_CODES
    events = args.events.split(",") if args.events else None
    for season in _seasons(args.seasons, ctx):
        if args.max_events and not events:
            from apexlens.ingestion.laps_ingest import event_mapping

            idx = ctx.tracinginsights.discover(season)
            emap = event_mapping(ctx, season, idx).dropna(subset=["event_id"]).sort_values("event_id")
            season_events = emap["event_id"].head(args.max_events).tolist()
        else:
            season_events = events
        st = ingest_lap_timing(ctx, season, codes=codes, events=season_events)
        ok = sum(1 for s in st if s.get("quality_status") in ("ok", "warning"))
        print(json.dumps({"season": season, "sessions": len(st), "usable": ok}))


def cmd_ingest_telemetry(args, ctx):
    from apexlens.ingestion.telemetry_ingest import ingest_telemetry

    codes = tuple(args.sessions.split(",")) if args.sessions else ("Q",)
    for season in _seasons(args.seasons, ctx):
        res = ingest_telemetry(ctx, season, codes=codes, laps_per_driver=args.laps_per_driver,
                               events=args.events.split(",") if args.events else None, max_events=args.max_events)
        print(json.dumps({"season": season, **res}))


def cmd_update_event(args, ctx):
    from apexlens.ingestion.f1db_ingest import ingest_f1db
    from apexlens.ingestion.laps_ingest import ingest_lap_timing
    from apexlens.ingestion.telemetry_ingest import ingest_telemetry

    season = int(args.event.split("-")[0])
    ingest_f1db(ctx, [season])
    ingest_lap_timing(ctx, season, events=[args.event], refresh_index=True)
    if args.telemetry:
        ingest_telemetry(ctx, season, events=[args.event], laps_per_driver=args.laps_per_driver)
    print(json.dumps({"updated": args.event}))


def cmd_coverage(args, ctx):
    from apexlens.ingestion.coverage import build_coverage_report

    rep = build_coverage_report(ctx)
    print(json.dumps(rep["summary"], indent=2))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="apexlens", description=__doc__)
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("ingest-f1db", help="historical results and canonical entities from F1DB")
    s.add_argument("--seasons", help="e.g. 2022-2026 or 2023,2024 (default: configured seasons)")
    s.add_argument("--all-history", action="store_true", help="every season available in F1DB (1950-present)")
    s.set_defaults(func=cmd_ingest_f1db)

    s = sub.add_parser("ingest-laps", help="lap timing, tyres, weather, race control (bounded by seasons/events)")
    s.add_argument("--seasons")
    s.add_argument("--events", help="event ids such as 2024-01,2024-21")
    s.add_argument("--sessions", help="session codes, default FP1,FP2,FP3,Q,SQ,S,R")
    s.add_argument("--max-events", type=int, help="only the first N events of each season")
    s.set_defaults(func=cmd_ingest_laps)

    s = sub.add_parser("ingest-telemetry", help="bounded per-lap car telemetry (fastest laps only)")
    s.add_argument("--seasons")
    s.add_argument("--events")
    s.add_argument("--sessions", help="default Q")
    s.add_argument("--laps-per-driver", type=int, default=1)
    s.add_argument("--max-events", type=int)
    s.set_defaults(func=cmd_ingest_telemetry)

    s = sub.add_parser("update-event", help="refresh one event, e.g. 2025-24")
    s.add_argument("event")
    s.add_argument("--telemetry", action="store_true")
    s.add_argument("--laps-per-driver", type=int, default=1)
    s.set_defaults(func=cmd_update_event)

    s = sub.add_parser("coverage", help="write the data coverage report")
    s.set_defaults(func=cmd_coverage)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(logging.DEBUG if args.verbose else logging.INFO)
    ctx = IngestionContext.create()
    args.func(args, ctx)
    return 0


if __name__ == "__main__":
    sys.exit(main())
