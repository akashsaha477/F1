"""Adapter for the TracingInsights FastF1 export archive (https://github.com/TracingInsights).

Each season is a public repository laid out as::

    {Event Name}/{Session Name}/session_laptimes.json   all laps of the session (FastF1 ``Laps``)
    {Event Name}/{Session Name}/weather.json            FastF1 ``weather_data``
    {Event Name}/{Session Name}/rcm.json                race-control messages
    {Event Name}/{Session Name}/corners.json            FastF1 ``CircuitInfo.corners`` + rotation
    {Event Name}/{Session Name}/drivers.json            session participants (abbreviation, team, number)
    {Event Name}/{Session Name}/{DRV}/{lap}_tel.json    FastF1 car + position telemetry for one lap

Files are fetched from raw.githubusercontent.com through the shared :class:`HttpClient` (cached,
rate limited, retried). The list of available files is discovered from a blob-less git listing of
the repository (cheap: no file contents are transferred); when git is unavailable the caller can
probe candidate paths instead.
"""

from __future__ import annotations

import gzip
import logging
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from apexlens.data_sources.http import FetchResult, HttpClient

log = logging.getLogger(__name__)

# Directory name -> canonical session code. 2021-2022 FastF1 named the Saturday sprint
# "Sprint Qualifying"; from 2023 the Friday/Saturday shoot-out is "Sprint Shootout"/"Sprint Qualifying".
SESSION_DIR_CODES = {
    "Practice 1": "FP1",
    "Practice 2": "FP2",
    "Practice 3": "FP3",
    "Qualifying": "Q",
    "Sprint Shootout": "SQ",
    "Sprint Qualifying": "SQ",
    "Sprint": "S",
    "Race": "R",
}

SESSION_FILES = ["session_laptimes.json", "weather.json", "rcm.json", "corners.json", "drivers.json"]


def session_code_for(dir_name: str, season: int) -> str | None:
    if dir_name == "Sprint Qualifying" and season <= 2022:
        # In 2021-2022 "Sprint Qualifying" was the sprint race itself.
        return "S_LEGACY"
    return SESSION_DIR_CODES.get(dir_name)


@dataclass
class SessionIndex:
    event: str
    session: str
    files: set[str] = field(default_factory=set)
    telemetry: dict[str, set[int]] = field(default_factory=lambda: defaultdict(set))


@dataclass
class SeasonIndex:
    season: int
    sessions: dict[tuple[str, str], SessionIndex] = field(default_factory=dict)
    source: str = "git"

    def events(self) -> list[str]:
        return sorted({e for e, _ in self.sessions})

    def session_names(self, event: str) -> list[str]:
        return sorted(s for e, s in self.sessions if e == event)


def parse_tree_listing(season: int, paths: list[str]) -> SeasonIndex:
    idx = SeasonIndex(season=season)
    for p in paths:
        parts = p.split("/")
        if len(parts) < 3:
            continue
        event, session = parts[0], parts[1]
        if session not in SESSION_DIR_CODES or event.startswith(".") or event.lower().startswith("pre-season"):
            continue
        si = idx.sessions.setdefault((event, session), SessionIndex(event, session))
        if len(parts) == 3:
            si.files.add(parts[2])
        elif len(parts) == 4 and parts[3].endswith("_tel.json"):
            lap = parts[3][: -len("_tel.json")]
            if lap.isdigit():
                si.telemetry[parts[2]].add(int(lap))
    # keep only sessions that actually have lap timing
    idx.sessions = {k: v for k, v in idx.sessions.items() if "session_laptimes.json" in v.files}
    return idx


class TracingInsightsSource:
    provider = "tracinginsights"

    def __init__(self, http: HttpClient, raw_base: str, git_base: str, cache_dir: Path, branch: str = "main"):
        self.http = http
        self.raw_base = raw_base.rstrip("/")
        self.git_base = git_base.rstrip("/")
        self.cache_dir = Path(cache_dir)
        self.branch = branch

    def repo_url(self, season: int) -> str:
        return f"{self.git_base}/{season}"

    def url(self, season: int, *parts: str) -> str:
        path = "/".join(quote(p) for p in parts)
        return f"{self.raw_base}/{season}/{self.branch}/{path}"

    # -- discovery -------------------------------------------------------------------------
    def _tree_cache(self, season: int) -> Path:
        return self.cache_dir / "tracinginsights" / f"tree_{season}.txt.gz"

    def list_tree(self, season: int, refresh: bool = False) -> list[str]:
        """File paths of the season repository (blob-less shallow clone, cached)."""
        cache = self._tree_cache(season)
        if cache.exists() and not refresh:
            return gzip.decompress(cache.read_bytes()).decode().splitlines()
        cache.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache.parent) as tmp:
            repo = Path(tmp) / "repo"
            subprocess.run(
                ["git", "clone", "-q", "--depth", "1", "--filter=blob:none", "--no-checkout",
                 self.repo_url(season), str(repo)],
                check=True, capture_output=True, timeout=900,
            )
            out = subprocess.run(
                ["git", "-C", str(repo), "-c", "core.quotepath=off", "ls-tree", "-r", "--name-only", "HEAD"],
                check=True, capture_output=True, timeout=300,
            )
        text = out.stdout.decode("utf-8")
        cache.write_bytes(gzip.compress(text.encode()))
        return text.splitlines()

    def discover(self, season: int, refresh: bool = False) -> SeasonIndex:
        return parse_tree_listing(season, self.list_tree(season, refresh=refresh))

    # -- fetching --------------------------------------------------------------------------
    def fetch_session_file(self, season: int, event: str, session: str, filename: str) -> FetchResult:
        return self.http.get(self.url(season, event, session, filename))

    def fetch_lap_telemetry(self, season: int, event: str, session: str, driver: str, lap: int) -> FetchResult:
        return self.http.get(self.url(season, event, session, driver, f"{lap}_tel.json"))
