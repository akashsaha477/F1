import math

import pytest

from apexlens.cleaning.parsing import normalize_compound, normalize_text, parse_duration_s, to_bool, to_float


@pytest.mark.parametrize(
    "value,expected",
    [("1:30.031", 90.031), ("1:31:44.742", 5504.742), ("36.604", 36.604), ("+22.457", 22.457), (95.5, 95.5)],
)
def test_parse_duration(value, expected):
    assert parse_duration_s(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", [None, "None", "", "+1 Lap", "DNF", float("nan")])
def test_parse_duration_invalid_is_nan(value):
    assert math.isnan(parse_duration_s(value))


@pytest.mark.parametrize(
    "raw,expected",
    [("SOFT", "SOFT"), ("soft", "SOFT"), ("INTERMEDIATE", "INTERMEDIATE"), ("Inter", "INTERMEDIATE"),
     ("WET", "WET"), ("HYPERSOFT", "LEGACY_SLICK"), ("TEST_UNKNOWN", "UNKNOWN"), (None, "UNKNOWN"), ("nan", "UNKNOWN")],
)
def test_normalize_compound(raw, expected):
    assert normalize_compound(raw) == expected


def test_to_float_and_bool():
    assert math.isnan(to_float("None"))
    assert to_float("1.5") == 1.5
    assert to_bool("True") is True
    assert to_bool(0) is False
    assert math.isnan(to_bool("None"))


def test_normalize_text_strips_accents():
    assert normalize_text("São Paulo Grand Prix") == "sao paulo grand prix"
