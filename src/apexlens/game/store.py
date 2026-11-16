"""One JSON file per race under ``data/game/events``; writes are atomic and serialised with a lock."""

from __future__ import annotations

import re
import threading
from pathlib import Path

from apexlens.storage.io import read_json, write_json

EVENT_ID = re.compile(r"^\d{4}-\d{2}$")


class GameStore:
    def __init__(self, root: Path):
        self.root = Path(root) / "game"
        self.lock = threading.RLock()

    def path(self, event_id: str) -> Path:
        if not EVENT_ID.match(event_id):
            raise ValueError(f"invalid event id {event_id!r}")
        return self.root / "events" / f"{event_id}.json"

    def load(self, event_id: str) -> dict | None:
        return read_json(self.path(event_id), default=None)

    def save(self, event: dict) -> None:
        with self.lock:
            write_json(self.path(event["event_id"]), event)

    def all(self) -> list[dict]:
        d = self.root / "events"
        if not d.exists():
            return []
        return [read_json(p) for p in sorted(d.glob("*.json"))]
