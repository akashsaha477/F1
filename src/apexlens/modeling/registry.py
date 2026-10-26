"""Versioned model artifacts: ``data/models/<version>/{model.joblib, metadata.json}``."""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from importlib import metadata as importlib_metadata
from pathlib import Path

import joblib

from apexlens.storage.io import read_json, write_json

PACKAGES = ["numpy", "pandas", "scikit-learn", "lightgbm", "shap", "statsmodels", "scipy", "pyarrow", "duckdb"]


def environment() -> dict:
    vers = {}
    for p in PACKAGES:
        try:
            vers[p] = importlib_metadata.version(p)
        except importlib_metadata.PackageNotFoundError:
            vers[p] = None
    return {"python": sys.version.split()[0], "platform": platform.platform(), "packages": vers}


def short_hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:10]


def make_version(task: str, model: str, config: dict) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d")
    return f"{task}-{model}-{stamp}-{short_hash(config)}"


def save_artifact(models_dir: Path, version: str, obj, metadata: dict) -> Path:
    d = Path(models_dir) / version
    d.mkdir(parents=True, exist_ok=True)
    joblib.dump(obj, d / "model.joblib")
    write_json(d / "metadata.json", {**metadata, "model_version": version,
                                     "saved_at": datetime.now(UTC).isoformat(timespec="seconds")})
    return d


def load_artifact(models_dir: Path, version: str):
    d = Path(models_dir) / version
    return joblib.load(d / "model.joblib"), read_json(d / "metadata.json")


def list_models(models_dir: Path) -> list[dict]:
    """All stored models. ``is_production`` follows the production pointer, not the flag saved at training
    time (older versions keep their original metadata after being superseded)."""
    prod = set(read_json(Path(models_dir) / "production.json", default={}).values())
    out = []
    for d in sorted(Path(models_dir).glob("*/metadata.json")):
        m = read_json(d)
        row = {k: m.get(k) for k in ("model_version", "task", "model", "horizon", "saved_at", "train_period", "target",
                                     "test_metrics")}
        row["is_production"] = m.get("model_version") in prod
        out.append(row)
    return out


def production_version(models_dir: Path, task: str) -> str | None:
    pointer = read_json(Path(models_dir) / "production.json", default={})
    return pointer.get(task)


def set_production(models_dir: Path, task: str, version: str) -> None:
    path = Path(models_dir) / "production.json"
    pointer = read_json(path, default={})
    pointer[task] = version
    write_json(path, pointer)
