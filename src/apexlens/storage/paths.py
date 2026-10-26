"""Filesystem layout of the bronze / silver / gold layers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from apexlens.config import get_settings


@dataclass(frozen=True)
class DataPaths:
    root: Path

    @classmethod
    def default(cls) -> DataPaths:
        return cls(Path(get_settings().data_dir))

    @property
    def cache(self) -> Path:
        return self.root / "cache"

    @property
    def raw(self) -> Path:
        """Bronze: payloads as downloaded. Never modified by later stages."""
        return self.root / "raw"

    @property
    def processed(self) -> Path:
        """Silver: normalised tables."""
        return self.root / "processed"

    @property
    def features(self) -> Path:
        """Gold: model-ready tables."""
        return self.root / "features"

    @property
    def manifests(self) -> Path:
        return self.root / "manifests"

    @property
    def models(self) -> Path:
        return self.root / "models"

    def silver(self, table: str) -> Path:
        return self.processed / table

    def gold(self, table: str) -> Path:
        return self.features / table

    def ensure(self) -> DataPaths:
        for p in (self.cache, self.raw, self.processed, self.features, self.manifests, self.models):
            p.mkdir(parents=True, exist_ok=True)
        return self
