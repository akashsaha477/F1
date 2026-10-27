"""Race-week planner: weather, best tyre strategy and pit windows, expected lap times, predicted finishing
order, and — for past races — what actually happened.
"""

from __future__ import annotations

import logging
from functools import cached_property, lru_cache

import numpy as np
import pandas as pd

from apexlens.config.settings import get_settings
from apexlens.data_sources.http import HttpClient
from apexlens.data_sources.openmeteo import OpenMeteoSource
from apexlens.predictions.service import PredictionService, ScenarioError
from apexlens.storage.io import read_json, read_table
from apexlens.storage.paths import DataPaths
from apexlens.strategy import actual as ACT
from apexlens.strategy import calibration as CAL
from apexlens.strategy import race as RACE
from apexlens.strategy import weather as WX
from apexlens.strategy.data import StrategyData
from apexlens.strategy.optimizer import lap_trace, optimise, robustness
from apexlens.strategy.pace import base_paces, season_model
from apexlens.strategy.params import estimate_params

log = logging.getLogger(__name__)
N_BOOT = 25
SHOWN_PLANS = 8

LIMITATIONS = [
    "Dry-race strategies only: if it rains, intermediate/wet tyre strategies are not optimised.",
    "Safety cars and VSCs are not simulated; their historical frequency here is shown because they often make "
    "an earlier or later stop the better call during the race.",
    "Every car is assumed to have new tyres for each stint after the start; real tyre allocations differ.",
    "Track temperature is shown but does not change tyre wear: temperature adjustments made held-out "
    "predictions worse in testing.",
    "Strategy costs are associations learned from past races, not a physical tyre model.",
]


class StrategyService:
    def __init__(self, paths: DataPaths):
        self.paths = paths
        self.data = StrategyData(paths)
        self.pred = PredictionService(paths)
        self._plans: dict = {}
        self._cache: dict = {}

    # -- catalogue ---------------------------------------------------------------------------
    @cached_property
    def last_data_date(self) -> pd.Timestamp:
        return self.data.races["date"].max()

    def race_weeks(self) -> list[dict]:
        ev = self.data.events
        first = int(self.data.races["season"].min())
        with_data = set(self.data.races["event_id"])
        today = pd.Timestamp.now().normalize()
        rows = []
        for e in ev[ev["season"] >= first].sort_values("date").itertuples():
            status = "past" if e.event_id in with_data else ("upcoming" if e.date >= today else "no_timing_data")
            rows.append({"event_id": e.event_id, "season": int(e.season), "round": int(e.round), "name": e.official_name,
                         "circuit_id": e.circuit_id, "date": str(e.date.date()), "status": status})
        return rows

    # -- pieces --------------------------------------------------------------------------------
    @cached_property
    def calibration_data(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        c = read_table(self.paths.models / "strategy" / "calibration_candidates")
        t = read_table(self.paths.models / "strategy" / "calibration_targets")
        if len(t):
            t["date"] = pd.to_datetime(t["date"])
        return c, t

    def calibration(self, before: pd.Timestamp) -> dict | None:
        key = ("cal", before)
        if key not in self._cache:
            self._cache[key] = self._calibration(before)
        return self._cache[key]

    def _calibration(self, before: pd.Timestamp) -> dict | None:
        c, t = self.calibration_data
        if t.empty:
            return None
        t = t[t["date"] < before]
        if t.empty:
            return None
        return CAL.fit(c[c["event_id"].isin(t["event_id"])], t[["event_id", "actual_stops", "actual_key"]])

    @cached_property
    def backtest_field(self) -> pd.DataFrame:
        f = read_table(self.paths.models / "strategy" / "backtest_field")
        if len(f):
            f["date"] = pd.to_datetime(f["date"])
        return f

    def blend_weight(self, before: pd.Timestamp) -> tuple[float, int]:
        key = ("w", before)
        if key not in self._cache:
            f = self.backtest_field
            self._cache[key] = RACE.fit_weight(f[f["date"] < before]) if len(f) else (RACE.DEFAULT_W, 0)
        return self._cache[key]

    def _forecast(self, event: pd.Series) -> dict | None:
        s = get_settings()
        if not s.weather_forecast_enabled or event["circuit_id"] not in self.data.circuits.index:
            return None
        start = self.data.sessions[(self.data.sessions["event_id"] == event["event_id"])
                                   & (self.data.sessions["session_code"] == "R")]["start"]
        if start.empty or pd.isna(start.iloc[0]):
            return None
        c = self.data.circuits.loc[event["circuit_id"]]
        http = HttpClient(cache_dir=self.paths.cache, timeout_s=10, max_retries=1)
        try:
            return OpenMeteoSource(http, s.weather_forecast_base).race_forecast(float(c["latitude"]), float(c["longitude"]),
                                                                                start.iloc[0])
        except Exception as exc:  # noqa: BLE001 - a forecast must never break planning
            return {"error": f"forecast unavailable: {exc}"}
        finally:
            http.close()

    def strategy_for(self, event_id: str, max_stops: int, window_s: float) -> dict:
        key = (event_id, max_stops, window_s)
        if key not in self._plans:
            ev = self.event(event_id)
            season, laps = int(ev["season"]), int(ev["laps"])
            p = estimate_params(self.data, ev["circuit_id"], ev["date"], season, laps, event_id=event_id)
            cal = self.calibration(ev["date"])
            plans = CAL.apply(optimise(p, max_stops=max_stops, window_s=window_s), cal)
            rng = np.random.default_rng(7)
            draws = [estimate_params(self.data, ev["circuit_id"], ev["date"], season, laps, event_id=event_id, rng=rng)
                     for _ in range(N_BOOT)]
            rob = robustness_calibrated(draws, cal, max_stops)
            self._plans[key] = {"params": p, "plans": plans, "calibration": cal, "robustness": rob}
        return self._plans[key]

    def event(self, event_id: str) -> pd.Series:
        if event_id not in self.data.events.index:
            raise ScenarioError(f"unknown event {event_id}")
        return self.data.events.loc[event_id]

    # -- main entry ----------------------------------------------------------------------------
    def plan(self, event_id: str, driver_id: str, constructor_override: str | None = None, grid_position: int | None = None,
             max_stops: int = 3, window_s: float = 2.0, weather_overrides: dict | None = None) -> dict:
        ev = self.event(event_id)
        has_data = event_id in set(self.data.races["event_id"])
        season = int(ev["season"])
        mode = "past" if has_data else "upcoming"
        warnings: list[str] = []

        weekend = WX.weekend_sessions(self.data, event_id)
        clim = WX.climatology(self.data, ev["circuit_id"], ev["date"])
        forecast = None if has_data else self._forecast(ev)
        if forecast and "error" in forecast:
            warnings.append(f"Weather forecast: {forecast['error']}; using the circuit's history.")
        scen = WX.scenario(weekend, clim, forecast if forecast and "error" not in forecast else None,
                           weather_overrides or {})
        if scen["values"].get("wet_race_likely"):
            warnings.append("Rain is likely: the plan below is for a dry race; wet-tyre strategies are not optimised.")

        strat = self.strategy_for(event_id, max_stops, window_s)
        p = strat["params"]

        model, model_note = season_model(self.paths, season, production=not has_data)
        if not has_data:
            last = int(self.data.races["season"].max())
            warnings.append(f"Upcoming race: drivers, cars and form are those after the last ingested race "
                            f"({self.last_data_date.date()}, {last} season).")
            if season > last:
                warnings.append(f"The models were trained on {int(self.data.races['season'].min())}–{last} cars; "
                                f"{season} cars may behave differently.")
        overrides = {driver_id: constructor_override} if constructor_override else None
        field = base_paces(self.pred, model, event_id=event_id if has_data else None,
                           circuit_id=None if has_data else ev["circuit_id"], weather=scen["values"], overrides=overrides)
        if driver_id not in set(field["driver_id"]):
            raise ScenarioError(f"{driver_id} has no pace estimate for {event_id} (did not take part, or no earlier races)")

        res = ACT.classified(self.data, event_id) if has_data else pd.DataFrame(columns=["driver_id", "grid_position", "position"])
        field = field.merge(res[["driver_id", "grid_position", "position"]], on="driver_id", how="left").rename(
            columns={"grid_position": "grid"})
        grid_source = "actual starting grid" if has_data and field["grid"].notna().any() else \
            "predicted from qualifying form (driver's recent average gap to pole)"
        if not (has_data and field["grid"].notna().any()):
            q = field["drv_quali_form"].astype(float)
            field["grid"] = q.fillna(q.max() + 1 if q.notna().any() else 0).rank(method="first")
        if grid_position is not None:
            others = field["driver_id"] != driver_id
            g = field.loc[others, "grid"].rank(method="first")
            field.loc[others, "grid"] = np.where(g >= grid_position, g + 1, g)
            field.loc[~others, "grid"] = grid_position
            grid_source = "your input for this driver; others shifted"
        w, n_w = self.blend_weight(ev["date"])
        order = RACE.predict_order(field, w)
        me = order[order["driver_id"] == driver_id].iloc[0]
        base = float(me["base_pct"])

        plans = strat["plans"]
        best = plans[0]
        trace = lap_trace(p, best["sequence"], best["stint_laps"], base)
        alt = next((q for q in plans[1:] if q["stops"] != best["stops"]), plans[1] if len(plans) > 1 else None)
        out = {
            "event": {"event_id": event_id, "name": ev["official_name"], "circuit_id": ev["circuit_id"],
                      "circuit_name": self._circuit_name(ev["circuit_id"]), "date": str(ev["date"].date()), "season": season,
                      "laps": int(ev["laps"]), "mode": mode},
            "driver": {"driver_id": driver_id, "name": self.pred.driver_name(driver_id), "constructor_id": me["constructor_id"],
                       "car_override": constructor_override},
            "weather": {"weekend_sessions": weekend, "circuit_history": clim, "forecast": forecast,
                        "race_actual": WX.race_weather(self.data, event_id) if has_data else None, "assumed": scen},
            "parameters": _param_view(p),
            "calibration": strat["calibration"],
            "plans": [_plan_view(q) for q in plans[:SHOWN_PLANS]],
            "best": _plan_view(best),
            "robustness": strat["robustness"],
            "trace": {"best": trace, "alternative": lap_trace(p, alt["sequence"], alt["stint_laps"], base) if alt else None,
                      "alternative_label": alt["label"] if alt else None},
            "expected_race_time_s": float(sum(r["lap_time_s"] for r in trace)),
            "prediction": {
                "pace_model": model_note, "base_pct": base, "grid": int(me["grid_used"]), "grid_source": grid_source,
                "predicted_position": int(me["predicted_position"]), "blend_weight": w, "blend_weight_races": n_w,
                "field": [{"driver_id": r.driver_id, "name": self.pred.driver_name(r.driver_id), "constructor_id": r.constructor_id,
                           "grid": int(r.grid_used), "base_pct": float(r.base_pct), "pace_rank": int(r.pace_rank),
                           "predicted_position": int(r.predicted_position),
                           "actual_position": int(r.position) if pd.notna(r.position) else None}
                          for r in order.itertuples()],
            },
            "warnings": warnings + ([f"Rule: {n}" for n in p.rule_notes]),
            "limitations": LIMITATIONS,
        }
        if has_data:
            out["actual"] = self._actual(event_id, driver_id, p, base, best)
        out["backtest"] = backtest_headline(self.paths)
        return out

    def _circuit_name(self, circuit_id: str) -> str:
        c = self.data.circuits
        return str(c.loc[circuit_id, "name"]) if circuit_id in c.index else circuit_id

    def _actual(self, event_id: str, driver_id: str, p, base: float, best: dict) -> dict:
        mine = ACT.driver_strategy(self.data, event_id, driver_id)
        summ = ACT.race_summary(self.data, event_id) or {}
        replay = lap_trace(p, mine["sequence"], mine["stint_laps"], base) if mine and mine["dry_only"] else None
        win = summ.get("winner")
        comparison = {}
        if mine:
            comparison = {
                "same_stop_count": mine["stops"] == best["stops"],
                "same_compounds": set(mine["sequence"]) == set(best["sequence"]),
                "first_stop_in_window": bool(mine["pit_laps"] and best["pit_windows"]
                                             and best["pit_windows"][0]["from_lap"] <= mine["pit_laps"][0]
                                             <= best["pit_windows"][0]["to_lap"]),
                "first_stop_difference_laps": (mine["pit_laps"][0] - best["pit_laps"][0]) if mine["pit_laps"] else None,
            }
        if win:
            comparison["winner_same_stop_count"] = win["stops"] == best["stops"]
            comparison["winner_same_compounds"] = set(win["sequence"]) == set(best["sequence"])
        if summ.get("top_modal_plan"):
            comparison["matches_most_common_top10_plan"] = CAL.plan_key(best["stops"], best["sequence"]) == summ["top_modal_plan"]
        return {"driver_strategy": mine, "result": ACT.driver_result(self.data, event_id, driver_id), "race": summ,
                "laps": ACT.driver_laps(self.data, event_id, driver_id), "replay_trace": replay, "comparison": comparison}


def robustness_calibrated(draws, cal: dict | None, max_stops: int) -> dict:
    winners, first = [], []
    for q in draws:
        plans = CAL.apply(optimise(q, max_stops=max_stops), cal)
        if plans:
            winners.append(plans[0]["label"])
            first.append(plans[0]["pit_laps"][0])
    if not winners:
        return robustness(draws, max_stops)
    labels, counts = np.unique(winners, return_counts=True)
    order = np.argsort(-counts)
    return {"n": len(winners), "method": "parameters re-estimated on race-level bootstrap resamples",
            "best_share": [{"label": str(labels[i]), "share": float(counts[i] / len(winners))} for i in order],
            "first_stop_lap": {"p10": float(np.quantile(first, 0.1)), "median": float(np.median(first)),
                               "p90": float(np.quantile(first, 0.9))}}


def _plan_view(q: dict) -> dict:
    keys = ("label", "sequence", "stops", "stint_laps", "pit_laps", "pit_windows", "delta_s", "strategy_cost_s",
            "calibration_cost_s", "equivalent_orders")
    return {k: q.get(k) for k in keys}


def _param_view(p) -> dict:
    d = p.to_dict()
    s_per_pct = p.ref_lap_s / 100
    d["slope_s_per_lap"] = {c: v * s_per_pct for c, v in p.slope_pct.items()}
    d["offset_s"] = {c: v * s_per_pct for c, v in p.offset_pct.items()}
    return d


@lru_cache(maxsize=1)
def _backtest_cached(path: str, mtime: float) -> dict | None:
    return read_json(path, default=None)


def backtest_headline(paths: DataPaths) -> dict | None:
    f = paths.models / "evaluation_runs" / "strategy_backtest.json"
    if not f.exists():
        return None
    b = _backtest_cached(str(f), f.stat().st_mtime)
    if not b:
        return None
    s = b["strategy"]["all"]
    return {"races": b["races_total"], "strategy_races": b["races_strategy_evaluated"],
            "plan_match": s["calibrated"]["plan_match"], "stops_match": s["calibrated"]["stops_match"],
            "start_match": s["calibrated"]["start_match"], "window_hit": s["calibrated"]["window_hit"],
            "previous_edition": s["previous_edition"], "finishing_order": b["finishing_order"],
            "lap_replay": b["lap_replay"]}
