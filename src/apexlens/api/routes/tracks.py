from __future__ import annotations

from fastapi import APIRouter, Path, Query

from apexlens.api.deps import track_service

router = APIRouter(tags=["tracks"])
CIRCUIT = Path(..., pattern=r"^[a-z0-9\-]+$", max_length=64)
SID = Query(None, pattern=r"^\d{4}-\d{2}-(Q|SQ)$")


@router.get("/circuits/{circuit_id}/layout")
def layout(circuit_id: str = CIRCUIT, session_id: str | None = SID):
    return track_service().layout(circuit_id, session_id)


@router.get("/circuits/{circuit_id}/corners")
def corners(circuit_id: str = CIRCUIT, session_id: str | None = SID):
    lay = track_service().layout(circuit_id, session_id)
    return {k: lay[k] for k in ("circuit_id", "session_id", "corners", "inferred_segments", "marker_validation",
                                "category_rules", "notes", "available_sessions")}


@router.get("/circuits/{circuit_id}/performance")
def performance(circuit_id: str = CIRCUIT, session_id: str | None = SID,
                corner_id: str | None = Query(None, max_length=32)):
    return track_service().performance(circuit_id, session_id, corner_id)


@router.get("/drivers/{driver_id}/corner-profile")
def driver_corner_profile(driver_id: str):
    return track_service().driver_corner_profile(driver_id)


@router.get("/corner-analysis")
def corner_analysis():
    return track_service().summary()
