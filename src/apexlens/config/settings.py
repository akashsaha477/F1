"""Environment-driven configuration.

All settings can be overridden with ``APEXLENS_*`` environment variables or a ``.env`` file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APEXLENS_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default=REPO_ROOT / "data")
    reports_dir: Path = Field(default=REPO_ROOT / "reports")
    default_seasons: str = "2022,2023,2024,2025"

    http_timeout_s: float = 30.0
    http_max_retries: int = 4
    http_backoff_base_s: float = 1.0
    http_max_concurrency: int = 4
    http_min_interval_s: float = 0.05
    user_agent: str = "ApexLens/0.1 (research; +https://github.com/akashsaha477/F1)"

    telemetry_laps_per_driver: int = 1

    f1db_local_path: Path | None = None
    f1db_raw_base: str = "https://raw.githubusercontent.com/f1db/f1db/main/src/data"
    tracinginsights_raw_base: str = "https://raw.githubusercontent.com/TracingInsights"
    tracinginsights_git_base: str = "https://github.com/TracingInsights"
    jolpica_base: str = "https://api.jolpi.ca/ergast/f1"
    openf1_base: str = "https://api.openf1.org/v1"

    api_cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @field_validator("f1db_local_path", mode="before")
    @classmethod
    def _empty_path_is_none(cls, v):
        if v in ("", None):
            return None
        return v

    @property
    def seasons(self) -> list[int]:
        return [int(s) for s in self.default_seasons.split(",") if s.strip()]

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
