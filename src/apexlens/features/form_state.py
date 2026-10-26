"""Pre-event form features for scenarios.

``form_as_of(event_id)`` returns the features exactly as they were before a historical event (the
same rows the models were trained/evaluated on). ``form_after_last_event()`` appends a pseudo
"next event" to every active driver's sequence and applies the same shifted-EWMA logic, i.e. the
form that would be used for an event after the most recent ingested one.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from apexlens.features.lap_features import FORM_N_CAP, HALF_LIFE_EVENTS, _ewm_prior

DRIVER_COLS = ["drv_form_pace", "drv_form_n", "drv_teammate_gap_form", "drv_quali_form"]
TEAM_COLS = ["team_form_pace", "team_quali_form", "team_season_form", "team_season_events"]


def form_as_of(form: pd.DataFrame, event_id: str) -> pd.DataFrame:
    rows = form[form["event_id"] == event_id]
    return rows.set_index("driver_id")


def form_after_last_event(form: pd.DataFrame) -> pd.DataFrame:
    form = form.copy()
    form["date"] = pd.to_datetime(form["date"])
    last_season = int(form["season"].max())
    latest = form[form["season"] == last_season].sort_values("date").groupby("driver_id").tail(1)
    next_date = form["date"].max() + pd.Timedelta(days=7)
    pseudo = latest[["driver_id", "constructor_id"]].assign(event_id="NEXT", season=last_season, date=next_date)
    base = pd.concat([form[["event_id", "driver_id", "constructor_id", "season", "date", "pace_dry", "tm_gap",
                            "evt_quali_gap"]], pseudo], ignore_index=True)
    order = ["date", "event_id"]
    base = base.sort_values(order).reset_index(drop=True)
    base["drv_form_pace"] = _ewm_prior(base, "driver_id", "pace_dry", order, HALF_LIFE_EVENTS)
    base["drv_form_n"] = base.groupby("driver_id")["pace_dry"].transform(
        lambda s: s.shift(1).notna().cumsum()).clip(upper=FORM_N_CAP)
    base["drv_teammate_gap_form"] = _ewm_prior(base, "driver_id", "tm_gap", order)
    base["drv_quali_form"] = _ewm_prior(base, "driver_id", "evt_quali_gap", order)
    team = base.groupby(["event_id", "constructor_id", "season", "date"]).agg(
        tpace=("pace_dry", "mean"), tquali=("evt_quali_gap", "mean")).reset_index().sort_values(order)
    team["team_form_pace"] = _ewm_prior(team, "constructor_id", "tpace", order)
    team["team_quali_form"] = _ewm_prior(team, "constructor_id", "tquali", order)
    team["team_season_form"] = team.groupby(["constructor_id", "season"])["tpace"].transform(
        lambda s: s.shift(1).expanding().mean())
    team["team_season_events"] = team.groupby(["constructor_id", "season"]).cumcount()
    out = base[base["event_id"] == "NEXT"].merge(team[["event_id", "constructor_id"] + TEAM_COLS],
                                                 on=["event_id", "constructor_id"], how="left")
    return out.set_index("driver_id")


def team_form_table(form_rows: pd.DataFrame) -> pd.DataFrame:
    """Team features keyed by constructor from a set of driver form rows (for 'same car' counterfactuals)."""
    cols = [c for c in TEAM_COLS if c in form_rows.columns]
    return form_rows.groupby("constructor_id")[cols].first()


def driver_circuit_history(form: pd.DataFrame, driver_id: str, circuit_id: str, before_season: int) -> tuple[float, int]:
    f = form[(form["driver_id"] == driver_id) & (form["circuit_id"] == circuit_id) & (form["season"] < before_season)]
    vals = (f["pace_dry"] - f["drv_form_pace"]).dropna()
    return (float(vals.mean()) if len(vals) else np.nan), int(len(vals))
