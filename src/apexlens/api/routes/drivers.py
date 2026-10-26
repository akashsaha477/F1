from __future__ import annotations

from fastapi import APIRouter, Query

from apexlens.api.deps import data_service, profile_service

router = APIRouter(prefix="/drivers", tags=["drivers"])


@router.get("/compare")
def compare(ids: str = Query(..., pattern=r"^[a-z0-9\-]+,[a-z0-9\-]+$", max_length=130),
            season: int | None = Query(None, ge=1950, le=2100)):
    a, b = ids.split(",")
    return profile_service().compare(a, b, season)


@router.get("/{driver_id}/profile")
def profile(driver_id: str):
    return profile_service().driver_profile(driver_id)


@router.get("/{driver_id}/performance")
def performance(driver_id: str, season: int | None = Query(None, ge=1950, le=2100)):
    return data_service().driver_performance(driver_id, season)


effects_router = APIRouter(tags=["drivers"])


@effects_router.get("/driver-effects")
def driver_effects(season: int = Query(..., ge=1950, le=2100)):
    return profile_service().season_effects(season)


@effects_router.get("/driver-clusters")
def driver_clusters():
    return profile_service().clusters()


@effects_router.get("/conditions")
def conditions(dimension: str = Query(..., pattern="^[a-z_]+$", max_length=40)):
    return profile_service().conditions_by_dimension(dimension)
