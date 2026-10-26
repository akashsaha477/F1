from __future__ import annotations

from fastapi import APIRouter, Query

from apexlens.api.deps import data_service
from apexlens.services.data_service import clean_value
from apexlens.services.methodology import METHODOLOGY

router = APIRouter(tags=["catalog"])


@router.get("/seasons")
def seasons():
    return data_service().seasons()


@router.get("/events")
def events(season: int | None = Query(None, ge=1950, le=2100)):
    return data_service().events_list(season)


@router.get("/circuits")
def circuits():
    return data_service().circuits()


@router.get("/drivers")
def drivers(season: int | None = Query(None, ge=1950, le=2100), constructor_id: str | None = Query(None, max_length=64),
            q: str | None = Query(None, max_length=64), scope: str = Query("lap", pattern="^(lap|all)$"),
            limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    return data_service().drivers(season, constructor_id, q, scope, limit, offset)


@router.get("/constructors")
def constructors(season: int | None = Query(None, ge=1950, le=2100)):
    return data_service().constructors(season)


@router.get("/sessions")
def sessions(event_id: str | None = Query(None, max_length=16), season: int | None = Query(None, ge=1950, le=2100)):
    return data_service().sessions_list(event_id, season)


@router.get("/data-coverage")
def data_coverage():
    return data_service().coverage()


@router.get("/sources")
def sources():
    return data_service().sources()


@router.get("/features")
def features():
    return data_service().features()


@router.get("/overview")
def overview():
    return data_service().overview()


@router.get("/methodology")
def methodology():
    return clean_value(METHODOLOGY)
