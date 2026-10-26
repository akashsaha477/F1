"""Time-aware evaluation splits.

Rows carry an ``event_id`` and a ``date``; laps from one event never straddle a split boundary.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Split:
    name: str
    train_idx: np.ndarray
    calib_idx: np.ndarray
    test_idx: np.ndarray
    train_period: str
    test_period: str

    def check_temporal(self, df: pd.DataFrame) -> None:
        """Raise if any training/calibration event is not strictly earlier than every test event."""
        if len(self.test_idx) == 0:
            return
        fit_dates = pd.to_datetime(df.loc[np.concatenate([self.train_idx, self.calib_idx]), "date"])
        test_dates = pd.to_datetime(df.loc[self.test_idx, "date"])
        if fit_dates.max() >= test_dates.min():
            raise AssertionError(f"{self.name}: training data reaches {fit_dates.max()} >= test start {test_dates.min()}")
        shared = set(df.loc[self.train_idx, "event_id"]) & set(df.loc[self.test_idx, "event_id"])
        if shared:
            raise AssertionError(f"{self.name}: events in both train and test: {sorted(shared)[:5]}")


def _calibration_tail(df: pd.DataFrame, idx: np.ndarray, frac: float) -> tuple[np.ndarray, np.ndarray]:
    """Split ``idx`` so the chronologically last ``frac`` of events become the calibration set."""
    ev = df.loc[idx].groupby("event_id")["date"].first().sort_values()
    n_cal = max(1, int(round(len(ev) * frac)))
    cal_events = set(ev.index[-n_cal:])
    mask = df.loc[idx, "event_id"].isin(cal_events).to_numpy()
    return idx[~mask], idx[mask]


def walk_forward_by_season(df: pd.DataFrame, min_train_seasons: int = 1, calib_frac: float = 0.2) -> Iterator[Split]:
    seasons = sorted(df["season"].unique())
    for i in range(min_train_seasons, len(seasons)):
        test_season = seasons[i]
        fit = np.flatnonzero(df["season"].lt(test_season).to_numpy())
        test = np.flatnonzero(df["season"].eq(test_season).to_numpy())
        train, calib = _calibration_tail(df, fit, calib_frac)
        yield Split(f"walk_forward_{test_season}", df.index[train].to_numpy(), df.index[calib].to_numpy(),
                    df.index[test].to_numpy(), f"{seasons[0]}-{test_season - 1}", str(test_season))


def final_fit_split(df: pd.DataFrame, calib_frac: float = 0.15) -> Split:
    """All data for fitting, with the most recent events held for conformal calibration."""
    idx = np.arange(len(df))
    train, calib = _calibration_tail(df, idx, calib_frac)
    seasons = sorted(df["season"].unique())
    return Split("final", df.index[train].to_numpy(), df.index[calib].to_numpy(), np.array([], dtype=int),
                 f"{seasons[0]}-{seasons[-1]}", "none")


def event_group_kfold(df: pd.DataFrame, k: int = 5, seed: int = 7, calib_frac: float = 0.2) -> Iterator[Split]:
    """Event-held-out folds (not chronological): probes generalisation to unseen events."""
    rng = np.random.default_rng(seed)
    events = np.array(sorted(df["event_id"].unique()))
    rng.shuffle(events)
    folds = np.array_split(events, k)
    for i, test_events in enumerate(folds):
        test = np.flatnonzero(df["event_id"].isin(test_events).to_numpy())
        fit = np.flatnonzero(~df["event_id"].isin(test_events).to_numpy())
        train, calib = _calibration_tail(df, fit, calib_frac)
        yield Split(f"event_kfold_{i}", df.index[train].to_numpy(), df.index[calib].to_numpy(), df.index[test].to_numpy(),
                    "all-but-fold", f"fold {i}")
