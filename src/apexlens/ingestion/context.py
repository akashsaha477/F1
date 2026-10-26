"""Shared runtime objects for ingestion jobs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import cached_property

from apexlens.config import Settings, get_settings
from apexlens.data_sources.f1db import F1DBSource
from apexlens.data_sources.http import HttpClient, RateLimiter
from apexlens.data_sources.registry import ProvenanceRegistry
from apexlens.data_sources.tracinginsights import TracingInsightsSource
from apexlens.storage.paths import DataPaths


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)


@dataclass
class IngestionContext:
    settings: Settings
    paths: DataPaths

    @classmethod
    def create(cls, settings: Settings | None = None) -> IngestionContext:
        settings = settings or get_settings()
        return cls(settings=settings, paths=DataPaths(settings.data_dir).ensure())

    @cached_property
    def http(self) -> HttpClient:
        s = self.settings
        return HttpClient(
            cache_dir=self.paths.cache,
            timeout_s=s.http_timeout_s,
            max_retries=s.http_max_retries,
            backoff_base_s=s.http_backoff_base_s,
            rate_limiter=RateLimiter(min_interval_s=s.http_min_interval_s),
            user_agent=s.user_agent,
        )

    @cached_property
    def registry(self) -> ProvenanceRegistry:
        return ProvenanceRegistry(self.paths.manifests)

    @cached_property
    def f1db(self) -> F1DBSource:
        return F1DBSource(local_path=self.settings.f1db_local_path, cache_dir=self.paths.cache)

    @cached_property
    def tracinginsights(self) -> TracingInsightsSource:
        s = self.settings
        return TracingInsightsSource(self.http, s.tracinginsights_raw_base, s.tracinginsights_git_base, self.paths.cache)
