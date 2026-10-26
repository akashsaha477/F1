import numpy as np
import pandas as pd

from apexlens.evaluation import metrics as M
from apexlens.explainability.local import comparison_narrative, contribution_rows, group_rows, lap_narrative


def test_basic_metrics():
    y, p = np.array([0.0, 1.0, 2.0]), np.array([0.0, 2.0, 2.0])
    assert M.mae(y, p) == 1 / 3
    assert M.rmse(y, p) == np.sqrt(1 / 3)
    assert M.coverage(y, p - 0.5, p + 0.5) == 2 / 3


def test_paired_bootstrap_detects_better_model():
    rng = np.random.default_rng(0)
    df = pd.DataFrame({"event_id": np.repeat(np.arange(30), 50), "y": rng.normal(0, 1, 1500)})
    df["good"] = df["y"] + rng.normal(0, 0.1, 1500)
    df["bad"] = df["y"] + rng.normal(0, 1.0, 1500)
    res = M.paired_mae_difference(df, "good", "bad", n_boot=200)
    assert res["estimate"] < 0 and res["significant"]


def test_contribution_rows_and_narrative():
    contrib = pd.Series({"drv_form_pace": -0.5, "race_progress": 0.2, "compound": 0.01})
    values = pd.Series({"drv_form_pace": -0.8, "race_progress": 0.4, "compound": "SOFT"})
    rows = contribution_rows(contrib, values, {"drv_form_pace": "driver", "race_progress": "race_context"}, 0.9)
    assert rows[0]["feature"] == "drv_form_pace" and rows[0]["direction"] == "faster"
    assert rows[0]["contribution_s"] == -0.45
    groups = group_rows(rows, 0.9)
    assert groups[0]["group"] == "driver"
    payload = {"prediction": {"value_pct": -0.3, "value_s": -0.27,
                              "interval": {"lo_pct": -1.0, "hi_pct": 0.4, "level": 0.9},
                              "model_uncertainty": {"lo_pct": -0.4, "hi_pct": -0.2}},
               "inputs": {"driver_id": "x", "driver_name": "Driver X", "circuit_id": "c", "circuit_name": "Circuit"},
               "model": "lightgbm", "horizon": "pre_event", "contributions": rows, "warnings": ["Few laps."]}
    text = lap_narrative(payload)
    assert "0.30% faster" in text and "-1.00% to +0.40%" in text and "not causal" in text and "Few laps." in text


def test_comparison_narrative_flags_overlap():
    c = {"drivers": [{"name": "A"}, {"name": "B"}],
         "difference": {"value_pct": -0.1, "value_s": -0.09,
                        "model_uncertainty": {"lo_pct": -0.3, "hi_pct": 0.1, "n_models": 20}, "group_contributions": []}}
    assert "not established" in comparison_narrative(c)
