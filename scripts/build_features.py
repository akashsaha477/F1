"""Rebuild gold feature tables from the silver layer (no network access)."""

import logging
import warnings

from apexlens.features.lap_features import build_lap_features
from apexlens.ingestion.context import configure_logging
from apexlens.storage.paths import DataPaths

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=FutureWarning)
    configure_logging(logging.INFO)
    build_lap_features(DataPaths.default())
