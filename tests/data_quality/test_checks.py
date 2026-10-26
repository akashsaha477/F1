"""Each data-quality check fires on the defect it targets and stays quiet on real fixture data."""

import pandas as pd
import pytest

from apexlens.cleaning.entity_mapping import DriverResolution
from apexlens.cleaning.laps import normalize_laps, tracinginsights_laps_to_frame
from apexlens.cleaning.validation import summarize, validate_laps, validate_telemetry, validate_weather
from apexlens.ingestion.telemetry_ingest import telemetry_frame

CTX = {"session_id": "2024-01-R", "event_id": "2024-01", "season": 2024, "round": 1, "session_code": "R",
       "circuit_id": "bahrain", "source": "tracinginsights"}


class FakeResolver:
    ids = {"1": ("max-verstappen", "red-bull"), "11": ("sergio-perez", "red-bull"), "16": ("charles-leclerc", "ferrari")}

    def resolve(self, event_id, season, code, number, abbr):
        d, c = self.ids.get(str(number), (None, None))
        return DriverResolution(d, c, "session_number" if d else "unresolved")


@pytest.fixture
def silver_laps(ti_laps_payload) -> pd.DataFrame:
    out, _ = normalize_laps(tracinginsights_laps_to_frame(ti_laps_payload), CTX, FakeResolver())
    return out


def _status(results, name):
    return next(r for r in results if r.name == name)


def test_fixture_has_no_fatal_failures(silver_laps):
    s = summarize(validate_laps(silver_laps))
    assert s["fatal"] == []


def test_duplicate_laps_are_fatal(silver_laps):
    bad = pd.concat([silver_laps, silver_laps.iloc[[5]]], ignore_index=True)
    r = _status(validate_laps(bad), "duplicate_laps")
    assert not r.passed and r.severity == "fatal" and r.n_failed == 2
    assert summarize(validate_laps(bad))["status"] == "failed"


def test_negative_lap_time_is_fatal(silver_laps):
    bad = silver_laps.copy()
    bad.loc[bad.index[3], "lap_time_s"] = -1.0
    assert not _status(validate_laps(bad), "non_positive_lap_time").passed


def test_implausible_values_are_warnings_not_deletions(silver_laps):
    bad = silver_laps.copy()
    bad.loc[bad.index[4], "lap_time_s"] = 900.0
    bad.loc[bad.index[6], "speed_st_kph"] = 450.0
    bad.loc[bad.index[7], "track_temp_c"] = 90.0
    res = validate_laps(bad)
    for name in ("implausible_lap_time", "implausible_speed_st_kph", "implausible_track_temp"):
        r = _status(res, name)
        assert not r.passed and r.severity == "warning"
    assert len(bad) == len(silver_laps)  # checks flag, never drop


def test_sector_sum_mismatch(silver_laps):
    bad = silver_laps.copy()
    i = bad.index[bad["sector1_s"].notna() & bad["sector2_s"].notna() & bad["sector3_s"].notna()][0]
    bad.loc[i, "sector1_s"] += 2.0
    assert _status(validate_laps(bad), "sector_sum_mismatch").n_failed >= 1


def test_unresolved_identity_threshold(silver_laps):
    few = silver_laps.copy()
    few.loc[few.index[:1], "driver_id"] = None
    assert _status(validate_laps(few, {"max_unresolved_driver_frac": 0.5}), "unresolved_driver_identity").passed
    many = silver_laps.copy()
    many.loc[many.index[: len(many) // 5], "driver_id"] = None
    assert not _status(validate_laps(many), "unresolved_driver_identity").passed


def test_driver_with_two_constructors_in_one_session(silver_laps):
    bad = silver_laps.copy()
    d = bad["driver_id"].iloc[0]
    bad.loc[bad.index[(bad["driver_id"] == d).to_numpy().nonzero()[0][:2]], "constructor_id"] = "other-team"
    assert not _status(validate_laps(bad), "driver_with_multiple_constructors_in_session").passed


def test_mixed_sessions_in_partition(silver_laps):
    bad = silver_laps.copy()
    bad.loc[bad.index[0], "session_id"] = "2024-02-R"
    assert not _status(validate_laps(bad), "mixed_sessions_in_partition").passed


def test_weather_checks():
    w = pd.DataFrame({"air_temp_c": [20.0, 21.0, 80.0], "humidity_pct": [40.0, 120.0, 50.0],
                      "session_time_s": [0.0, 60.0, 30.0]})
    res = {r.name: r for r in validate_weather(w)}
    assert not res["implausible_air_temp"].passed
    assert not res["humidity_out_of_range"].passed
    assert not res["weather_time_not_increasing"].passed


def test_telemetry_checks(ti_tel_payload):
    tel = telemetry_frame(ti_tel_payload)
    assert summarize(validate_telemetry(tel))["fatal"] == []
    bad = tel.copy()
    bad.loc[bad.index[10], "time_s"] = bad["time_s"].iloc[5]
    bad.loc[bad.index[20], "gear"] = 11
    res = {r.name: r for r in validate_telemetry(bad)}
    assert not res["time_not_increasing"].passed and res["time_not_increasing"].severity == "fatal"
    assert not res["invalid_gear"].passed
