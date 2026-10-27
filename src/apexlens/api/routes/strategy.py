from __future__ import annotations

from fastapi import APIRouter

from apexlens.api.deps import paths, strategy_service
from apexlens.schemas.api import StrategyRequest
from apexlens.services.data_service import NotFound, clean_value
from apexlens.storage.io import read_json

router = APIRouter(prefix="/strategy", tags=["strategy"])


@router.get("/race-weeks")
def race_weeks():
    return {"race_weeks": strategy_service().race_weeks()}


@router.post("/plan")
def plan(req: StrategyRequest):
    out = strategy_service().plan(
        req.event_id, req.driver_id, constructor_override=req.constructor_override, grid_position=req.grid_position,
        max_stops=req.max_stops, window_s=req.window_s,
        weather_overrides={"track_temp_c": req.track_temp_c, "air_temp_c": req.air_temp_c,
                           "humidity_pct": req.humidity_pct, "rain": req.rain})
    return clean_value(out)


@router.get("/backtest")
def backtest():
    b = read_json(paths().models / "evaluation_runs" / "strategy_backtest.json", default=None)
    if not b:
        raise NotFound("strategy backtest not run yet (python scripts/evaluate_models.py --only strategy)")
    return clean_value(b)
