"""Source catalogue and provenance registry.

Every retrieval (successful or not) is appended to ``manifests/provenance.jsonl``. The registry
can be summarised per provider/dataset/season so the application can show which sources back
a given analysis.
"""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from apexlens.data_sources.http import utc_now_iso

SCHEMA_VERSION = "1"

SOURCE_CATALOG: dict[str, dict] = {
    "f1db": {
        "name": "F1DB",
        "url": "https://github.com/f1db/f1db",
        "licence": "CC BY 4.0 (attribution required)",
        "coverage": "World Championship 1950-present: drivers, constructors, circuits, schedules, results, "
                    "qualifying, grids, pit stops, standings",
        "role": "Canonical identities and historical results",
        "notes": "Read from a local git checkout or individual YAML files on raw.githubusercontent.com.",
    },
    "tracinginsights": {
        "name": "TracingInsights FastF1 archive",
        "url": "https://github.com/TracingInsights",
        "licence": "Season repositories declare MIT (2022-2024) or Apache 2.0 (2025-2026). Timing/telemetry "
                   "originates from the Formula 1 live timing service via FastF1 and is unofficial; use for "
                   "non-commercial research.",
        "coverage": "2018-present per-season repositories: per-session lap timing (all laps, sectors, tyres, "
                    "track status, joined weather), weather series, race-control messages, FastF1 corner markers, "
                    "per-lap car telemetry with position.",
        "role": "Lap timing, tyres, weather, race control, telemetry (FastF1-derived export)",
        "notes": "Used because FastF1's own backend (livetiming.formula1.com) was not reachable from the build "
                 "environment. Values are FastF1 outputs serialised to JSON; acceleration channels in telemetry "
                 "are derived by the archive author, not measured.",
    },
    "fastf1": {
        "name": "FastF1",
        "url": "https://docs.fastf1.dev/",
        "licence": "MIT library; F1 timing data is unofficial",
        "coverage": "2018-present timing and telemetry",
        "role": "Primary live source when livetiming.formula1.com is reachable",
        "notes": "Adapter implemented and tested against mocked sessions; not reachable from the build environment.",
    },
    "jolpica": {
        "name": "Jolpica-F1 (Ergast-compatible)",
        "url": "https://github.com/jolpica/jolpica-f1",
        "licence": "See provider documentation; rate limited",
        "coverage": "1950-present results, schedules, standings, laps, pit stops",
        "role": "Alternative historical results source",
        "notes": "Adapter implemented and tested with mocked responses; host not reachable from the build environment.",
    },
    "openf1": {
        "name": "OpenF1",
        "url": "https://openf1.org/",
        "licence": "Unofficial provider; review terms before public or commercial use",
        "coverage": "2023-present sessions, laps, stints, weather, pit, race control, positions, overtakes, car data",
        "role": "Supplementary source (e.g. overtakes)",
        "notes": "Adapter implemented and tested with mocked responses; host not reachable from the build environment.",
    },
}


@dataclass
class ProvenanceRecord:
    provider: str
    dataset: str
    endpoint: str
    season: int | None = None
    event: str | None = None
    session: str | None = None
    params: dict = field(default_factory=dict)
    retrieved_at: str = field(default_factory=utc_now_iso)
    schema_version: str = SCHEMA_VERSION
    status: str = "ok"  # ok | error | missing | skipped
    error: str | None = None
    content_hash: str | None = None
    n_bytes: int | None = None
    from_cache: bool = False
    bronze_path: str | None = None
    licence: str | None = None

    def __post_init__(self):
        if self.licence is None and self.provider in SOURCE_CATALOG:
            self.licence = SOURCE_CATALOG[self.provider]["licence"]


class ProvenanceRegistry:
    def __init__(self, manifests_dir: Path):
        self.path = Path(manifests_dir) / "provenance.jsonl"
        self._lock = threading.Lock()

    def record(self, rec: ProvenanceRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(rec), default=str)
        with self._lock, self.path.open("a") as fh:
            fh.write(line + "\n")

    def load(self) -> pd.DataFrame:
        if not self.path.exists():
            return pd.DataFrame(columns=[f.name for f in ProvenanceRecord.__dataclass_fields__.values()])
        rows = [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]
        return pd.DataFrame(rows)

    def latest(self) -> pd.DataFrame:
        """Most recent record per (provider, dataset, endpoint)."""
        df = self.load()
        if df.empty:
            return df
        df = df.sort_values("retrieved_at")
        return df.drop_duplicates(["provider", "dataset", "endpoint"], keep="last")

    def summary(self) -> list[dict]:
        df = self.latest()
        if df.empty:
            return []
        out = []
        for (prov, ds), g in df.groupby(["provider", "dataset"]):
            out.append({
                "provider": prov,
                "dataset": ds,
                "seasons": sorted({int(s) for s in g["season"].dropna()}),
                "n_items": int(len(g)),
                "n_ok": int((g["status"] == "ok").sum()),
                "n_missing": int((g["status"] == "missing").sum()),
                "n_error": int((g["status"] == "error").sum()),
                "bytes": int(pd.to_numeric(g["n_bytes"], errors="coerce").fillna(0).sum()),
                "first_retrieved": str(g["retrieved_at"].min()),
                "last_retrieved": str(g["retrieved_at"].max()),
                "licence": SOURCE_CATALOG.get(prov, {}).get("licence"),
            })
        return out
