"""Form features must only use information from earlier events."""

import numpy as np
import pandas as pd

from apexlens.features.form_state import form_after_last_event
from apexlens.features.lap_features import _ewm_prior, driver_event_form


def toy_inputs(values: dict[str, list[float]]):
    events = pd.DataFrame({"event_id": [f"2024-{i:02d}" for i in range(1, 6)], "season": 2024, "round": range(1, 6),
                           "date": pd.date_range("2024-03-01", periods=5, freq="14D"), "circuit_id": [f"c{i}" for i in range(5)]})
    rows = []
    for d, vals in values.items():
        for e, v in zip(events.itertuples(), vals, strict=True):
            rows.append({"session_id": f"{e.event_id}-R", "event_id": e.event_id, "season": 2024, "round": e.round,
                         "session_code": "R", "circuit_id": e.circuit_id, "driver_id": d,
                         "constructor_id": "t1" if d in ("a", "b") else "t2", "med_rel_pace": v, "n_laps": 40,
                         "teammate_gap": 0.0, "is_wet_session": False})
    summary = pd.DataFrame(rows)
    quali = summary[["event_id", "driver_id", "constructor_id"]].assign(quali_gap_pct=1.0)
    return summary, quali, events


def test_ewm_prior_excludes_current_row():
    df = pd.DataFrame({"k": ["x"] * 4, "v": [1.0, 2.0, 3.0, 4.0], "o": [1, 2, 3, 4]})
    out = _ewm_prior(df, "k", "v", ["o"])
    assert np.isnan(out.iloc[0]) and out.iloc[1] == 1.0
    assert out.iloc[2] < 2.0  # EWMA of [1, 2] only


def test_future_values_do_not_change_past_features():
    s1, q, ev = toy_inputs({"a": [0.1, 0.2, 0.3, 0.4, 0.5], "b": [0.0, 0.0, 0.0, 0.0, 0.0]})
    s2, _, _ = toy_inputs({"a": [0.1, 0.2, 0.3, 9.0, 9.0], "b": [0.0, 0.0, 0.0, 0.0, 0.0]})
    f1 = driver_event_form(s1, q, ev).set_index(["event_id", "driver_id"]).sort_index()
    f2 = driver_event_form(s2, q, ev).set_index(["event_id", "driver_id"]).sort_index()
    cols = ["drv_form_pace", "team_form_pace", "drv_quali_form", "team_season_form"]
    early = [i for i in f1.index if i[0] <= "2024-04"]
    pd.testing.assert_frame_equal(f1.loc[early, cols], f2.loc[early, cols])
    assert f1.loc[("2024-05", "a"), "drv_form_pace"] != f2.loc[("2024-05", "a"), "drv_form_pace"]


def test_first_event_has_no_form():
    s, q, ev = toy_inputs({"a": [0.1] * 5, "b": [0.2] * 5})
    f = driver_event_form(s, q, ev)
    first = f[f.event_id == "2024-01"]
    assert first["drv_form_pace"].isna().all() and (first["drv_form_n"] == 0).all()


def test_next_event_form_includes_last_event():
    s, q, ev = toy_inputs({"a": [0.0, 0.0, 0.0, 0.0, 1.0], "b": [0.0] * 5})
    f = driver_event_form(s, q, ev)
    nxt = form_after_last_event(f)
    last_pre = f[(f.event_id == "2024-05") & (f.driver_id == "a")]["drv_form_pace"].iloc[0]
    assert last_pre == 0.0 and nxt.loc["a", "drv_form_pace"] > 0.0
