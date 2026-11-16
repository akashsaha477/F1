"""Prediction game over HTTP against the fixture dataset: Bahrain 2024 is presented as an upcoming race, predicted,
locked and then scored against the real classified result in the ingested F1DB fixture."""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from apexlens.game.service import GameService
from apexlens.storage.paths import DataPaths
from apexlens.strategy.data import StrategyData

EVENT = "2024-01"
DEADLINE = "2024-03-02T15:00:00Z"


class FakeStrategy:
    """The real silver tables (events, sessions, results) with a stand-in for the model's finishing order."""

    def __init__(self, paths: DataPaths):
        self.data = StrategyData(paths)

    def race_weeks(self):
        e = self.data.events.loc[EVENT]
        return [{"event_id": EVENT, "season": 2024, "round": 1, "name": e["official_name"], "circuit_id": e["circuit_id"],
                 "date": str(e["date"].date()), "status": "upcoming", "race_start_utc": DEADLINE}]

    def finishing_order(self, event_id):
        res = self.data.results[self.data.results["event_id"] == event_id].sort_values("driver_id")
        field = [{"driver_id": r.driver_id, "name": r.driver_id.replace("-", " ").title(), "constructor_id": r.constructor_id,
                  "grid": i + 1, "base_pct": 0.0, "pace_rank": i + 1, "predicted_position": i + 1, "actual_position": None}
                 for i, r in enumerate(res.itertuples())]
        return {"event": {"event_id": event_id, "mode": "upcoming", "circuit_name": "Bahrain International Circuit", "laps": 57},
                "field": field, "pace_model": "test model", "grid_source": "test", "blend_weight": 0.5, "blend_weight_races": 1,
                "weather": {"track_temp_c": 30.0, "rain_risk": 0.0, "wet_race_likely": False}, "warnings": [],
                "data_as_of": "2023-11-26"}


@pytest.fixture
def client(ingested, monkeypatch):
    from apexlens.api import deps
    from apexlens.api.main import create_app
    from apexlens.api.routes import game as game_routes

    deps.reset()
    paths = deps.paths()
    strat = FakeStrategy(paths)
    clock = {"now": pd.Timestamp("2024-02-28T12:00:00Z")}
    svc = GameService(paths, strategy=lambda: strat, now=lambda: clock["now"], spawn=lambda fn: fn(),
                      ai_predictor=lambda ctx: {"status": "ok", "picks": [f["driver_id"] for f in ctx["field"]][:10],
                                                "rationale": "alphabetical", "model": "claude-test"})
    monkeypatch.setattr(game_routes, "game_service", lambda: svc)
    c = TestClient(create_app())
    c.clock = clock
    yield c
    deps.reset()


ANN = ["max-verstappen", "charles-leclerc", "sergio-perez", "carlos-sainz-jr", "george-russell", "lando-norris",
       "lewis-hamilton", "oscar-piastri", "fernando-alonso", "lance-stroll"]


def test_settle_needs_the_admin_token_when_one_is_configured(client):
    from apexlens.config import get_settings

    client.post(f"/api/game/events/{EVENT}/predictions", json={"player": "Ann", "picks": ANN})
    client.clock["now"] = pd.Timestamp("2024-03-02T15:00:00Z")
    get_settings().game_admin_token = "s3cret"
    assert client.get("/api/game/rules").json()["settle_protected"] is True
    r = client.post(f"/api/game/events/{EVENT}/settle", json={"fetch": False})
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    r = client.post(f"/api/game/events/{EVENT}/settle", json={"fetch": False}, headers={"X-Admin-Token": "wrong"})
    assert r.status_code == 403
    r = client.post(f"/api/game/events/{EVENT}/settle", json={"fetch": False}, headers={"X-Admin-Token": "s3cret"})
    assert r.status_code == 200 and r.json()["status"] == "settled"
    # predicting never needs the token (the race is closed here, which is a game error, not a permission one)
    assert client.post(f"/api/game/events/{EVENT}/predictions", json={"player": "Bob", "picks": ANN}).status_code == 422


def test_predict_lock_settle_and_leaderboard(client):
    rules = client.get("/api/game/rules").json()
    assert rules["max_points"] == 135 and rules["settle_protected"] is False
    ev = client.get("/api/game/events", params={"season": 2024}).json()["events"]
    assert ev[0]["event_id"] == EVENT and ev[0]["game_status"] == "open" and ev[0]["deadline_utc"] == DEADLINE

    v = client.get(f"/api/game/events/{EVENT}").json()
    assert v["status"] == "open" and not v["revealed"] and len(v["field"]) == 20
    assert v["entries"][0]["kind"] == "model" and "picks" not in v["entries"][0]

    r = client.post(f"/api/game/events/{EVENT}/predictions", json={"player": "Ann", "picks": ANN[:9]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    r = client.post(f"/api/game/events/{EVENT}/predictions", json={"player": "Ann", "picks": [*ANN[:9], "nobody"]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "game_error" and "nobody" in r.json()["error"]["message"]

    v = client.post(f"/api/game/events/{EVENT}/predictions", json={"player": "Ann", "picks": ANN}).json()
    by = {e["key"]: e for e in v["entries"]}
    assert v["revealed"] and v["you"] == "ann" and by["ann"]["picks"] == ANN
    assert by["apexlens"]["picks"][0] == "alexander-albon" and by["claude"]["status"] == "ok" and by["claude"]["picks"]
    assert client.get(f"/api/game/events/{EVENT}", params={"player": "ann"}).json()["revealed"]
    assert not client.get(f"/api/game/events/{EVENT}", params={"player": "bob"}).json()["revealed"]

    client.clock["now"] = pd.Timestamp("2024-03-02T15:00:00Z")
    r = client.post(f"/api/game/events/{EVENT}/predictions", json={"player": "Bob", "picks": ANN})
    assert r.status_code == 422 and "closed" in r.json()["error"]["message"]

    v = client.post(f"/api/game/events/{EVENT}/settle", json={"fetch": False}).json()
    assert v["status"] == "settled"
    assert [c["driver_id"] for c in v["result"]["classified"][:3]] == ["max-verstappen", "sergio-perez", "carlos-sainz-jr"]
    ann = next(e for e in v["entries"] if e["key"] == "ann")["score"]
    # actual: VER, PER, SAI, LEC, RUS … — P1 exact, P2 Leclerc two off, P3 Perez and P4 Sainz one off each, P5–P10 exact;
    # the podium set is wrong (Leclerc instead of Sainz), so no bonus
    assert ann["points"] == 10 + 3 + 6 + 6 + 6 * 10 == 85 and ann["exact"] == 7 and not ann["podium"] and ann["winner"]
    assert v["standings"][0]["name"] == "Ann"
    lb = client.get("/api/game/leaderboard", params={"season": 2024}).json()
    assert lb["rows"][0]["name"] == "Ann" and {r["kind"] for r in lb["rows"]} == {"player", "model", "ai"}
    assert lb["races"][0]["points"]["ann"] == ann["points"]
    assert client.get("/api/game/events/1999-01").status_code == 404
