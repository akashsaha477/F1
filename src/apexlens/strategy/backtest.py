"""Backtest of the race strategy planner against what actually happened.

Every race from the second ingested season on is planned with data available before its start
(parameters before the race date, pace model trained on earlier seasons, weather from the weekend's
sessions). The plan is then compared with the race:

* strategy — number of stops and starting compound vs the most common choice among the top-10 finishers
  (and the winner); first pit stop vs the top-10 drivers who stopped as often as planned; share of their
  first stops inside the planned window. Baselines: copy the previous race at the same circuit; the most
  common stop count in all earlier races. Wet and red-flagged races are excluded (free tyre changes);
  races are split into green races and races with a safety car / VSC, which force reactive strategies.
* lap times — every top-10 finisher's *actual* tyre sequence is replayed through the model and compared
  with their representative laps; baseline: a constant lap time at the predicted pace.
* finishing order — blend of grid and predicted pace (weight fitted on earlier races only) vs grid order
  and pace order, on classified finishers.

All intervals are 95% bootstrap intervals over races.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import numpy as np
import pandas as pd

from apexlens.predictions.service import PredictionService
from apexlens.storage.io import write_json, write_table
from apexlens.storage.paths import DataPaths
from apexlens.strategy import calibration as CAL
from apexlens.strategy import race as RACE
from apexlens.strategy.actual import classified, race_summary
from apexlens.strategy.data import StrategyData
from apexlens.strategy.optimizer import lap_trace, optimise
from apexlens.strategy.pace import base_paces, season_model
from apexlens.strategy.params import estimate_params
from apexlens.strategy.weather import climatology, scenario, weekend_sessions

log = logging.getLogger(__name__)


def _mean_ci(x, n_boot: int = 2000, seed: int = 0) -> dict:
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], dtype=float)
    if len(x) == 0:
        return {"estimate": None, "lo": None, "hi": None, "n": 0}
    rng = np.random.default_rng(seed)
    boots = rng.choice(x, size=(n_boot, len(x)), replace=True).mean(axis=1)
    return {"estimate": float(x.mean()), "lo": float(np.quantile(boots, 0.025)), "hi": float(np.quantile(boots, 0.975)),
            "n": int(len(x))}


def _paired(a, b, n_boot: int = 2000, seed: int = 0) -> dict:
    d = [x - y for x, y in zip(a, b, strict=True) if x is not None and y is not None and np.isfinite(x) and np.isfinite(y)]
    r = _mean_ci(d, n_boot, seed)
    r["significant"] = bool(r["n"] and (r["lo"] > 0 or r["hi"] < 0))
    return r


def _previous_edition(data: StrategyData, circuit_id: str, before: pd.Timestamp) -> dict | None:
    prev = data.races[(data.races["circuit_id"] == circuit_id) & (data.races["date"] < before) & ~data.races["wet"]
                      & ~data.races["red"]]
    if prev.empty:
        return None
    p = prev.iloc[-1]
    s = race_summary(data, p["event_id"])
    if not s or s["top_modal_stops"] is None:
        return None
    return {**s, "laps_scheduled": int(p["scheduled_laps"])}


def _replay(data: StrategyData, params, event_id: str, top: list[dict], base: pd.Series) -> list[dict]:
    rows = []
    laps = data.laps[(data.laps["session_id"] == f"{event_id}-R") & data.laps["is_representative"].fillna(False)]
    for t in top:
        if not t["dry_only"] or t["driver_id"] not in base.index:
            continue
        trace = pd.DataFrame(lap_trace(params, t["sequence"], t["stint_laps"], float(base[t["driver_id"]])))
        act = laps[laps["driver_id"] == t["driver_id"]][["lap_number", "lap_time_s"]]
        m = act.merge(trace, left_on="lap_number", right_on="lap", suffixes=("_act", "_pred"))
        if m.empty:
            continue
        const = params.ref_lap_s * (1 + float(base[t["driver_id"]]) / 100)
        rows.append({"event_id": event_id, "driver_id": t["driver_id"], "n": int(len(m)),
                     "mae_model_s": float(np.mean(np.abs(m["lap_time_s_act"] - m["lap_time_s_pred"]))),
                     "mae_constant_s": float(np.mean(np.abs(m["lap_time_s_act"] - const))),
                     "bias_model_s": float(np.mean(m["lap_time_s_pred"] - m["lap_time_s_act"]))})
    return rows


def run_backtest(paths: DataPaths) -> dict:
    data = StrategyData(paths)
    svc = PredictionService(paths)
    races = data.races[data.races["season"] > data.races["season"].min()].sort_values("date")
    models = {}
    field_rows, per_race, replay = [], [], []
    cand_rows, target_rows = [], []
    for r in races.itertuples():
        ev = data.events.loc[r.event_id]
        season = int(r.season)
        if season not in models:
            models[season] = season_model(paths, season)
        model, _ = models[season]
        params = estimate_params(data, r.circuit_id, ev["date"], season, int(r.scheduled_laps), event_id=r.event_id)
        plans = optimise(params)
        if not plans:
            continue
        wk = weekend_sessions(data, r.event_id)
        clim = climatology(data, r.circuit_id, ev["date"])
        weather = scenario(wk, clim, None, {})["values"]
        bp = base_paces(svc, model, event_id=r.event_id, circuit_id=None, weather=weather)
        res = classified(data, r.event_id)
        field = bp.merge(res[["driver_id", "grid_position", "position"]], on="driver_id", how="left").rename(
            columns={"grid_position": "grid"})
        prior = pd.DataFrame(field_rows)
        w, n_w = RACE.fit_weight(prior) if len(prior) else (RACE.DEFAULT_W, 0)
        actual = field.set_index("driver_id")["position"]
        order = {}
        for name, weight in (("blend", w), ("grid_order", 1.0), ("pace_order", 0.0)):
            pred = RACE.predict_order(field, weight).set_index("driver_id")["predicted_position"]
            order[name] = RACE.order_metrics(pred, actual)
        field_rows += field.assign(event_id=r.event_id, date=ev["date"]).to_dict("records")

        summ = race_summary(data, r.event_id) or {}
        cal = (CAL.fit(pd.concat(cand_rows, ignore_index=True), pd.DataFrame(target_rows)) if target_rows
               else {"stop_s": 0.0, "soft_stint_s": 0.0, "races": 0, "agreement": None})
        variants = {"physical": plans, "calibrated": CAL.apply(plans, cal)}
        row = {"event_id": r.event_id, "season": season, "circuit_id": r.circuit_id, "date": str(ev["date"].date()),
               "wet": bool(r.wet), "red_flag": bool(r.red), "safety_car": bool(r.sc), "vsc": bool(r.vsc),
               "green": bool(not r.sc and not r.vsc), "calibration": cal,
               "blend_weight": w, "blend_weight_races": n_w, "order": order, "rule_notes": params.rule_notes}
        for name, pl in variants.items():
            b = pl[0]
            row[name] = {"plan": b["label"], "stops": b["stops"], "start": b["sequence"][0], "key": CAL.plan_key(b["stops"], b["sequence"]),
                         "first_stop": b["pit_laps"][0], "window": [b["pit_windows"][0]["from_lap"], b["pit_windows"][0]["to_lap"]]}
        strategy_ok = not r.wet and not r.red and summ.get("top_modal_stops") is not None
        row["strategy_evaluated"] = bool(strategy_ok)
        if strategy_ok:
            top = [t for t in summ["top"] if t["dry_only"]]
            win = summ["winner"]
            prev = _previous_edition(data, r.circuit_id, ev["date"])
            earlier = [x for x in per_race if x.get("strategy_evaluated")]
            glob_stops = int(pd.Series([x["actual_modal_stops"] for x in earlier]).mode().min()) if earlier else 1
            row.update({"actual_modal_stops": summ["top_modal_stops"], "actual_modal_start": summ["top_modal_start"],
                        "actual_modal_plan": summ["top_modal_plan"],
                        "winner": win["driver_id"] if win else None, "winner_strategy": win["label"] if win else None,
                        "previous_edition": prev["event_id"] if prev else None})
            for name in variants:
                v = row[name]
                same = [t["pit_laps"][0] for t in top if t["stops"] == v["stops"] and t["pit_laps"]]
                v.update({
                    "stops_match": v["stops"] == summ["top_modal_stops"],
                    "plan_match": v["key"] == summ["top_modal_plan"],
                    "start_match": v["start"] == summ["top_modal_start"],
                    "stops_match_winner": bool(win) and v["stops"] == win["stops"],
                    "first_stop_error": float(abs(v["first_stop"] - np.median(same))) if same else None,
                    "window_hit": float(np.mean([v["window"][0] <= x <= v["window"][1] for x in same])) if same else None,
                })
            row["previous"] = {
                "stops_match": (prev["top_modal_stops"] == summ["top_modal_stops"]) if prev else None,
                "plan_match": (prev["top_modal_plan"] == summ["top_modal_plan"]) if prev else None,
                "start_match": (prev["top_modal_start"] == summ["top_modal_start"]) if prev else None,
                "first_stop_error": (float(abs(prev["top_first_stop_median"] * r.scheduled_laps / prev["laps_scheduled"]
                                               - summ["top_first_stop_median"]))
                                     if prev and prev["top_first_stop_median"] is not None
                                     and summ["top_first_stop_median"] is not None
                                     and prev["top_modal_stops"] == summ["top_modal_stops"] else None)}
            row["most_common_stops"] = {"stops_match": glob_stops == summ["top_modal_stops"]}
            replay += _replay(data, params, r.event_id, top, bp.set_index("driver_id")["base_pct"])
            cand_rows.append(CAL.candidate_table(r.event_id, plans))
            target_rows.append({"event_id": r.event_id, "actual_stops": summ["top_modal_stops"],
                                "actual_key": summ["top_modal_plan"]})
        per_race.append(row)
        log.info("backtest %s %s plan=%s calibrated=%s actual=%s", r.event_id, r.circuit_id, row["physical"]["plan"],
                 row["calibrated"]["plan"], row.get("actual_modal_plan"))

    if cand_rows:
        write_table(paths.models / "strategy" / "calibration_candidates", pd.concat(cand_rows, ignore_index=True))
        write_table(paths.models / "strategy" / "calibration_targets",
                    pd.DataFrame(target_rows).merge(races[["event_id", "date"]], on="event_id"))
    out = summarise(per_race, replay)
    write_json(paths.models / "evaluation_runs" / "strategy_backtest.json", out)
    write_table(paths.models / "strategy" / "backtest_field", pd.DataFrame(field_rows))
    return out


def summarise(per_race: list[dict], replay: list[dict]) -> dict:
    ev = [r for r in per_race if r.get("strategy_evaluated")]

    def col(rows, who, k):
        vals = [(r.get(who) or {}).get(k) for r in rows]
        return [float(v) if v is not None else None for v in vals]

    metrics = ("stops_match", "plan_match", "start_match", "stops_match_winner", "first_stop_error", "window_hit")
    strategy = {}
    for part, rows in (("all", ev), ("green", [r for r in ev if r["green"]]),
                       ("safety_car_or_vsc", [r for r in ev if not r["green"]])):
        block = {"races": len(rows)}
        for who in ("physical", "calibrated"):
            block[who] = {k: _mean_ci(col(rows, who, k)) for k in metrics}
        block["previous_edition"] = {k: _mean_ci(col(rows, "previous", k))
                                     for k in ("stops_match", "plan_match", "start_match", "first_stop_error")}
        block["most_common_stops"] = {"stops_match": _mean_ci(col(rows, "most_common_stops", "stops_match"))}
        block["calibrated_minus_previous_edition"] = {
            k: _paired(col(rows, "calibrated", k), col(rows, "previous", k)) for k in ("stops_match", "plan_match", "start_match")}
        block["calibrated_minus_physical"] = {k: _paired(col(rows, "calibrated", k), col(rows, "physical", k))
                                              for k in ("stops_match", "plan_match", "start_match", "first_stop_error")}
        strategy[part] = block
    order = {}
    for name in ("blend", "grid_order", "pace_order"):
        ms = [r["order"].get(name) or {} for r in per_race]
        order[name] = {k: _mean_ci([m.get(k) for m in ms if m]) for k in ("spearman", "winner_correct", "podium_overlap",
                                                                          "position_mae")}
    blend_vs_grid = _paired([(r["order"].get("blend") or {}).get("spearman") for r in per_race],
                            [(r["order"].get("grid_order") or {}).get("spearman") for r in per_race])
    rp = pd.DataFrame(replay)
    lap_replay = {}
    if len(rp):
        g = rp.groupby("event_id")
        lap_replay = {"drivers": int(len(rp)), "laps": int(rp["n"].sum()),
                      "model_mae_s": _mean_ci(g["mae_model_s"].mean()),
                      "constant_pace_mae_s": _mean_ci(g["mae_constant_s"].mean()),
                      "model_bias_s": _mean_ci(g["bias_model_s"].mean()),
                      "model_minus_constant": _paired(g["mae_model_s"].mean().tolist(), g["mae_constant_s"].mean().tolist())}
    last_cal = next((r["calibration"] for r in reversed(per_race) if r.get("calibration")), None)
    return {
        "run_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "races_total": len(per_race), "races_strategy_evaluated": len(ev),
        "excluded_from_strategy": {"wet": [r["event_id"] for r in per_race if r["wet"]],
                                   "red_flag": [r["event_id"] for r in per_race if r["red_flag"] and not r["wet"]]},
        "strategy": strategy, "latest_calibration": last_cal, "finishing_order": order,
        "blend_minus_grid_spearman": blend_vs_grid, "lap_replay": lap_replay, "races": per_race,
        "notes": ["Planned with data available before each race; the pace model for season S is trained on earlier seasons.",
                  "'Actual' = the choice most often made by the top-10 classified finishers (plan = stop count + set of "
                  "compounds). Safety cars and VSCs change real strategies, so green races are reported separately.",
                  "'calibrated' adds per-stop and per-SOFT-stint costs fitted on earlier races only; 'physical' uses "
                  "lap-time effects alone.",
                  "Finishing-order metrics use classified finishers only; retirements are not predicted.",
                  "Intervals are 95% bootstrap intervals over races."],
    }
