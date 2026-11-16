"""Prediction game from the command line.

    python scripts/game.py settle 2026-21 --fetch   # after the weekend: pull results, score everyone
    python scripts/game.py settle-due --fetch       # the same for every race that has started (cron)
    python scripts/game.py open 2026-22             # freeze the model's order for the next race now
    python scripts/game.py leaderboard --season 2026
"""

import sys

from apexlens.cli import main as cli

if __name__ == "__main__":
    sys.exit(cli(["game", *sys.argv[1:]]))
