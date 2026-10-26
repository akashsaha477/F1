"""Invariants of the ingested dataset (skipped when data/ has not been built)."""

import numpy as np
import pytest

from apexlens.storage.io import read_table
from apexlens.storage.paths import DataPaths

pytestmark = pytest.mark.realdata


@pytest.fixture(scope="module")
def paths() -> DataPaths:
    p = DataPaths.default()
    if not (p.gold("lap_features")).exists():
        pytest.skip("no gold tables in data/; run the pipeline first")
    return p


@pytest.fixture(scope="module")
def laps(paths):
    return read_table(paths.gold("all_laps_relative"))


def test_lap_keys_unique(laps):
    assert not laps.duplicated(["session_id", "driver_id", "lap_number"]).any()


def test_every_lap_has_identity(laps):
    assert laps["driver_id"].notna().all()
    assert laps["constructor_id"].notna().mean() > 0.99


def test_clean_laps_have_no_exclusion_reason(laps):
    assert laps.loc[laps["is_clean"], "exclusion_reason"].isna().all()
    assert laps.loc[~laps["is_clean"], "exclusion_reason"].notna().all()


def test_representative_laps_are_clean_and_close_to_driver_median(laps):
    rep = laps[laps["is_representative"].fillna(False).astype(bool)]
    assert rep["is_clean"].all()
    assert (rep["lap_time_s"] <= rep["drv_session_median_s"] * 1.05 + 1e-9).all()


def test_session_reference_is_median_of_clean_laps(laps):
    clean = laps[laps["is_clean"] & laps["lap_time_s"].notna()]
    med = clean.groupby("session_id")["lap_time_s"].median()
    ref = laps.groupby("session_id")["session_ref_s"].first().reindex(med.index)
    assert np.allclose(med.to_numpy(), ref.to_numpy(), rtol=1e-9)


def test_relative_pace_definition(laps):
    d = laps.dropna(subset=["rel_pace_pct", "lap_time_s", "session_ref_s"]).sample(5000, random_state=0)
    assert np.allclose(d["rel_pace_pct"], 100 * (d["lap_time_s"] / d["session_ref_s"] - 1))


def test_lap_times_positive_and_plausible(laps):
    lt = laps["lap_time_s"].dropna()
    assert (lt > 0).all()
    assert (lt.between(40, 600)).mean() > 0.999


def test_form_features_use_only_earlier_events(paths):
    form = read_table(paths.gold("driver_event_form")).sort_values(["driver_id", "date"])
    first = form.groupby("driver_id").head(1)
    # a driver's first event in the data has no prior form
    assert first["drv_form_pace"].isna().all()
    assert (form["drv_form_n"].fillna(0) <= 10).all()


def test_tyre_compounds_known_or_excluded(laps):
    known = {"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"}
    assert set(laps["compound"].dropna().unique()) <= known | {"UNKNOWN"}
    unknown = laps["compound"].isna() | (laps["compound"] == "UNKNOWN")
    assert not laps.loc[unknown, "is_clean"].any()
