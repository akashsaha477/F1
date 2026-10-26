"""Model C helpers, empirical-Bayes power, clustering stability and ablation specs (synthetic data)."""

import numpy as np
import pandas as pd

from apexlens.driver_profiles.clustering import describe, stability
from apexlens.driver_profiles.mixed_model import empirical_bayes
from apexlens.modeling.ablation import ORDER, spec_for
from apexlens.modeling.tyre_model import _ols_slope, degradation_summaries, driver_deg_effects


def test_ols_slope_recovers_degradation():
    age = np.arange(1, 21, dtype=float)
    y = 0.08 * age + np.random.default_rng(0).normal(0, 0.05, 20)
    b, se, _ = _ols_slope(age, y)
    assert abs(b - 0.08) < 0.01 and se > 0


def synthetic_stints(driver_effect: float = 0.0, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(40):
        for d in range(10):
            dev = driver_effect if d == 0 else 0.0
            rows.append({"session_id": f"2024-{s:02d}-R", "season": 2024, "circuit_id": f"c{s % 10}", "driver_id": f"d{d}",
                         "compound": "MEDIUM", "slope_pct": 0.06 + dev + rng.normal(0, 0.02), "slope_se": 0.02,
                         "track_temp_c": rng.uniform(20, 50), "session_ref_s": 90.0})
    return pd.DataFrame(rows)


def test_degradation_summary_and_driver_effects():
    st = synthetic_stints()
    summ = degradation_summaries(st)
    row = summ["by_compound"].iloc[0]
    assert abs(row["slope_pct"] - 0.06) < 0.005 and row["ci_lo"] < 0.06 < row["ci_hi"]
    eff = driver_deg_effects(st)
    assert (eff["status"] != "supported").all()  # no real driver differences were simulated


def test_driver_deg_effect_detected_when_real():
    eff = driver_deg_effects(synthetic_stints(driver_effect=0.04)).set_index("driver_id")
    assert eff.loc["d0", "status"] == "supported" and eff.loc["d0", "posterior_mean"] > 0.02


def test_empirical_bayes_has_power_when_effects_exist():
    rng = np.random.default_rng(1)
    truth = rng.normal(0, 0.3, 30)
    est = truth + rng.normal(0, 0.1, 30)
    post, pvar, tau2 = empirical_bayes(est, np.full(30, 0.01))
    assert 0.15 < np.sqrt(tau2) < 0.45
    assert np.mean(np.abs(post) > 1.645 * np.sqrt(pvar)) > 0.25  # vs ~0 when there are no real effects


def test_cluster_stability_and_descriptions():
    rng = np.random.default_rng(0)
    two = np.r_[rng.normal(-3, 0.3, (40, 3)), rng.normal(3, 0.3, (40, 3))]
    assert stability(two, 2, n_boot=20) > 0.9
    assert stability(rng.normal(0, 1, (80, 3)), 4, n_boot=20) < 0.9
    text = describe(pd.Series({"race_pace_adj": -1.2, "quali_adj": 0.1}))
    assert text[0].startswith("lower team-adjusted race pace")


def test_ablation_specs():
    full = spec_for(ORDER, available={"drv_form_pace", "team_form_pace", "tyre_life_laps", "race_progress", "compound"})
    assert "compound" in full.categorical and "drv_form_pace" in full.numeric
    no_tyre = spec_for([g for g in ORDER if g != "tyre"], available={"drv_form_pace", "tyre_life_laps"})
    assert no_tyre.categorical == [] and "tyre_life_laps" not in no_tyre.numeric
