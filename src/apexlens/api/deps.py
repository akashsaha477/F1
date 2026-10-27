"""Shared service singletons for the API."""

from __future__ import annotations

from functools import lru_cache

from apexlens.config import get_settings
from apexlens.predictions.service import PredictionService
from apexlens.services.data_service import DataService, ProfileService, TrackService, TyreService
from apexlens.storage.paths import DataPaths
from apexlens.strategy.service import StrategyService


@lru_cache
def paths() -> DataPaths:
    return DataPaths(get_settings().data_dir)


@lru_cache
def data_service() -> DataService:
    return DataService(paths())


@lru_cache
def profile_service() -> ProfileService:
    return ProfileService(paths())


@lru_cache
def track_service() -> TrackService:
    return TrackService(paths())


@lru_cache
def tyre_service() -> TyreService:
    return TyreService(paths())


@lru_cache
def prediction_service() -> PredictionService:
    return PredictionService(paths())


@lru_cache
def strategy_service() -> StrategyService:
    return StrategyService(paths())


def reset() -> None:
    for f in (paths, data_service, profile_service, track_service, tyre_service, prediction_service, strategy_service):
        f.cache_clear()
