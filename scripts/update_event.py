"""Refresh a single event (results, lap timing and optionally telemetry), e.g. ``python scripts/update_event.py 2025-24``."""

import sys

from apexlens.cli import main as cli

if __name__ == "__main__":
    sys.exit(cli(["update-event", *sys.argv[1:]]))
