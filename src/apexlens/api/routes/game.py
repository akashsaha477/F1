from __future__ import annotations

import secrets

from fastapi import APIRouter, Header, Path, Query

from apexlens.api.deps import game_service
from apexlens.config import get_settings
from apexlens.game.service import Forbidden
from apexlens.schemas.api import PredictionSubmission, SettleRequest
from apexlens.services.data_service import clean_value

router = APIRouter(prefix="/game", tags=["game"])


@router.get("/rules")
def rules():
    return game_service().rules()


@router.get("/events")
def events(season: int | None = Query(None, ge=1950, le=2100)):
    return {"events": clean_value(game_service().events(season))}


@router.get("/events/{event_id}")
def event(event_id: str = Path(max_length=16), player: str | None = Query(None, max_length=40)):
    return clean_value(game_service().event(event_id, player))


@router.post("/events/{event_id}/predictions")
def predict(req: PredictionSubmission, event_id: str = Path(max_length=16)):
    return clean_value(game_service().submit(event_id, req.player, req.picks))


@router.post("/events/{event_id}/settle")
def settle(req: SettleRequest, event_id: str = Path(max_length=16),
           x_admin_token: str | None = Header(None, max_length=200)):
    token = get_settings().game_admin_token
    if token and not (x_admin_token and secrets.compare_digest(x_admin_token, token)):
        raise Forbidden("Settling a race needs the admin token (X-Admin-Token header) on this server.")
    return clean_value(game_service().settle(event_id, fetch=req.fetch, laps=req.laps))


@router.get("/leaderboard")
def leaderboard(season: int | None = Query(None, ge=1950, le=2100)):
    return clean_value(game_service().leaderboard(season))
