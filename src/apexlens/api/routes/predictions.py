from __future__ import annotations

from fastapi import APIRouter, HTTPException

from apexlens.api.deps import prediction_service, tyre_service
from apexlens.schemas.api import ComparisonRequest, DegradationRequest, ExplainRequest, LapTimeRequest

router = APIRouter(tags=["predictions"])


@router.post("/predict/lap-time")
def predict_lap_time(req: LapTimeRequest):
    return prediction_service().predict_lap(req)


@router.post("/predict/driver-comparison")
def predict_comparison(req: ComparisonRequest):
    return prediction_service().compare(req)


@router.post("/explain")
def explain(req: ExplainRequest):
    if req.task == "lap_time" and req.lap:
        return prediction_service().predict_lap(req.lap)
    if req.task == "driver_comparison" and req.comparison:
        return prediction_service().compare(req.comparison)
    raise HTTPException(status_code=422, detail="provide `lap` for task lap_time or `comparison` for driver_comparison")


@router.post("/scenarios")
def scenarios(req: LapTimeRequest):
    return prediction_service().counterfactuals(req)


@router.post("/predict/tyre-degradation")
def predict_tyre_degradation(req: DegradationRequest):
    return tyre_service().curve(req.compound, req.circuit_id, req.driver_id, req.max_tyre_age)
