from __future__ import annotations

from fastapi import APIRouter, Query

from apexlens.api.deps import data_service

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("/{driver_id}/performance")
def performance(driver_id: str, season: int | None = Query(None, ge=1950, le=2100)):
    return data_service().driver_performance(driver_id, season)
