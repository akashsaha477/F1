from __future__ import annotations

from fastapi import APIRouter, Path

from apexlens.api.deps import paths
from apexlens.modeling.registry import list_models
from apexlens.predictions.service import evaluation_run
from apexlens.services.data_service import NotFound, clean_value
from apexlens.storage.io import read_json

router = APIRouter(tags=["models"])
VERSION = Path(..., pattern=r"^[a-z0-9_\-]+$", max_length=120)


@router.get("/models")
def models():
    prod = read_json(paths().models / "production.json", default={})
    return {"production": prod, "models": clean_value(list_models(paths().models))}


def _meta(version: str) -> dict:
    meta = read_json(paths().models / version / "metadata.json")
    if meta is None:
        raise NotFound(f"unknown model version {version}")
    return meta


@router.get("/models/{model_version}/metrics")
def model_metrics(model_version: str = VERSION):
    m = _meta(model_version)
    keep = ["model_version", "task", "model", "horizon", "target", "target_unit", "train_period", "calibration_events",
            "conformal", "test_metrics", "feature_set_version", "features", "dataset_version", "environment", "saved_at",
            "is_production", "evaluation_run"]
    return clean_value({k: m.get(k) for k in keep})


@router.get("/models/{model_version}/explanations")
def model_explanations(model_version: str = VERSION):
    _meta(model_version)
    e = read_json(paths().models / model_version / "global_explanations.json")
    if e is None:
        raise NotFound("global explanations are stored for production models only")
    return clean_value(e)


@router.get("/evaluation")
def evaluation():
    run = evaluation_run(paths())
    if run is None:
        raise NotFound("no evaluation run; run scripts/train_models.py")
    run = dict(run)
    run.pop("environment", None)
    for h in run.get("horizons", {}).values():
        h.get("global_explanations", {}).pop("ridge_coefficients", None)
    return clean_value(run)
