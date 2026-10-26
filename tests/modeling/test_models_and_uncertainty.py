"""Model portfolio tests on synthetic data with known structure (not real results)."""

import numpy as np
import pandas as pd
import pytest
import shap

from apexlens.evaluation.splits import event_group_kfold, walk_forward_by_season
from apexlens.modeling.models import (
    FeatureSpec,
    HistoricalGroupMedian,
    LightGBMPaceModel,
    LinearPaceModel,
    TeamAdjustedBaseline,
)
from apexlens.modeling.uncertainty import MondrianConformal, conformal_quantile

SPEC = FeatureSpec(numeric=["drv_form_pace", "team_form_pace", "drv_teammate_gap_form", "tyre_life_laps",
                            "race_progress", "track_temp_c"], categorical=["compound"], spline=["race_progress"])


def synthetic(n_events=30, laps_per_event=200, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for e in range(n_events):
        season = 2022 + e // 10
        date = pd.Timestamp(f"{season}-03-01") + pd.Timedelta(days=14 * (e % 10))
        for _ in range(laps_per_event):
            d = rng.integers(0, 10)
            comp = rng.choice(["SOFT", "MEDIUM", "HARD"])
            rows.append({"event_id": f"{season}-{e % 10 + 1:02d}", "season": season, "date": date,
                         "driver_id": f"d{d}", "compound": comp, "drv_form_pace": d * 0.1 - 0.5 + rng.normal(0, 0.05),
                         "team_form_pace": (d // 2) * 0.2 - 0.4, "drv_teammate_gap_form": rng.normal(0, 0.1),
                         "tyre_life_laps": rng.integers(1, 30), "race_progress": rng.uniform(0, 1),
                         "track_temp_c": rng.uniform(20, 50), "is_wet_compound": 0.0})
    df = pd.DataFrame(rows)
    df["rel_pace_pct"] = (0.8 * df["drv_form_pace"] - 1.0 * df["race_progress"]
                          + 0.03 * df["tyre_life_laps"] * (df["compound"] == "SOFT") + rng.normal(0, 0.3, len(df)))
    return df.reset_index(drop=True)


@pytest.fixture(scope="module")
def data():
    return synthetic()


@pytest.mark.parametrize("model", [LinearPaceModel(SPEC, name="ridge"), LinearPaceModel(SPEC, name="gam"),
                                   LightGBMPaceModel(SPEC, params={"n_estimators": 200})])
def test_contributions_are_additive(data, model):
    model.fit(data, data["rel_pace_pct"])
    X = data.sample(200, random_state=1)
    base, contrib = model.contributions(X)
    np.testing.assert_allclose(base + contrib.sum(axis=1).to_numpy(), model.predict(X), atol=1e-6)


def test_linear_model_recovers_signs(data):
    m = LinearPaceModel(FeatureSpec(numeric=SPEC.numeric, categorical=["compound"]), name="ridge").fit(data, data["rel_pace_pct"])
    coefs = {c["design_column"]: c["coef_per_sd"] for c in m.coefficients()}
    assert coefs["num__drv_form_pace"] > 0 and coefs["num__race_progress"] < 0
    assert coefs["num__tyre_life_x_soft"] > 0


def test_lightgbm_contributions_match_shap_library(data):
    m = LightGBMPaceModel(SPEC, params={"n_estimators": 100, "objective": "regression"}).fit(data, data["rel_pace_pct"])
    X = data.sample(100, random_state=2)
    _, contrib = m.contributions(X)
    explainer = shap.TreeExplainer(m.model.booster_)
    sv = explainer.shap_values(m._prep(X))
    np.testing.assert_allclose(contrib.to_numpy(), sv, atol=1e-6)


def test_lightgbm_is_reproducible(data):
    a = LightGBMPaceModel(SPEC, params={"n_estimators": 100}, seed=3).fit(data, data["rel_pace_pct"]).predict(data.head(50))
    b = LightGBMPaceModel(SPEC, params={"n_estimators": 100}, seed=3).fit(data, data["rel_pace_pct"]).predict(data.head(50))
    np.testing.assert_array_equal(a, b)


def test_baselines(data):
    h = HistoricalGroupMedian().fit(data, data["rel_pace_pct"])
    new = data.head(5).assign(driver_id="unknown-driver")
    pred, level = h._lookup(new)
    assert (level >= 2).all() and np.isfinite(pred).all()
    t = TeamAdjustedBaseline().fit(data, data["rel_pace_pct"])
    base, contrib = t.contributions(data.head(20))
    np.testing.assert_allclose(base + contrib.sum(axis=1), t.predict(data.head(20)))


def test_conformal_coverage_on_exchangeable_data():
    rng = np.random.default_rng(0)
    y_cal, y_test = rng.normal(0, 1, 5000), rng.normal(0, 1, 5000)
    conf = MondrianConformal(alpha=0.1).fit(y_cal, np.zeros(5000), np.array(["dry"] * 5000))
    lo, hi = conf.interval(np.zeros(5000), np.array(["dry"] * 5000))
    cov = np.mean((y_test >= lo) & (y_test <= hi))
    assert 0.88 < cov < 0.92
    assert conformal_quantile(np.arange(1, 11), 0.1) == 10


def test_mondrian_groups_fall_back_to_pooled():
    y = np.r_[np.zeros(500), np.ones(10) * 5]
    conf = MondrianConformal(alpha=0.1, min_group=200).fit(y, np.zeros(510), np.r_[["dry"] * 500, ["wet"] * 10])
    assert "wet" not in conf.group_q_
    assert conf.half_width(["wet"])[0] == conf.global_q_


def test_walk_forward_splits_are_temporal(data):
    splits = list(walk_forward_by_season(data))
    assert [s.test_period for s in splits] == ["2023", "2024"]
    for s in splits:
        s.check_temporal(data)
        fit_events = set(data.loc[np.r_[s.train_idx, s.calib_idx], "event_id"])
        assert not fit_events & set(data.loc[s.test_idx, "event_id"])
        assert data.loc[s.calib_idx, "date"].min() >= data.loc[s.train_idx, "date"].max()


def test_temporal_check_detects_leakage(data):
    s = next(walk_forward_by_season(data))
    s.train_idx = np.r_[s.train_idx, s.test_idx[:5]]
    with pytest.raises(AssertionError):
        s.check_temporal(data)


def test_event_kfold_disjoint(data):
    seen = set()
    for s in event_group_kfold(data, k=5):
        test_events = set(data.loc[s.test_idx, "event_id"])
        assert not test_events & set(data.loc[s.train_idx, "event_id"])
        assert not test_events & seen
        seen |= test_events
    assert seen == set(data["event_id"])
