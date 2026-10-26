import numpy as np

from apexlens.cleaning.validation import summarize, validate_telemetry
from apexlens.data_sources.tracinginsights import TracingInsightsSource, parse_tree_listing, session_code_for
from apexlens.ingestion.telemetry_ingest import telemetry_frame


def test_parse_tree_listing():
    paths = [
        "Bahrain Grand Prix/Race/session_laptimes.json",
        "Bahrain Grand Prix/Race/weather.json",
        "Bahrain Grand Prix/Race/VER/10_tel.json",
        "Bahrain Grand Prix/Race/VER/11_tel.json",
        "Bahrain Grand Prix/Race/VER/laptimes.json",
        "Bahrain Grand Prix/Practice 1/weather.json",  # no lap timing -> dropped
        "Pre-Season Testing/Practice 1/session_laptimes.json",
        "cache/x.json",
    ]
    idx = parse_tree_listing(2024, paths)
    assert list(idx.sessions) == [("Bahrain Grand Prix", "Race")]
    si = idx.sessions[("Bahrain Grand Prix", "Race")]
    assert si.telemetry["VER"] == {10, 11}
    assert "weather.json" in si.files


def test_session_codes():
    assert session_code_for("Sprint Qualifying", 2022) == "S_LEGACY"
    assert session_code_for("Sprint Qualifying", 2024) == "SQ"
    assert session_code_for("Sprint Shootout", 2023) == "SQ"
    assert session_code_for("Race", 2024) == "R"


def test_url_quoting():
    src = TracingInsightsSource(http=None, raw_base="https://raw.example/TI", git_base="g", cache_dir=".")
    url = src.url(2024, "São Paulo Grand Prix", "Race", "session_laptimes.json")
    assert url == "https://raw.example/TI/2024/main/S%C3%A3o%20Paulo%20Grand%20Prix/Race/session_laptimes.json"


def test_telemetry_frame_units(ti_tel_payload):
    df = telemetry_frame(ti_tel_payload)
    assert {"time_s", "speed_kph", "x_m", "y_m", "brake", "throttle_pct", "distance_m"} <= set(df.columns)
    # coordinates converted from 1/10 m to metres: step length ~ speed * dt
    step = np.hypot(np.diff(df.x_m), np.diff(df.y_m))
    expected = (df.speed_kph.to_numpy()[1:] / 3.6) * np.diff(df.time_s)
    ratio = step.sum() / expected.sum()
    assert 0.9 < ratio < 1.1
    assert df.brake.dtype == bool
    df["lap_key"] = "a"
    res = summarize(validate_telemetry(df))
    assert res["fatal"] == []
