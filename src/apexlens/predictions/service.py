"""Scenario predictions with structured explanations (Model A and Model D).

Feature vectors are assembled from the gold tables exactly as during training: form features come
from :mod:`apexlens.features.form_state`, circuit descriptors from previous seasons only, and the
scenario conditions from the request.
"""

from __future__ import annotations

import logging
from functools import cached_property
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from apexlens.explainability.local import (
    comparison_narrative,
    contribution_rows,
    group_rows,
    label,
    lap_narrative,
)
from apexlens.features.form_state import driver_circuit_history, form_after_last_event, form_as_of
from apexlens.modeling import lap_pace as LP
from apexlens.modeling.registry import load_artifact, production_version
from apexlens.modeling.uncertainty import condition_group
from apexlens.schemas.api import ComparisonRequest, LapTimeRequest, ScenarioConditions
from apexlens.storage.io import read_json, read_table
from apexlens.storage.paths import DataPaths

log = logging.getLogger(__name__)

WET = {"INTERMEDIATE", "WET"}
MIN_COMPOUND_DRIVER_LAPS = 30
MIN_WET_DRIVER_LAPS = 30


class ScenarioError(ValueError):
    """Request cannot be answered from the stored data (unknown driver, no form, ...)."""


class PredictionService:
    def __init__(self, paths: DataPaths):
        self.paths = paths
        self._artifacts: dict[str, tuple] = {}

    # -- data ------------------------------------------------------------------------------
    @cached_property
    def form(self) -> pd.DataFrame:
        f = read_table(self.paths.gold("driver_event_form"))
        if f.empty or "date" not in f:
            raise ScenarioError("feature tables are not built; run scripts/build_features.py")
        f["date"] = pd.to_datetime(f["date"])
        return f

    def ensure_ready(self, horizon: str) -> None:
        self.artifact(horizon)
        _ = self.form

    @cached_property
    def next_form(self) -> pd.DataFrame:
        return form_after_last_event(self.form)

    @cached_property
    def events(self) -> pd.DataFrame:
        e = read_table(self.paths.silver("events"))
        e["date"] = pd.to_datetime(e["date"])
        return e

    @cached_property
    def drivers(self) -> pd.DataFrame:
        return read_table(self.paths.silver("drivers")).set_index("driver_id")

    @cached_property
    def circuits(self) -> pd.DataFrame:
        return read_table(self.paths.silver("circuits")).set_index("circuit_id")

    @cached_property
    def constructors(self) -> pd.DataFrame:
        return read_table(self.paths.silver("constructors")).set_index("constructor_id")

    @cached_property
    def laps(self) -> pd.DataFrame:
        cols = ["event_id", "season", "date", "circuit_id", "driver_id", "constructor_id", "compound", "is_wet_compound",
                "track_temp_c", "air_temp_c", "humidity_pct", "session_ref_s", "session_code", "is_representative"]
        lf = read_table(self.paths.gold("lap_features"), columns=cols)
        lf = lf[lf["is_representative"]]
        lf["date"] = pd.to_datetime(lf["date"])
        return lf

    @cached_property
    def circuit_profiles(self) -> pd.DataFrame:
        p = read_table(self.paths.gold("circuit_profiles"))
        return p.set_index("circuit_id") if len(p) else p

    def artifact(self, horizon: str):
        if horizon not in self._artifacts:
            version = production_version(self.paths.models, f"{LP.TASK}_{horizon}")
            if not version:
                raise ScenarioError(f"no production model for horizon {horizon}; run scripts/train_models.py")
            obj, meta = load_artifact(self.paths.models, version)
            ens_path = Path(self.paths.models) / version / "ensemble.joblib"
            ensemble = joblib.load(ens_path) if ens_path.exists() else None
            self._artifacts[horizon] = (obj, meta, ensemble)
        return self._artifacts[horizon]

    def driver_name(self, driver_id: str) -> str:
        return str(self.drivers.loc[driver_id, "name"]) if driver_id in self.drivers.index else driver_id

    # -- feature assembly -----------------------------------------------------------------
    def _context(self, cond: ScenarioConditions) -> dict:
        if cond.as_of_event_id:
            ev = self.events[self.events["event_id"] == cond.as_of_event_id]
            if ev.empty:
                raise ScenarioError(f"unknown event {cond.as_of_event_id}")
            ev = ev.iloc[0]
            if cond.circuit_id and cond.circuit_id != ev["circuit_id"]:
                raise ScenarioError(f"event {cond.as_of_event_id} was held at {ev['circuit_id']}, not {cond.circuit_id}")
            form = form_as_of(self.form, cond.as_of_event_id)
            if form.empty:
                raise ScenarioError(f"no form data for event {cond.as_of_event_id} (outside the lap-timing seasons?)")
            return {"circuit_id": ev["circuit_id"], "season": int(ev["season"]), "date": ev["date"], "form": form,
                    "as_of": f"before {cond.as_of_event_id}", "event": ev}
        if cond.circuit_id not in self.circuits.index:
            raise ScenarioError(f"unknown circuit {cond.circuit_id}")
        last = self.form["date"].max()
        return {"circuit_id": cond.circuit_id, "season": int(self.form["season"].max()), "date": last + pd.Timedelta(days=7),
                "form": self.next_form, "as_of": f"after the last ingested event ({last.date()})", "event": None,
                "note": (f"Hypothetical next race with the cars and form of the {int(self.form['season'].max())} season; "
                         "not a forecast for a later regulation era.")}

    def _circuit_features(self, circuit_id: str, season: int, before: pd.Timestamp) -> dict:
        ev = self.events[(self.events["circuit_id"] == circuit_id) & (self.events["date"] < before)].sort_values("date")
        circ = self.circuits.loc[circuit_id] if circuit_id in self.circuits.index else None
        latest = ev.iloc[-1] if len(ev) else None
        laps_hist = self.laps[(self.laps["circuit_id"] == circuit_id) & (self.laps["date"] < before)]
        race_hist = laps_hist[(laps_hist["session_code"] == "R") & (laps_hist["season"] < season)]
        ref_prev = race_hist.groupby("event_id")["session_ref_s"].first().median() if len(race_hist) else np.nan
        all_race = laps_hist[laps_hist["session_code"] == "R"]
        ref_any = all_race.groupby("event_id")["session_ref_s"].first().median() if len(all_race) else np.nan
        out = {
            "circuit_length_km": float(latest["course_length_km"]) if latest is not None else float(circ["length_km"]) if circ is not None else np.nan,
            "circuit_turns": float(latest["turns"]) if latest is not None else float(circ["turns"]) if circ is not None else np.nan,
            "circuit_is_street": float((latest["circuit_type"] if latest is not None else circ["type"]) == "STREET") if (latest is not None or circ is not None) else np.nan,
            "circuit_ref_lap_s": float(ref_prev) if pd.notna(ref_prev) else np.nan,
            "scheduled_laps": int(latest["laps"]) if latest is not None and pd.notna(latest["laps"]) else 57,
            "_ref_lap_for_seconds": float(ref_any) if pd.notna(ref_any) else (float(ref_prev) if pd.notna(ref_prev) else None),
            "_weather_medians": {c: float(laps_hist[c].median()) if laps_hist[c].notna().any() else np.nan
                                 for c in ["track_temp_c", "air_temp_c", "humidity_pct"]},
            "_n_events_at_circuit": int(laps_hist["event_id"].nunique()),
        }
        if len(self.circuit_profiles) and circuit_id in self.circuit_profiles.index:
            for c in ["circuit_frac_slow", "circuit_frac_fast", "circuit_full_throttle_frac"]:
                if c in self.circuit_profiles.columns:
                    out[c] = float(self.circuit_profiles.loc[circuit_id, c])
        return out

    def build_row(self, req: LapTimeRequest, ctx: dict | None = None) -> tuple[pd.DataFrame, dict]:
        ctx = ctx or self._context(req)
        form = ctx["form"]
        if req.driver_id not in form.index:
            raise ScenarioError(
                f"no form for driver {req.driver_id} {ctx['as_of']}; the driver must have raced in the lap-timing "
                "seasons (use as_of_event_id for historical scenarios)")
        frow = form.loc[req.driver_id]
        if isinstance(frow, pd.DataFrame):
            frow = frow.iloc[0]
        circ = self._circuit_features(ctx["circuit_id"], ctx["season"], ctx["date"])
        assumptions = []
        row = {f: frow.get(f, np.nan) for f in LP.DRIVER + LP.TEAM}
        team_id = frow.get("constructor_id")
        if req.constructor_override:
            others = form[form["constructor_id"] == req.constructor_override]
            if others.empty:
                raise ScenarioError(f"constructor {req.constructor_override} has no form {ctx['as_of']}")
            for f in LP.TEAM:
                row[f] = others.iloc[0].get(f, np.nan)
            assumptions.append(f"Team features replaced by {req.constructor_override}'s (counterfactual car).")
            team_id = req.constructor_override
        hist, n_hist = driver_circuit_history(self.form, req.driver_id, ctx["circuit_id"], ctx["season"])
        row["drv_circuit_hist"] = hist
        row.update({k: v for k, v in circ.items() if not k.startswith("_") and k != "scheduled_laps"})
        for c in ["track_temp_c", "air_temp_c", "humidity_pct"]:
            val = getattr(req, c)
            if val is None:
                val = circ["_weather_medians"][c]
                assumptions.append(f"{label(c)} not given: using the circuit's historical median ({val:.1f}).")
            row[c] = val
        wet = req.compound in WET
        row.update({
            "compound": req.compound, "tyre_life_laps": float(req.tyre_life_laps),
            "fresh_tyre": float(req.fresh_tyre if req.fresh_tyre is not None else req.tyre_life_laps <= 3),
            "stint": float(req.stint), "rainfall": float(req.rainfall), "is_wet_compound": float(wet),
            "race_progress": float(req.race_progress), "lap_number": float(round(req.race_progress * circ["scheduled_laps"])),
            "is_sprint": float(req.is_sprint),
        })
        if req.horizon == "pre_race":
            if req.quali_gap_pct is not None:
                row["evt_quali_gap"] = req.quali_gap_pct
                assumptions.append(f"Assumed qualifying gap to pole: {req.quali_gap_pct:.2f}%.")
            elif ctx["event"] is not None:
                row["evt_quali_gap"] = frow.get("evt_quali_gap", np.nan)
                assumptions.append("Qualifying gap taken from the actual qualifying session of this event.")
            else:
                row["evt_quali_gap"] = row.get("drv_quali_form", np.nan)
                assumptions.append("No qualifying result: assumed qualifying gap equals the driver's recent average.")
            team_rows = form[form["constructor_id"] == team_id]
            row["evt_team_quali_gap"] = (team_rows["evt_quali_gap"].mean() if ctx["event"] is not None
                                         else team_rows["drv_quali_form"].mean())
        if ctx["event"] is None:
            obj_meta = self.artifact(req.horizon)[1]
            cap = obj_meta.get("feature_ranges", {}).get("team_season_events", {}).get("max")
            if cap is not None and pd.notna(row.get("team_season_events")) and row["team_season_events"] > cap:
                row["team_season_events"] = cap
                assumptions.append(f"Races completed this season capped at {cap:.0f} (training maximum).")
        info = {"ctx": ctx, "circuit": circ, "assumptions": assumptions, "team_id": team_id, "n_circuit_hist": n_hist,
                "form_row": frow}
        return pd.DataFrame([row]), info

    # -- evidence and range checks ---------------------------------------------------------
    def evidence(self, driver_id: str, circuit_id: str, compound: str, before: pd.Timestamp, team_id: str | None) -> dict:
        L = self.laps[self.laps["date"] < before]
        d = L[L["driver_id"] == driver_id]
        return {
            "driver_representative_laps": int(len(d)),
            "driver_events": int(d["event_id"].nunique()),
            "driver_laps_at_circuit": int((d["circuit_id"] == circuit_id).sum()),
            "driver_events_at_circuit": int(d[d["circuit_id"] == circuit_id]["event_id"].nunique()),
            "driver_laps_on_compound": int((d["compound"] == compound).sum()),
            "driver_wet_laps": int((d["is_wet_compound"] > 0.5).sum()),
            "team_events": int(L[L["constructor_id"] == team_id]["event_id"].nunique()) if team_id else 0,
            "training_laps_on_compound": int((L["compound"] == compound).sum()),
            "cutoff": str(before.date()),
        }

    @staticmethod
    def range_flags(X: pd.DataFrame, meta: dict) -> list[dict]:
        flags = []
        for f, r in meta.get("feature_ranges", {}).items():
            if f not in X.columns:
                continue
            v = pd.to_numeric(X[f], errors="coerce").iloc[0]
            if pd.notna(v) and (v < r["p01"] or v > r["p99"]):
                flags.append({"feature": f, "label": label(f), "value": float(v), "p01": r["p01"], "p99": r["p99"],
                              "outside_observed_range": bool(v < r["min"] or v > r["max"])})
        return flags

    def _warnings(self, ev: dict, flags: list[dict], req: ScenarioConditions, n_hist: int) -> list[str]:
        w = []
        if req.compound in WET and ev["driver_wet_laps"] < MIN_WET_DRIVER_LAPS:
            w.append(f"Insufficient wet-weather evidence for this driver ({ev['driver_wet_laps']} representative wet laps).")
        if ev["driver_laps_on_compound"] < MIN_COMPOUND_DRIVER_LAPS:
            w.append(f"Few laps by this driver on {req.compound} ({ev['driver_laps_on_compound']}).")
        if ev["driver_events"] < 3:
            w.append("Fewer than three previous races for this driver: form features are weak.")
        outside = [f for f in flags if f["outside_observed_range"]]
        if outside:
            w.append("Extrapolation: " + ", ".join(f["label"] for f in outside) + " outside the range seen in training.")
        return w

    # -- predictions -----------------------------------------------------------------------
    def _predict_row(self, X: pd.DataFrame, horizon: str):
        obj, meta, ensemble = self.artifact(horizon)
        model, conf = obj["model"], obj["conformal"]
        pred = float(model.predict(X)[0])
        lo, hi = conf.interval(np.array([pred]), condition_group(X))
        base, contrib = model.contributions(X)
        ens = np.array([m.predict(X)[0] for m in ensemble]) if ensemble else None
        return pred, float(lo[0]), float(hi[0]), float(base[0]), contrib.iloc[0], ens, meta

    def predict_lap(self, req: LapTimeRequest) -> dict:
        self.ensure_ready(req.horizon)
        X, info = self.build_row(req)
        pred, lo, hi, base, contrib, ens, meta = self._predict_row(X, req.horizon)
        ref = info["circuit"]["_ref_lap_for_seconds"]
        spp = ref / 100.0 if ref else None
        rows = contribution_rows(contrib, X.iloc[0], LP.FEATURE_GROUP, spp)
        ev = self.evidence(req.driver_id, info["ctx"]["circuit_id"], req.compound, info["ctx"]["date"], info["team_id"])
        flags = self.range_flags(X, meta)
        cond = condition_group(X)[0]
        payload = {
            "task": "lap_time", "horizon": req.horizon, "model": meta["model"], "model_version": meta["model_version"],
            "target": meta["target"], "target_definition": "Representative race-lap time relative to the session "
            "reference (median clean lap of all drivers in that session); negative = faster.",
            "inputs": {**req.model_dump(), "driver_name": self.driver_name(req.driver_id),
                       "circuit_name": self.circuits.loc[info["ctx"]["circuit_id"], "name"] if info["ctx"]["circuit_id"] in self.circuits.index else None,
                       "circuit_id": info["ctx"]["circuit_id"], "form_as_of": info["ctx"]["as_of"],
                       "constructor_id": info["team_id"]},
            "prediction": {
                "value_pct": pred, "value_s": pred * spp if spp else None,
                "interval": {"lo_pct": lo, "hi_pct": hi, "lo_s": lo * spp if spp else None, "hi_s": hi * spp if spp else None,
                             "level": meta["conformal"]["level"], "method": meta["conformal"]["method"],
                             "condition_group": cond},
                "model_uncertainty": ({"lo_pct": float(np.quantile(ens, 0.05)), "hi_pct": float(np.quantile(ens, 0.95)),
                                       "sd_pct": float(np.std(ens)), "n_models": int(len(ens)),
                                       "method": "event-cluster bootstrap refits (5th-95th percentile)"}
                                      if ens is not None else None),
            },
            "reference_lap_s": ref,
            "reference_description": "Median session-reference race lap at this circuit in the ingested seasons; used "
                                     "only to convert % to seconds.",
            "baseline": {"value_pct": base, "description": "Average model output over its training data (SHAP base value)"},
            "contributions": rows,
            "group_contributions": group_rows(rows, spp),
            "assumptions": info["assumptions"] + [f"Form features as they stood {info['ctx']['as_of']}."]
            + ([info["ctx"]["note"]] if info["ctx"].get("note") else []),
            "evidence": {**ev, "driver_events_at_circuit_prior_seasons": info["n_circuit_hist"]},
            "extrapolation": flags,
            "warnings": self._warnings(ev, flags, req, info["n_circuit_hist"]),
            "evaluation": {"holdout": _metric_subset(meta["test_metrics"]["holdout"]),
                           "development": _metric_subset(meta["test_metrics"]["development"]),
                           "train_period": meta["train_period"]},
            "limitations": [
                "Contributions are exact TreeSHAP values of the model, i.e. how the model uses inputs, not causal effects.",
                "Form features mix driver and car performance; team features are a proxy for the car.",
                "Traffic, damage, setup and strategy instructions are not observed.",
            ],
        }
        payload["uncertainty"] = uncertainty_summary(payload)
        payload["narrative"] = lap_narrative(payload)
        return payload

    def compare(self, req: ComparisonRequest) -> dict:
        self.ensure_ready(req.horizon)
        ctx = self._context(req)
        a_id, b_id = req.driver_ids
        base_fields = req.model_dump(exclude={"driver_ids", "common_car"})
        reqs = [LapTimeRequest(**base_fields, driver_id=d) for d in (a_id, b_id)]
        if req.common_car:
            team_a = ctx["form"].loc[a_id, "constructor_id"] if a_id in ctx["form"].index else None
            reqs[1] = LapTimeRequest(**base_fields, driver_id=b_id, constructor_override=team_a)
        rows, infos, preds = [], [], []
        for r in reqs:
            X, info = self.build_row(r, ctx)
            rows.append(X)
            infos.append(info)
            preds.append(self._predict_row(X, req.horizon))
        ref = infos[0]["circuit"]["_ref_lap_for_seconds"]
        spp = ref / 100.0 if ref else None
        (pa, loa, hia, _, ca, ea, meta), (pb, lob, hib, _, cb, eb, _) = preds
        diff_contrib = ca - cb
        drows = contribution_rows(diff_contrib, rows[0].iloc[0], LP.FEATURE_GROUP, spp)
        evs = [self.evidence(r.driver_id, ctx["circuit_id"], req.compound, ctx["date"], i["team_id"]) for r, i in zip(reqs, infos, strict=True)]
        warnings = []
        for r, ev, X in zip(reqs, evs, rows, strict=True):
            warnings += [f"{self.driver_name(r.driver_id)}: {w}" for w in self._warnings(ev, self.range_flags(X, meta), req, 0)]
        diff = pa - pb
        mu = None
        if ea is not None:
            d = ea - eb
            mu = {"lo_pct": float(np.quantile(d, 0.05)), "hi_pct": float(np.quantile(d, 0.95)), "sd_pct": float(np.std(d)),
                  "n_models": int(len(d)), "prob_a_faster": float(np.mean(d < 0)),
                  "method": "event-cluster bootstrap refits (5th-95th percentile)"}
        out = {
            "task": "driver_comparison", "horizon": req.horizon, "model_version": meta["model_version"],
            "target_definition": "Difference in expected representative race-lap pace (first minus second driver), "
                                 "% of session reference; negative = first driver faster.",
            "scenario": {**base_fields, "circuit_id": ctx["circuit_id"], "form_as_of": ctx["as_of"], "common_car": req.common_car},
            "drivers": [{"driver_id": r.driver_id, "name": self.driver_name(r.driver_id), "constructor_id": i["team_id"],
                         "prediction_pct": p[0], "interval_pct": [p[1], p[2]], "evidence": ev}
                        for r, i, p, ev in zip(reqs, infos, preds, evs, strict=True)],
            "difference": {"value_pct": diff, "value_s": diff * spp if spp else None, "model_uncertainty": mu,
                           "contributions": drows, "group_contributions": group_rows(drows, spp)},
            "reference_lap_s": ref,
            "warnings": sorted(set(warnings)),
            "limitations": ["Lap-to-lap noise is excluded: the comparison concerns expected pace.",
                            "Driver and car effects are only separated to the extent team features capture the car."],
        }
        out["counterfactuals"] = self._comparison_counterfactuals(req, ctx, diff)
        out["narrative"] = comparison_narrative(out)
        return out

    def _comparison_counterfactuals(self, req: ComparisonRequest, ctx: dict, diff: float) -> dict:
        res = {}
        if not req.common_car:
            same = req.model_copy(update={"common_car": True})
            try:
                Xa, _ = self.build_row(LapTimeRequest(**same.model_dump(exclude={"driver_ids", "common_car"}), driver_id=req.driver_ids[0]), ctx)
                team_a = ctx["form"].loc[req.driver_ids[0], "constructor_id"]
                Xb, _ = self.build_row(LapTimeRequest(**same.model_dump(exclude={"driver_ids", "common_car"}),
                                                      driver_id=req.driver_ids[1], constructor_override=team_a), ctx)
                pa = self._predict_row(Xa, req.horizon)[0]
                pb = self._predict_row(Xb, req.horizon)[0]
                res["same_car"] = {"difference_pct": pa - pb, "description": "both drivers given the first driver's team features"}
            except ScenarioError as exc:
                res["same_car"] = {"error": str(exc)}
        alt = "INTERMEDIATE" if req.compound not in WET else "MEDIUM"
        alt_req = req.model_copy(update={"compound": alt, "rainfall": alt in WET})
        try:
            pa = self._predict_row(self.build_row(LapTimeRequest(**alt_req.model_dump(exclude={"driver_ids", "common_car"}), driver_id=req.driver_ids[0]), ctx)[0], req.horizon)[0]
            pb = self._predict_row(self.build_row(LapTimeRequest(**alt_req.model_dump(exclude={"driver_ids", "common_car"}), driver_id=req.driver_ids[1]), ctx)[0], req.horizon)[0]
            res["conditions_switched"] = {"compound": alt, "difference_pct": pa - pb,
                                          "description": "same comparison with wet/dry conditions switched"}
        except ScenarioError as exc:
            res["conditions_switched"] = {"error": str(exc)}
        return res

    def counterfactuals(self, req: LapTimeRequest) -> dict:
        """Model-estimated changes for single, plausible changes to scenario inputs (not causal effects)."""
        self.ensure_ready(req.horizon)
        X, info = self.build_row(req)
        obj, meta, _ = self.artifact(req.horizon)
        model = obj["model"]
        base_pred = float(model.predict(X)[0])
        ranges = meta["feature_ranges"]
        out = []
        for comp in ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]:
            if comp == req.compound:
                continue
            Xc = X.copy()
            Xc["compound"] = comp
            Xc["is_wet_compound"] = float(comp in WET)
            Xc["rainfall"] = float(comp in WET)
            out.append({"change": f"compound -> {comp}", "feature": "compound", "new_value": comp,
                        "delta_pct": float(model.predict(Xc)[0]) - base_pred,
                        "supported": meta["compound_counts"].get(comp, 0) > 500})
        for f in ["tyre_life_laps", "race_progress", "track_temp_c"]:
            if f not in ranges:
                continue
            r = ranges[f]
            grid = np.linspace(r["p01"], r["p99"], 9)
            preds = []
            for v in grid:
                Xc = X.copy()
                Xc[f] = v
                if f == "race_progress":
                    Xc["lap_number"] = round(v * info["circuit"]["scheduled_laps"])
                preds.append(float(model.predict(Xc)[0]))
            preds = np.array(preds)
            k = int(np.argmax(np.abs(preds - base_pred)))
            shown = f"{grid[k]:.2f}" if f == "race_progress" else f"{grid[k]:.1f}"
            out.append({"change": f"{label(f)} -> {shown}", "feature": f, "new_value": float(grid[k]),
                        "delta_pct": float(preds[k] - base_pred), "supported": True,
                        "curve": [{"value": float(v), "prediction_pct": float(p)} for v, p in zip(grid, preds, strict=True)]})
        out.sort(key=lambda r: -abs(r["delta_pct"]))
        return {"base_prediction_pct": base_pred, "changes": out,
                "note": "Changes are evaluated one at a time within the central 98% of training data. They describe the "
                        "model's response, not the causal effect of an intervention."}


def uncertainty_summary(p: dict) -> dict:
    """Four separately reported components (no combined score). Level rules are fixed and documented here."""
    ev = p["evidence"]
    n_ev, n_circ = ev.get("driver_events", 0), ev.get("driver_laps_at_circuit", 0)
    coverage = "good" if n_ev >= 10 and n_circ >= 30 else ("limited" if n_ev >= 3 else "weak")
    reasons = []
    if n_ev < 10:
        reasons.append(f"{n_ev} previous races for this driver")
    if n_circ < 30:
        reasons.append(f"{n_circ} representative laps at this circuit")
    if p["inputs"].get("compound") in WET and ev.get("driver_wet_laps", 0) < MIN_WET_DRIVER_LAPS:
        coverage = "weak"
        reasons.append("few wet laps")
    iv = p["prediction"]["interval"]
    mu = p["prediction"].get("model_uncertainty")
    outside = [f for f in p["extrapolation"] if f["outside_observed_range"]]
    return {
        "data_coverage": {"level": coverage, "reasons": reasons,
                          "rule": "good: >= 10 previous races and >= 30 laps at the circuit; limited: >= 3 races; weak otherwise or wet with < 30 wet laps"},
        "lap_to_lap_and_model_error": {"interval_half_width_pct": (iv["hi_pct"] - iv["lo_pct"]) / 2, "level": iv["level"],
                                       "meaning": "range for a single representative lap (conformal, calibrated on later races)"},
        "model_uncertainty": {"sd_pct": mu["sd_pct"] if mu else None,
                              "meaning": "spread of the expected value across event-bootstrap refits"},
        "extrapolation_risk": {"level": "outside_training_range" if outside else ("edge_of_training_data" if p["extrapolation"] else "none"),
                               "features": [f["feature"] for f in p["extrapolation"]]},
    }


def _metric_subset(m: dict) -> dict:
    keys = ["n", "mae", "rmse", "r2", "coverage", "interval_width", "mae_seconds"]
    out = {k: m.get(k) for k in keys}
    if "mae_ci" in m:
        out["mae_ci"] = [m["mae_ci"]["lo"], m["mae_ci"]["hi"]]
    return out


def load_service(paths: DataPaths | None = None) -> PredictionService:
    return PredictionService(paths or DataPaths.default())


def evaluation_run(paths: DataPaths) -> dict | None:
    latest = read_json(paths.models / "evaluation_runs" / "latest.json")
    if not latest:
        return None
    return read_json(paths.models / "evaluation_runs" / f"{latest['run_id']}.json")
