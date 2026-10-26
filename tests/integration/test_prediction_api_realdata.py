"""Prediction endpoints against the locally ingested dataset and trained models (skipped when absent)."""

import pytest
from fastapi.testclient import TestClient

from apexlens.storage.paths import DataPaths

pytestmark = pytest.mark.realdata


@pytest.fixture(scope="module")
def client():
    if not (DataPaths.default().models / "production.json").exists():
        pytest.skip("no trained models in data/; run the pipeline first")
    from apexlens.api import deps
    from apexlens.api.main import create_app

    deps.reset()
    return TestClient(create_app())


def test_lap_prediction_payload(client):
    r = client.post("/api/predict/lap-time", json={"driver_id": "max-verstappen", "as_of_event_id": "2024-12",
                                                   "compound": "MEDIUM", "tyre_life_laps": 12, "race_progress": 0.5})
    assert r.status_code == 200
    p = r.json()
    pred = p["prediction"]
    assert pred["interval"]["lo_pct"] <= pred["value_pct"] <= pred["interval"]["hi_pct"]
    total = p["baseline"]["value_pct"] + sum(c["contribution_pct"] for c in p["contributions"])
    assert abs(total - pred["value_pct"]) < 1e-6
    assert p["model_version"] and p["evidence"]["driver_events"] > 0 and p["narrative"]
    assert p["evidence"]["cutoff"] == "2024-07-07"  # evidence strictly before the event date


def test_comparison_and_counterfactuals(client):
    body = {"driver_ids": ["lando-norris", "oscar-piastri"], "circuit_id": "silverstone", "compound": "HARD"}
    c = client.post("/api/predict/driver-comparison", json=body).json()
    d = c["difference"]
    assert abs(d["value_pct"] - (c["drivers"][0]["prediction_pct"] - c["drivers"][1]["prediction_pct"])) < 1e-9
    assert "same_car" in c["counterfactuals"]
    s = client.post("/api/scenarios", json={"driver_id": "charles-leclerc", "circuit_id": "monaco"}).json()
    assert s["changes"] and "not the causal effect" in s["note"]


def test_wet_scenario_warns_on_low_evidence(client):
    p = client.post("/api/predict/lap-time", json={"driver_id": "oliver-bearman", "circuit_id": "interlagos",
                                                    "compound": "WET", "rainfall": True}).json()
    assert any("wet" in w.lower() for w in p["warnings"])
