"""Rebuild gold feature tables from the silver layer (no network access)."""

import logging
import warnings

from apexlens.driver_profiles.fingerprint import build_profiles
from apexlens.features.corner_metrics import build_corner_tables
from apexlens.features.lap_features import build_lap_features
from apexlens.ingestion.context import configure_logging
from apexlens.storage.paths import DataPaths

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=FutureWarning)
    configure_logging(logging.INFO)
    paths = DataPaths.default()
    build_corner_tables(paths)  # circuit profiles feed the lap features and driver profiles
    build_lap_features(paths)
    build_profiles(paths)
