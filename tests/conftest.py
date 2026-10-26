from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def ti_laps_payload() -> dict:
    return json.loads((FIXTURES / "tracinginsights" / "bahrain_2024_race_laps_excerpt.json").read_text())


@pytest.fixture
def ti_tel_payload() -> dict:
    return json.loads((FIXTURES / "tracinginsights" / "bahrain_2024_race_VER_lap10_tel_excerpt.json").read_text())


@pytest.fixture
def tmp_settings(tmp_path, monkeypatch):
    from apexlens.config import settings as settings_mod

    monkeypatch.setenv("APEXLENS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("APEXLENS_REPORTS_DIR", str(tmp_path / "reports"))
    monkeypatch.setenv("APEXLENS_F1DB_LOCAL_PATH", str(FIXTURES / "f1db_repo"))
    settings_mod.get_settings.cache_clear()
    yield settings_mod.get_settings()
    settings_mod.get_settings.cache_clear()
