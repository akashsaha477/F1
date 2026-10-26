"""Stage-1 adjustment and fingerprint helpers on synthetic sessions with known structure."""

import numpy as np
import pandas as pd

from apexlens.driver_profiles.fingerprint import (
    _percentile_lower_better,
    _status,
    session_regression_residuals,
)
from apexlens.driver_profiles.session_adjust import adjust_session

OFFSETS = {"a": -0.6, "b": -0.2, "c": 0.0, "d": 0.3, "e": 0.5}


def race(seed=0, pit=True, compound_per_driver=False):
    rng = np.random.default_rng(seed)
    rows = []
    comp_effect = {"SOFT": -0.4, "MEDIUM": 0.0, "HARD": 0.3}
    deg = {"SOFT": 0.08, "MEDIUM": 0.05, "HARD": 0.03}
    for i, (d, off) in enumerate(OFFSETS.items()):
        stop = 20 + 3 * i if pit else 999
        first = "SOFT" if (compound_per_driver and i % 2 == 0) else ("MEDIUM" if compound_per_driver else "MEDIUM")
        for lap in range(2, 50):
            comp, stint, age = (first, 1, lap) if lap < stop else ("HARD", 2, lap - stop + 1)
            y = off + comp_effect[comp] + deg[comp] * age - 0.05 * lap + rng.normal(0, 0.15)
            rows.append({"driver_id": d, "compound": comp, "tyre_life_laps": age, "lap_number": lap, "stint": stint, "rel_pace_pct": y})
    return pd.DataFrame(rows)


def test_adjust_session_recovers_driver_offsets():
    out = adjust_session(race()).set_index("driver_id")
    est = out["adj_pace"] - out["adj_pace"].mean()
    truth = pd.Series(OFFSETS) - np.mean(list(OFFSETS.values()))
    assert np.allclose(est.loc[truth.index], truth, atol=0.08)
    assert (out["adjusted_for"] == "compound+age+lap").all()
    assert abs(out["fuel_slope_pct_per_lap"].iloc[0] + 0.05) < 0.02
    assert (out["se"] > 0).all()


def test_no_stop_session_drops_fuel_term():
    out = adjust_session(race(pit=False))
    assert (out["adjusted_for"] == "age").all() or (out["adjusted_for"] == "compound+age").all()
    assert out["fuel_slope_pct_per_lap"].isna().all()


def test_one_compound_per_driver_drops_compound_offset():
    out = adjust_session(race(pit=False, compound_per_driver=True))
    assert (out["adjusted_for"] == "age").all()


def test_percentile_and_status():
    p = _percentile_lower_better(pd.Series([-1.0, 0.0, 1.0]))
    assert list(p) == [100.0, 50.0, 0.0]
    assert _status(1, 100, 0.5, 0.1, 2, 30) == "insufficient_evidence"
    assert _status(5, 100, 0.5, 0.1, 2, 30) == "supported"
    assert _status(5, 100, 0.1, 0.1, 2, 30) == "not_distinguishable_from_zero"
    assert _status(5, 100, 0.0, 0.0, 2, 30) == "not_distinguishable_from_zero"


def test_session_regression_absorbs_amplification():
    # wet gaps are 2x the dry expectation for everyone except driver 'x', who gains 0.5
    exp = np.linspace(-1, 1, 10)
    obs = 2 * exp
    obs[3] -= 0.5
    df = pd.DataFrame({"session_id": "s", "driver_id": [f"d{i}" if i != 3 else "x" for i in range(10)], "obs": obs, "exp": exp})
    out = session_regression_residuals(df, "obs", "exp").set_index("driver_id")
    assert out.loc["x", "dev"] < -0.3
    assert abs(out["slope"].iloc[0] - 2) < 0.2
