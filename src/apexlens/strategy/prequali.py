"""Predicted starting grid for races whose qualifying has not happened yet.

The grid is ranked by each driver's recent qualifying gap to pole, as an exponentially weighted mean whose single
sessions are capped: a crash or a lap deleted in Q1 (a 3-5% "gap") would otherwise dominate the mean for several
races and push a fast driver down the predicted grid. The weight of this grid in the finishing-order blend is fitted
on earlier races *with this predicted grid* — a weight fitted on actual grids trusts a guessed grid far too much.

Chosen on the 2023-2025 races of the strategy backtest by mean prediction-game points (2026 held out); see
``reports/race_strategy.md`` and docs/progress.md. Alternatives tried (medians of gaps or positions, other half-lives
and caps, expected-points picks) were within about 1.5 points and not better.
"""

from __future__ import annotations

import pandas as pd

from apexlens.storage.io import read_table
from apexlens.storage.paths import DataPaths
from apexlens.strategy import race as RACE

HALF_LIFE = 2.0   # events
GAP_CAP = 1.5     # % of pole time; a worse single session counts as this
WINDOW = 60       # earlier races used to fit the blend weight


def qualifying_history(paths: DataPaths) -> pd.DataFrame:
    """One row per (event, driver) in grand-prix qualifying: date, position and gap to pole (%)."""
    q = read_table(paths.silver("qualifying_results"))
    if q.empty:
        return pd.DataFrame(columns=["event_id", "date", "driver_id", "position", "gap"])
    q = q[q["session_code"] == "Q"].copy()
    ev = read_table(paths.silver("events"))
    q["date"] = q["event_id"].map(ev.set_index("event_id")["date"].pipe(pd.to_datetime))
    q["position"] = pd.to_numeric(q["position"], errors="coerce")
    pole = q.groupby("event_id")["best_s"].transform("min")
    q["gap"] = 100.0 * (q["best_s"] / pole - 1.0)
    return q.sort_values(["date", "event_id"])[["event_id", "date", "driver_id", "position", "gap"]].reset_index(drop=True)


def grid_form(history: pd.DataFrame, before: pd.Timestamp, drivers: list[str], half_life: float = HALF_LIFE,
              cap: float = GAP_CAP) -> pd.Series:
    """Capped, recency-weighted qualifying gap to pole (lower is better) from sessions strictly before ``before``.
    Drivers without any earlier qualifying get NaN."""
    h = history[(history["date"] < before) & history["driver_id"].isin(drivers)]
    form = (h.assign(g=h["gap"].clip(upper=cap))
             .groupby("driver_id")["g"].apply(lambda s: s.ewm(halflife=half_life, ignore_na=True).mean().iloc[-1]))
    return form.reindex(drivers)


def grid_from_form(form: pd.Series) -> pd.Series:
    """Rank 1..n; drivers without history start behind everyone with history."""
    f = form.astype(float)
    return f.fillna(f.max() + 1 if f.notna().any() else 0).rank(method="first")


def fit_predicted_grid_weight(field: pd.DataFrame, history: pd.DataFrame, before: pd.Timestamp,
                              window: int = WINDOW) -> tuple[float, int]:
    """Blend weight for a predicted grid, fitted on the last ``window`` backtest races before ``before``.
    ``field``: the backtest table (event_id, date, driver_id, base_pct, position)."""
    if field.empty:
        return RACE.DEFAULT_W, 0
    f = field[pd.to_datetime(field["date"]) < before]
    events = f.groupby("event_id")["date"].first().sort_values().index[-window:]
    rows = []
    for eid in events:
        g = f[f["event_id"] == eid][["event_id", "driver_id", "base_pct", "position"]].copy()
        date = pd.to_datetime(f.loc[f["event_id"] == eid, "date"].iloc[0])
        g["grid"] = grid_from_form(grid_form(history, date, list(g["driver_id"]))).to_numpy()
        rows.append(g)
    return RACE.fit_weight(pd.concat(rows, ignore_index=True)) if rows else (RACE.DEFAULT_W, 0)
