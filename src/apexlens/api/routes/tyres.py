from __future__ import annotations

from fastapi import APIRouter, Query

from apexlens.api.deps import tyre_service

router = APIRouter(prefix="/tyres", tags=["tyres"])


@router.get("/degradation")
def degradation(season: int | None = Query(None, ge=2018, le=2100), circuit_id: str | None = Query(None, max_length=64),
                compound: str | None = Query(None, pattern="^(SOFT|MEDIUM|HARD)$"), driver_id: str | None = Query(None, max_length=64)):
    return tyre_service().degradation(season, circuit_id, compound, driver_id)
