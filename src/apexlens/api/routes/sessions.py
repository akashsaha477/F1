from __future__ import annotations

from fastapi import APIRouter, Path, Query

from apexlens.api.deps import data_service

router = APIRouter(prefix="/sessions", tags=["sessions"])
SID = Path(..., pattern=r"^\d{4}-\d{2}-(FP1|FP2|FP3|FP4|Q|SQ|S|R)$")


@router.get("/{session_id}/laps")
def laps(session_id: str = SID, driver_id: str | None = Query(None, max_length=64)):
    return data_service().session_laps(session_id, driver_id)


@router.get("/{session_id}/weather")
def weather(session_id: str = SID):
    return data_service().session_weather(session_id)


@router.get("/{session_id}/stints")
def stints(session_id: str = SID):
    return data_service().session_stints(session_id)


@router.get("/{session_id}/results")
def results(session_id: str = SID):
    return data_service().session_results(session_id)


@router.get("/{session_id}/race-control")
def race_control(session_id: str = SID):
    return data_service().session_race_control(session_id)


@router.get("/{session_id}/telemetry")
def telemetry(session_id: str = SID, driver_id: str | None = Query(None, max_length=64),
              lap: int | None = Query(None, ge=1, le=200), max_points: int = Query(2000, ge=100, le=10000)):
    return data_service().session_telemetry(session_id, driver_id, lap, max_points)
