import pandas as pd
import pytest

from apexlens.cleaning.entity_mapping import DriverResolution
from apexlens.cleaning.laps import (
    lap_condition,
    normalize_laps,
    tracinginsights_corners_to_frame,
    tracinginsights_laps_to_frame,
    track_status_flags,
)
from apexlens.cleaning.validation import summarize, validate_laps

CTX = {"session_id": "2024-01-R", "event_id": "2024-01", "season": 2024, "round": 1, "session_code": "R",
       "circuit_id": "bahrain", "source": "tracinginsights"}


class FakeResolver:
    ids = {"1": ("max-verstappen", "red-bull"), "11": ("sergio-perez", "red-bull"), "16": ("charles-leclerc", "ferrari")}

    def resolve(self, event_id, season, code, number, abbr):
        d, c = self.ids.get(str(number), (None, None))
        return DriverResolution(d, c, "session_number" if d else "unresolved")


@pytest.fixture
def laps(ti_laps_payload):
    frame = tracinginsights_laps_to_frame(ti_laps_payload)
    out, report = normalize_laps(frame, CTX, FakeResolver())
    return out, report


def test_frame_conversion_types(ti_laps_payload):
    f = tracinginsights_laps_to_frame(ti_laps_payload)
    assert f["LapTime"].dtype == float
    assert f["Sector1Time"].isna().any()  # "None" strings become NaN
    assert f["DriverNumber"].iloc[0] in {"1", "11", "16"}
    assert str(f["Rainfall"].dtype) == "boolean"


def test_normalized_schema_and_identity(laps):
    out, report = laps
    assert set(out["driver_id"]) == {"max-verstappen", "sergio-perez", "charles-leclerc"}
    assert out["identity_method"].eq("session_number").all()
    assert len(report) == 3
    assert {"lap_time_s", "tyre_life_laps", "compound", "is_clean", "exclusion_reason", "condition"} <= set(out.columns)


def test_race_start_lap_is_never_clean(laps):
    out, _ = laps
    lap1 = out[out.lap_number == 1]
    assert (~lap1.is_clean).all()
    # labels are preserved, not deleted
    assert len(lap1) == 3


def test_clean_laps_meet_all_rules(laps):
    out, _ = laps
    clean = out[out.is_clean]
    assert len(clean) > 0
    assert clean.flag_green_only.all()
    assert not clean.is_pit_in_lap.any() and not clean.is_pit_out_lap.any()
    assert (clean.lap_time_s > 0).all()


def test_track_status_flags():
    assert track_status_flags("1")["flag_green_only"]
    f = track_status_flags("124")
    assert f["flag_yellow"] and f["flag_sc"] and not f["flag_green_only"]
    assert track_status_flags("67")["flag_vsc"]
    assert not track_status_flags(None)["status_known"]


def test_lap_condition():
    assert lap_condition("INTERMEDIATE", False) == "wet"
    assert lap_condition("SOFT", True) == "damp"
    assert lap_condition("HARD", False) == "dry"
    assert lap_condition("HARD", None) == "dry_unverified"


def test_validation_detects_duplicates_and_negative_times(laps):
    out, _ = laps
    bad = pd.concat([out, out.iloc[[5]]], ignore_index=True)
    bad.loc[0, "lap_time_s"] = -1.0
    res = summarize(validate_laps(bad))
    assert res["status"] == "failed"
    assert "duplicate_laps" in res["fatal"] and "non_positive_lap_time" in res["fatal"]


def test_validation_passes_on_real_excerpt(laps):
    out, _ = laps
    res = summarize(validate_laps(out))
    assert res["fatal"] == []


def test_unresolved_driver_threshold(laps):
    out, _ = laps
    out = out.copy()
    out.loc[out.index[:5], "driver_id"] = None
    res = summarize(validate_laps(out))
    assert "unresolved_driver_identity" in res["fatal"]


def test_corners_frame(fixtures_dir):
    import json

    payload = json.loads((fixtures_dir / "tracinginsights" / "bahrain_2024_corners.json").read_text())
    df, rot = tracinginsights_corners_to_frame(payload)
    assert len(df) == 15 and rot == 92.0
    assert df["Number"].tolist()[:3] == [1, 2, 3]
