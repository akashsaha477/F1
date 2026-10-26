"""FastAPI application. Run with ``uvicorn apexlens.api.main:app``."""

from __future__ import annotations

import logging
import time

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from apexlens import __version__
from apexlens.api.deps import paths
from apexlens.api.routes import catalog, drivers, models, predictions, sessions
from apexlens.config import get_settings
from apexlens.predictions.service import ScenarioError
from apexlens.services.data_service import NotFound

log = logging.getLogger("apexlens.api")


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def create_app() -> FastAPI:
    app = FastAPI(title="ApexLens API", version=__version__,
                  description="Explainable Formula 1 performance intelligence. Unofficial; not associated with "
                              "Formula 1, the FIA or any team.")
    app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_methods=["GET", "POST"],
                       allow_headers=["*"])
    app.add_middleware(GZipMiddleware, minimum_size=2048)

    @app.middleware("http")
    async def timing(request: Request, call_next):
        t0 = time.time()
        response = await call_next(request)
        log.info("%s %s %s %.0fms", request.method, request.url.path, response.status_code, (time.time() - t0) * 1000)
        return response

    @app.exception_handler(NotFound)
    async def not_found(_, exc: NotFound):
        return error(404, "not_found", str(exc))

    @app.exception_handler(ScenarioError)
    async def scenario_error(_, exc: ScenarioError):
        return error(422, "unsupported_scenario", str(exc))

    @app.exception_handler(RequestValidationError)
    async def validation(_, exc: RequestValidationError):
        msgs = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
        return error(422, "invalid_request", msgs)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return error(500, "internal_error", "Internal error. See server logs.")

    @app.get("/api/health", tags=["health"])
    def health():
        p = paths()
        return {"status": "ok", "version": __version__,
                "data": {"silver": (p.processed / "laps").exists(), "gold": (p.features / "lap_features").exists(),
                         "models": (p.models / "production.json").exists()}}

    for r in (catalog.router, sessions.router, drivers.router, predictions.router, models.router):
        app.include_router(r, prefix="/api")
    return app


app = create_app()
