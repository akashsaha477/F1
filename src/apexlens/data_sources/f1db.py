"""F1DB source adapter (https://github.com/f1db/f1db, CC BY 4.0).

F1DB stores its data as YAML under ``src/data``. The adapter reads a local checkout. When none is
configured it creates a shallow, sparse git checkout of ``src/data`` (git reads of public GitHub
repositories) under the cache directory.
"""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

_INT = "tag:yaml.org,2002:int"
_FLOAT = "tag:yaml.org,2002:float"


class F1DBLoader(yaml.CSafeLoader if hasattr(yaml, "CSafeLoader") else yaml.SafeLoader):  # type: ignore[misc]
    """YAML loader without YAML 1.1 sexagesimal numbers (``15:00`` must stay a string)."""


F1DBLoader.yaml_implicit_resolvers = {
    k: [(t, r) for t, r in v if t not in (_INT, _FLOAT)]
    for k, v in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
F1DBLoader.add_implicit_resolver(_INT, re.compile(r"^[-+]?(?:0|[1-9][0-9_]*)$"), list("-+0123456789"))
F1DBLoader.add_implicit_resolver(
    _FLOAT,
    re.compile(r"^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?|[-+]?\.(?:inf|Inf|INF)|\.(?:nan|NaN|NAN))$"),
    list("-+0123456789."),
)


def load_yaml_text(text: str) -> Any:
    return yaml.load(text, Loader=F1DBLoader)


RACE_FILES = {
    "race": "race.yml",
    "race_results": "race-results.yml",
    "qualifying_results": "qualifying-results.yml",
    "starting_grid": "starting-grid-positions.yml",
    "pit_stops": "pit-stops.yml",
    "fastest_laps": "fastest-laps.yml",
    "driver_standings": "driver-standings.yml",
    "constructor_standings": "constructor-standings.yml",
    "fp1_results": "free-practice-1-results.yml",
    "fp2_results": "free-practice-2-results.yml",
    "fp3_results": "free-practice-3-results.yml",
    "fp4_results": "free-practice-4-results.yml",
    "sprint_qualifying_results": "sprint-qualifying-results.yml",
    "sprint_results": "sprint-race-results.yml",
    "sprint_starting_grid": "sprint-starting-grid-positions.yml",
}

ENTITY_DIRS = ["drivers", "constructors", "circuits", "grands-prix", "countries", "engine-manufacturers"]


class F1DBSource:
    provider = "f1db"
    repo_url = "https://github.com/f1db/f1db"

    def __init__(self, local_path: Path | None = None, cache_dir: Path | None = None):
        self._local_path = Path(local_path) if local_path else None
        self._cache_dir = Path(cache_dir) if cache_dir else None

    # -- checkout handling -----------------------------------------------------------------
    @property
    def repo_path(self) -> Path:
        if self._local_path:
            return self._local_path
        if not self._cache_dir:
            raise RuntimeError("F1DB needs either a local checkout path or a cache directory")
        return self._cache_dir / "f1db_repo"

    @property
    def data_path(self) -> Path:
        return self.repo_path / "src" / "data"

    def ensure_checkout(self) -> Path:
        """Return the data directory, cloning a sparse shallow checkout when needed."""
        if self.data_path.exists():
            return self.data_path
        if self._local_path:
            raise FileNotFoundError(f"F1DB checkout not found at {self._local_path}")
        target = self.repo_path
        target.parent.mkdir(parents=True, exist_ok=True)
        log.info("cloning F1DB (sparse, shallow) into %s", target)
        subprocess.run(
            ["git", "clone", "--depth", "1", "--filter=blob:none", "--sparse", self.repo_url, str(target)],
            check=True, capture_output=True, timeout=900,
        )
        subprocess.run(["git", "-C", str(target), "sparse-checkout", "set", "src/data"],
                       check=True, capture_output=True, timeout=900)
        return self.data_path

    def commit(self) -> str | None:
        try:
            out = subprocess.run(["git", "-C", str(self.repo_path), "rev-parse", "HEAD"],
                                 check=True, capture_output=True, text=True, timeout=30)
            return out.stdout.strip()
        except (subprocess.SubprocessError, FileNotFoundError):
            return None

    # -- reading ---------------------------------------------------------------------------
    def _read(self, path: Path) -> Any:
        return load_yaml_text(path.read_text(encoding="utf-8"))

    def entities(self, kind: str) -> list[dict]:
        if kind not in ENTITY_DIRS:
            raise ValueError(f"unknown F1DB entity kind {kind}")
        d = self.ensure_checkout() / kind
        return [self._read(p) for p in sorted(d.glob("*.yml"))]

    def seasons(self) -> list[int]:
        d = self.ensure_checkout() / "seasons"
        return sorted(int(p.name) for p in d.iterdir() if p.is_dir() and p.name.isdigit())

    def season_file(self, season: int, name: str) -> Any:
        p = self.ensure_checkout() / "seasons" / str(season) / name
        return self._read(p) if p.exists() else None

    def race_dirs(self, season: int) -> list[Path]:
        d = self.ensure_checkout() / "seasons" / str(season) / "races"
        if not d.exists():
            return []
        return sorted(p for p in d.iterdir() if p.is_dir())

    def race(self, race_dir: Path) -> dict[str, Any]:
        """All available YAML files of one race keyed by logical name (missing files omitted)."""
        out: dict[str, Any] = {"slug": race_dir.name}
        for key, fname in RACE_FILES.items():
            p = race_dir / fname
            if p.exists():
                out[key] = self._read(p)
        return out

    def season_races(self, season: int) -> list[dict[str, Any]]:
        return [self.race(d) for d in self.race_dirs(season)]
