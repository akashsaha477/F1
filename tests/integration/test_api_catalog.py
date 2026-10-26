import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(ingested):
    from apexlens.api import deps
    from apexlens.api.main import create_app

    deps.reset()
    yield TestClient(create_app())
    deps.reset()


def test_health(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["data"]["silver"] is True and body["data"]["models"] is False


def test_catalog(client):
    assert client.get("/api/seasons").json()[0]["season"] == 2024
    events = client.get("/api/events", params={"season": 2024}).json()
    assert events[0]["event_id"] == "2024-01" and events[0]["winner_id"] == "max-verstappen"
    sessions = client.get("/api/sessions", params={"event_id": "2024-01"}).json()
    assert {"FP1", "Q", "R"} <= {s["session_code"] for s in sessions}
    drivers = client.get("/api/drivers", params={"scope": "all"}).json()
    assert drivers["total"] >= 3 and "items" in drivers


def test_session_endpoints(client):
    laps = client.get("/api/sessions/2024-01-R/laps").json()
    assert len(laps["laps"]) == 24 and "is_clean" in laps["laps"][0]
    one = client.get("/api/sessions/2024-01-R/laps", params={"driver_id": "max-verstappen"}).json()
    assert {r["driver_id"] for r in one["laps"]} == {"max-verstappen"}
    assert len(client.get("/api/sessions/2024-01-R/weather").json()) == 20
    assert client.get("/api/sessions/2024-01-R/results").json()[0]["driver_id"] == "max-verstappen"
    tel = client.get("/api/sessions/2024-01-R/telemetry").json()
    assert tel["available_laps"] == [] and "note" in tel


def test_errors_are_structured(client):
    r = client.get("/api/sessions/2024-01-Q/laps")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = client.get("/api/sessions/not-a-session/laps")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"
    r = client.get("/api/drivers", params={"limit": 100000})
    assert r.status_code == 422
    r = client.post("/api/predict/lap-time", json={"driver_id": "max-verstappen", "circuit_id": "bahrain"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "unsupported_scenario"
    assert "Traceback" not in r.text and "/data/" not in r.text


def test_coverage_endpoint(client):
    assert client.get("/api/data-coverage").json()["summary"]["sessions_with_timing"] == 1
    src = client.get("/api/sources").json()
    assert "f1db" in src["catalog"]
