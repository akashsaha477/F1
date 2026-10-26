"""Builds a small, controlled data directory from stored fixtures with a mocked provider (no network)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import unquote

import httpx
import pytest

from apexlens.config import settings as settings_mod
from apexlens.data_sources.http import HttpClient

FIX = Path(__file__).parents[1] / "fixtures"
TI = FIX / "tracinginsights"

TREE = [
    "Bahrain Grand Prix/Race/session_laptimes.json",
    "Bahrain Grand Prix/Race/weather.json",
    "Bahrain Grand Prix/Race/rcm.json",
    "Bahrain Grand Prix/Race/corners.json",
    "Bahrain Grand Prix/Race/drivers.json",
]
FILES = {
    "session_laptimes.json": TI / "bahrain_2024_race_laps_excerpt.json",
    "weather.json": TI / "bahrain_2024_race_weather_excerpt.json",
    "rcm.json": TI / "bahrain_2024_race_rcm_excerpt.json",
    "corners.json": TI / "bahrain_2024_corners.json",
}


class MockProvider:
    """Serves fixture files for raw.githubusercontent.com-style URLs; can inject failures."""

    def __init__(self):
        self.fail: dict[str, int] = {}
        self.calls: list[str] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        name = unquote(request.url.path.rsplit("/", 1)[-1])
        self.calls.append(name)
        if name in self.fail:
            return httpx.Response(self.fail[name])
        if name in FILES:
            return httpx.Response(200, content=FILES[name].read_bytes())
        return httpx.Response(404)


def make_context(tmp_path: Path, provider: MockProvider, monkeypatch):
    monkeypatch.setenv("APEXLENS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APEXLENS_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("APEXLENS_F1DB_LOCAL_PATH", str(FIX / "f1db_repo"))
    settings_mod.get_settings.cache_clear()
    from apexlens.ingestion.context import IngestionContext

    ctx = IngestionContext.create()
    ctx.__dict__["http"] = HttpClient(cache_dir=None, transport=httpx.MockTransport(provider), sleep=lambda s: None,
                                      max_retries=1)
    monkeypatch.setattr(ctx.tracinginsights, "list_tree", lambda season, refresh=False: TREE)
    return ctx


@pytest.fixture
def provider():
    return MockProvider()


@pytest.fixture
def ingested(tmp_path, provider, monkeypatch):
    from apexlens.ingestion.coverage import build_coverage_report
    from apexlens.ingestion.f1db_ingest import ingest_f1db
    from apexlens.ingestion.laps_ingest import ingest_lap_timing

    ctx = make_context(tmp_path, provider, monkeypatch)
    ingest_f1db(ctx, [2024])
    statuses = ingest_lap_timing(ctx, 2024, codes=("R",))
    build_coverage_report(ctx)
    yield ctx, statuses
    settings_mod.get_settings.cache_clear()


def read_json(p: Path):
    return json.loads(p.read_text())
