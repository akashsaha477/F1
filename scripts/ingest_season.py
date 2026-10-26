"""Ingest one or more seasons (bounded).

Examples:
    python scripts/ingest_season.py --seasons 2024 --max-events 3          # small initial dataset
    python scripts/ingest_season.py --seasons 2022-2025 --telemetry        # default research dataset
"""

import argparse
import sys

from apexlens.cli import main as cli

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seasons", required=True)
    p.add_argument("--max-events", type=int)
    p.add_argument("--telemetry", action="store_true", help="also fetch fastest qualifying-lap telemetry")
    p.add_argument("--laps-per-driver", type=int, default=1)
    a = p.parse_args()
    extra = ["--max-events", str(a.max_events)] if a.max_events else []
    cli(["ingest-f1db", "--seasons", a.seasons])
    cli(["ingest-laps", "--seasons", a.seasons, *extra])
    if a.telemetry:
        cli(["ingest-telemetry", "--seasons", a.seasons, "--sessions", "Q,SQ", "--laps-per-driver",
             str(a.laps_per_driver), *extra])
    sys.exit(cli(["coverage"]))
