"""Predicted grid before qualifying: capped recency-weighted form and a blend weight fitted on predicted grids."""

import numpy as np
import pandas as pd

from apexlens.strategy import prequali as PQ


def history(rows):
    df = pd.DataFrame(rows, columns=["event_id", "driver_id", "gap"])
    df["date"] = pd.to_datetime("2026-01-01") + pd.to_timedelta(df["event_id"].str[-2:].astype(int) * 7, unit="D")
    df["position"] = df.groupby("event_id")["gap"].rank(method="first")
    return df


def test_one_bad_session_does_not_dominate_the_grid():
    # "fast" is quicker than "steady" in every session except one, four races ago, where they crashed in Q1
    # (a 5% "gap"). Capped, the crash fades; uncapped, it still ranks them behind "steady" (Antonelli, 2026 R15).
    rows = []
    for i, fast_gap in enumerate([0.05, 5.0, 0.08, 0.04, 0.06, 0.05], 1):
        rows += [(f"2026-{i:02d}", "fast", fast_gap), (f"2026-{i:02d}", "steady", 0.30), (f"2026-{i:02d}", "slow", 0.9)]
    h = history(rows)
    before = pd.Timestamp("2026-03-01")
    capped = PQ.grid_form(h, before, ["fast", "steady", "slow", "rookie"])
    assert capped["fast"] < capped["steady"] < capped["slow"] and np.isnan(capped["rookie"])
    grid = PQ.grid_from_form(capped)
    assert list(grid.sort_values().index) == ["fast", "steady", "slow", "rookie"]
    # the uncapped mean (the old behaviour) is fooled by the single crash
    uncapped = PQ.grid_form(h, before, ["fast", "steady"], cap=100.0)
    assert uncapped["fast"] > uncapped["steady"]


def test_form_uses_only_sessions_before_the_race():
    h = history([("2026-01", "a", 0.1), ("2026-01", "b", 0.5), ("2026-02", "a", 3.0), ("2026-02", "b", 0.0)])
    early = PQ.grid_form(h, pd.Timestamp("2026-01-10"), ["a", "b"])  # only round 1 is before this date
    assert early["a"] < early["b"]


def test_predicted_grid_weight_is_fitted_on_predicted_grids():
    # qualifying form says a < b < c < d < e < f, but races finish in pace order; a grid-trusting weight would lose
    rng = np.random.default_rng(0)
    q_rows, field_rows = [], []
    drivers = list("abcdef")
    pace = dict(zip(drivers, [0.5, 0.4, 0.3, 0.2, 0.1, 0.0], strict=True))  # f fastest
    for i in range(1, 13):
        eid = f"2026-{i:02d}"
        for j, d in enumerate(drivers):
            q_rows.append((eid, d, 0.1 * j))
            field_rows.append({"event_id": eid, "driver_id": d, "base_pct": pace[d] + rng.normal(0, 0.01),
                               "position": 6 - j})
    h = history(q_rows)
    field = pd.DataFrame(field_rows)
    field["date"] = field["event_id"].map(h.groupby("event_id")["date"].first())
    w, n = PQ.fit_predicted_grid_weight(field, h, pd.Timestamp("2027-01-01"))
    assert n >= 10 and w < 0.5
