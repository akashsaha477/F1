"""Fetch a race's results after the weekend: pull F1DB, re-ingest the season's results and the event's timing."""

from __future__ import annotations

import logging

from apexlens.ingestion.context import IngestionContext

log = logging.getLogger(__name__)


def refresh_event(event_id: str, laps: bool = True) -> dict:
    """Results come from F1DB (usually published within a day or two of the race); lap timing from the FastF1
    export is optional and only needed for the race week planner's "what happened" view. Lap-timing failures are
    logged, not raised: scoring needs the results only."""
    from apexlens.ingestion.f1db_ingest import ingest_f1db
    from apexlens.ingestion.laps_ingest import ingest_lap_timing

    ctx = IngestionContext.create()
    season = int(event_id.split("-")[0])
    pulled = ctx.f1db.refresh()
    res = ingest_f1db(ctx, [season])
    lap_sessions = None
    if laps:
        try:
            lap_sessions = len(ingest_lap_timing(ctx, season, events=[event_id], refresh_index=True))
        except Exception as exc:  # noqa: BLE001
            log.warning("lap timing for %s not refreshed: %s", event_id, exc)
    return {"event_id": event_id, "f1db_commit": res["commit"], "f1db_updated": pulled, "lap_sessions": lap_sessions}
