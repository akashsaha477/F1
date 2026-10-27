"""Race strategy planner (Model G): optimiser, calibration, finishing order, weather and the forecast adapter."""

import itertools

import httpx
import numpy as np
import pandas as pd
import pytest

from apexlens.data_sources.http import HttpClient
from apexlens.data_sources.openmeteo import OpenMeteoSource
from apexlens.strategy import calibration as CAL
from apexlens.strategy import race as RACE
from apexlens.strategy.optimizer import lap_trace, optimise, optimise_sequence, sequences, stint_cost_s
from apexlens.strategy.params import StrategyParams
from apexlens.strategy.weather import scenario


def params(**kw) -> StrategyParams:
    base = dict(circuit_id="test", season=2024, cutoff="2024-01-01", laps=40, ref_lap_s=90.0, ref_source="test",
                slope_pct={"SOFT": 0.15, "MEDIUM": 0.08, "HARD": 0.05}, offset_pct={"SOFT": -0.3, "MEDIUM": 0.0, "HARD": 0.2},
                pit_loss_s=22.0, max_stint={"SOFT": 18, "MEDIUM": 28, "HARD": 35}, min_stint=5, start_age=0.0,
                fuel_pct_per_lap=-0.06, lap1_delta_pct=6.0, start_share={"SOFT": 0.2, "MEDIUM": 0.7, "HARD": 0.1},
                sc_prob=0.5, vsc_prob=0.4, red_prob=0.1)
    base.update(kw)
    return StrategyParams(**base)


def brute_force(p: StrategyParams, seq) -> float:
    costs = [stint_cost_s(p, c, i == 0) for i, c in enumerate(seq)]
    n, best = p.laps, np.inf
    for cut in itertools.combinations(range(1, n), len(seq) - 1):
        bounds = (0, *cut, n)
        best = min(best, sum(costs[i][bounds[i + 1] - bounds[i]] for i in range(len(seq))))
    return best + (len(seq) - 1) * p.pit_loss_s


@pytest.mark.parametrize("seq", [("MEDIUM", "HARD"), ("SOFT", "MEDIUM", "HARD"), ("SOFT", "SOFT", "HARD", "MEDIUM")])
def test_dynamic_programme_matches_brute_force(seq):
    p = params()
    r = optimise_sequence(p, seq, window_s=2.0)
    assert r["strategy_cost_s"] == pytest.approx(brute_force(p, seq), abs=1e-9)
    assert sum(r["stint_laps"]) == p.laps
    assert all(p.min_stint <= L <= p.max_stint[c] for c, L in zip(seq, r["stint_laps"], strict=True))
    for w in r["pit_windows"]:
        assert w["from_lap"] <= w["best_lap"] <= w["to_lap"]


def test_dry_rule_and_minimum_stops():
    assert all(len(set(s)) >= 2 for s in sequences(3))
    plans = optimise(params(min_stops=2))
    assert plans and all(r["stops"] >= 2 for r in plans)


def test_high_degradation_needs_more_stops():
    low = optimise(params(slope_pct={"SOFT": 0.05, "MEDIUM": 0.03, "HARD": 0.02}))[0]
    high = optimise(params(slope_pct={"SOFT": 0.6, "MEDIUM": 0.45, "HARD": 0.35},
                           max_stint={"SOFT": 40, "MEDIUM": 40, "HARD": 40}))[0]
    assert low["stops"] == 1 and high["stops"] >= 2


def test_order_tie_break_uses_start_share():
    plans = optimise(params())
    best = plans[0]
    assert best["equivalent_orders"], "orderings of the same tyres cost the same in this model"
    others = {o.split(" ")[0].split("-")[0] for o in best["equivalent_orders"]}
    first = {"S": "SOFT", "M": "MEDIUM", "H": "HARD"}
    share = params().start_share
    assert all(share[best["sequence"][0]] >= share[first[o]] for o in others)
    assert len({(r["stops"], tuple(sorted(r["sequence"]))) for r in plans}) == len(plans)


def test_lap_trace_adds_pit_loss_and_lap_one():
    p = params()
    best = optimise(p)[0]
    tr = pd.DataFrame(lap_trace(p, best["sequence"], best["stint_laps"], base_pct=0.0))
    assert len(tr) == p.laps
    assert (tr["pit"] == "in").sum() == best["stops"] == (tr["pit"] == "out").sum()
    assert tr.loc[0, "lap_time_s"] > tr.loc[1, "lap_time_s"] + 3  # standing start
    in_lap = tr[tr["pit"] == "in"].iloc[0]
    neighbour = tr.loc[in_lap.name - 1]
    assert in_lap["lap_time_s"] - neighbour["lap_time_s"] == pytest.approx(p.pit_loss_s / 2, abs=1.0)


def test_calibration_recovers_revealed_preference():
    # three races where the physical optimum is a 2-stop SOFT plan but teams ran 1 stop on MEDIUM/HARD
    cands, targets = [], []
    for i in range(3):
        e = f"e{i}"
        cands.append(pd.DataFrame([{"event_id": e, "stops": 2, "n_soft": 2, "key": "2|HARD+SOFT", "cost_s": 40.0},
                                   {"event_id": e, "stops": 1, "n_soft": 0, "key": "1|HARD+MEDIUM", "cost_s": 48.0}]))
        targets.append({"event_id": e, "actual_stops": 1, "actual_key": "1|HARD+MEDIUM"})
    cal = CAL.fit(pd.concat(cands), pd.DataFrame(targets))
    assert cal["agreement"] == 1.0 and cal["stop_s"] + 2 * cal["soft_stint_s"] > 8.0
    plans = [{"stops": 2, "sequence": ["SOFT", "SOFT", "HARD"], "strategy_cost_s": 40.0},
             {"stops": 1, "sequence": ["MEDIUM", "HARD"], "strategy_cost_s": 48.0}]
    ranked = CAL.apply(plans, cal)
    assert ranked[0]["stops"] == 1 and ranked[0]["delta_s"] == 0.0 and ranked[0]["strategy_cost_s"] == 48.0


def test_finishing_order_blend():
    field = pd.DataFrame({"driver_id": list("abcd"), "grid": [1, 2, 3, 4], "base_pct": [0.3, 0.1, -0.2, 0.0]})
    assert list(RACE.predict_order(field, 1.0)["driver_id"]) == list("abcd")
    assert list(RACE.predict_order(field, 0.0)["driver_id"]) == list("cdba")
    # races where the finishing order equals the grid while pace says otherwise: the fitted weight must
    # reproduce the grid order
    six = pd.DataFrame({"driver_id": list("abcdef"), "grid": [1, 2, 3, 4, 5, 6], "base_pct": [0.4, 0.3, 0.2, 0.1, 0.0, -0.1],
                        "position": [1, 2, 3, 4, 5, 6]})
    rows = pd.concat([six.assign(event_id=f"r{i}") for i in range(3)])
    w, n = RACE.fit_weight(rows)
    assert n == 3 and w > 0.5
    assert list(RACE.predict_order(six, w)["driver_id"]) == list("abcdef")


def test_order_metrics_on_finishers_only():
    pred = pd.Series({"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6})
    actual = pd.Series({"a": 1, "b": 2, "c": np.nan, "d": 3, "e": 4, "f": 5})
    m = RACE.order_metrics(pred, actual)
    assert m["spearman"] == pytest.approx(1.0) and m["winner_correct"] and m["n_finishers"] == 5


def test_weather_scenario_precedence():
    weekend = [{"session_code": "FP1", "air_temp_c": 20.0, "track_temp_c": 30.0, "humidity_pct": 50.0, "rain_share": 0.0},
               {"session_code": "Q", "air_temp_c": 22.0, "track_temp_c": 34.0, "humidity_pct": 40.0, "rain_share": 0.0}]
    clim = {"air_temp_c": 25.0, "track_temp_c": 40.0, "humidity_pct": 45.0, "rain_race_share": 0.2, "track_minus_air_c": 15.0}
    s = scenario(weekend, clim, None, {})
    assert s["values"]["track_temp_c"] == 32.0 and s["source"]["track_temp_c"].startswith("mean of this weekend")
    s = scenario(weekend, clim, {"air_temp_c": 18.0, "humidity_pct": 70.0, "rain_probability_pct": 80.0}, {})
    assert s["values"]["air_temp_c"] == 18.0 and s["values"]["track_temp_c"] == 33.0 and s["values"]["wet_race_likely"]
    s = scenario(weekend, clim, None, {"track_temp_c": 50.0, "rain": False})
    assert s["values"]["track_temp_c"] == 50.0 and s["values"]["rain_risk"] == 0.0
    s = scenario([], clim, None, {})
    assert s["values"]["track_temp_c"] == 40.0 and s["values"]["rain_risk"] == 0.2


def test_open_meteo_forecast_parsing(tmp_path):
    start = (pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=3)).floor("h")
    hours = pd.date_range(start - pd.Timedelta(hours=2), periods=6, freq="h")
    body = {"hourly": {"time": [h.strftime("%Y-%m-%dT%H:%M") for h in hours], "temperature_2m": [20, 21, 22, 24, 23, 22],
                       "relative_humidity_2m": [60] * 6, "precipitation_probability": [5, 10, 30, 70, 40, 10],
                       "precipitation": [0, 0, 0.2, 1.0, 0.1, 0]}}
    seen = []

    def handler(request):
        seen.append(dict(request.url.params))
        return httpx.Response(200, json=body)

    http = HttpClient(cache_dir=tmp_path, transport=httpx.MockTransport(handler), sleep=lambda s: None)
    src = OpenMeteoSource(http, "https://api.example/v1/forecast")
    f = src.race_forecast(19.4, -99.09, start)
    assert f["air_temp_c"] == pytest.approx((22 + 24 + 23) / 3) and f["rain_probability_pct"] == 70
    assert seen[0]["latitude"] == "19.4" and "precipitation_probability" in seen[0]["hourly"]
    assert "error" in src.race_forecast(19.4, -99.09, start + pd.Timedelta(days=40))
    assert len(seen) == 1  # out-of-horizon requests are not sent
