"""Race strategy planner on the ingested dataset (skipped when absent)."""

import pytest
from fastapi.testclient import TestClient

from apexlens.storage.paths import DataPaths

pytestmark = pytest.mark.realdata


@pytest.fixture(scope="module")
def paths():
    p = DataPaths.default()
    if not (p.models / "production.json").exists() or not p.gold("tyre_stints").exists():
        pytest.skip("no trained models / gold tables in data/; run the pipeline first")
    return p


@pytest.fixture(scope="module")
def client(paths):
    from apexlens.api import deps
    from apexlens.api.main import create_app

    deps.reset()
    return TestClient(create_app())


def test_parameters_ignore_everything_after_the_race(paths):
    from apexlens.strategy.data import StrategyData
    from apexlens.strategy.params import estimate_params

    event = "2024-12"
    d = StrategyData(paths)
    ev = d.events.loc[event]
    args = (ev["circuit_id"], ev["date"], int(ev["season"]), int(ev["laps"]))
    before = estimate_params(d, *args, event_id=event).to_dict()
    # corrupt every table from the race onwards (the same weekend's sprint is legitimately allowed)
    st = d.stint_slopes
    future = (st["date"] >= ev["date"]) & ~((st["event_id"] == event) & (st["session_code"] == "S"))
    st.loc[future, "slope_pct"] *= 10
    st.loc[future, "level_at_age0"] += 5
    d.pit_stops.loc[d.pit_stops["date"] >= ev["date"], "loss_s"] += 40
    d.stints.loc[d.stints["date"] >= ev["date"], "n_laps"] = 1
    d.races.loc[d.races["date"] >= ev["date"], ["sc", "vsc", "red"]] = True
    d.races.loc[d.races["date"] >= ev["date"], "ref_s"] *= 2
    d.laps.loc[d.laps["date"] >= ev["date"], "lap_time_s"] *= 2
    after = estimate_params(d, *args, event_id=event).to_dict()
    assert after == before


def test_plan_for_a_past_race(client):
    r = client.post("/api/strategy/plan", json={"event_id": "2024-13", "driver_id": "lando-norris"})
    assert r.status_code == 200, r.text
    p = r.json()
    best = p["best"]
    assert best["delta_s"] == 0 and all(q["delta_s"] >= 0 for q in p["plans"])
    assert sum(best["stint_laps"]) == p["event"]["laps"] == len(p["trace"]["best"])
    assert len(set(best["sequence"])) >= 2
    for w in best["pit_windows"]:
        assert w["from_lap"] <= w["best_lap"] <= w["to_lap"]
    assert p["prediction"]["pace_model"].startswith("lap-pace model trained on")  # no in-season leakage
    assert any(f["driver_id"] == "lando-norris" for f in p["prediction"]["field"])
    assert p["actual"]["driver_strategy"]["stops"] >= 1 and p["actual"]["result"]["position"] is not None
    shares = [s["share"] for s in p["robustness"]["best_share"]]
    assert abs(sum(shares) - 1) < 1e-9


def test_plan_with_another_car_and_grid(client):
    base = client.post("/api/strategy/plan", json={"event_id": "2024-13", "driver_id": "logan-sargeant"}).json()
    swap = client.post("/api/strategy/plan", json={"event_id": "2024-13", "driver_id": "logan-sargeant",
                                                   "constructor_override": "mclaren", "grid_position": 1}).json()
    assert swap["driver"]["constructor_id"] == "mclaren" and swap["prediction"]["grid"] == 1
    assert swap["prediction"]["base_pct"] < base["prediction"]["base_pct"]
    assert swap["prediction"]["predicted_position"] < base["prediction"]["predicted_position"]


def test_upcoming_race_and_errors(client):
    weeks = client.get("/api/strategy/race-weeks").json()["race_weeks"]
    upcoming = [w for w in weeks if w["status"] == "upcoming"]
    if upcoming:  # the plan uses the line-up after the last ingested race
        r = client.post("/api/strategy/plan", json={"event_id": upcoming[0]["event_id"], "driver_id": "lando-norris"})
        assert r.status_code == 200, r.text
        assert r.json()["event"]["mode"] == "upcoming" and r.json()["warnings"]
    bad = client.post("/api/strategy/plan", json={"event_id": "2024-13", "driver_id": "nobody"})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "unsupported_scenario"
    assert client.post("/api/strategy/plan", json={"event_id": "1999-01", "driver_id": "x"}).status_code == 422
