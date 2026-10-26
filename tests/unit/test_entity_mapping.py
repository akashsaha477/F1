import pandas as pd

from apexlens.cleaning.entity_mapping import DriverResolver, match_event

GPS = pd.DataFrame([
    {"grand_prix_id": "mexico", "name": "Mexico", "full_name": "Mexican Grand Prix", "short_name": "Mexican GP"},
    {"grand_prix_id": "sao-paulo", "name": "São Paulo", "full_name": "São Paulo Grand Prix", "short_name": "São Paulo GP"},
    {"grand_prix_id": "great-britain", "name": "Great Britain", "full_name": "British Grand Prix", "short_name": "British GP"},
    {"grand_prix_id": "bahrain", "name": "Bahrain", "full_name": "Bahrain Grand Prix", "short_name": "Bahrain GP"},
])
EVENTS = pd.DataFrame([
    {"event_id": "2024-01", "grand_prix_id": "bahrain"}, {"event_id": "2024-12", "grand_prix_id": "great-britain"},
    {"event_id": "2024-20", "grand_prix_id": "mexico"}, {"event_id": "2024-21", "grand_prix_id": "sao-paulo"},
])


def test_match_event_exact_override_and_accents():
    assert match_event("Bahrain Grand Prix", EVENTS, GPS) == ("2024-01", "full_name")
    assert match_event("Mexico City Grand Prix", EVENTS, GPS) == ("2024-20", "override")
    assert match_event("Sao Paulo Grand Prix", EVENTS, GPS)[0] == "2024-21"
    assert match_event("British Grand Prix", EVENTS, GPS)[0] == "2024-12"
    assert match_event("Atlantis Grand Prix", EVENTS, GPS) == (None, "unresolved")


PARTS = pd.DataFrame([
    {"event_id": "2024-01", "season": 2024, "session_code": "R", "driver_number": 1, "driver_id": "max-verstappen", "constructor_id": "red-bull"},
    {"event_id": "2024-01", "season": 2024, "session_code": "FP1", "driver_number": 38, "driver_id": "oliver-bearman", "constructor_id": "ferrari"},
    {"event_id": "2024-02", "season": 2024, "session_code": "R", "driver_number": 38, "driver_id": "oliver-bearman", "constructor_id": "ferrari"},
    {"event_id": "2024-01", "season": 2024, "session_code": "R", "driver_number": 55, "driver_id": "carlos-sainz-jr", "constructor_id": "ferrari"},
])
DRIVERS = pd.DataFrame([
    {"driver_id": "max-verstappen", "abbreviation": "VER"}, {"driver_id": "oliver-bearman", "abbreviation": "BEA"},
    {"driver_id": "carlos-sainz-jr", "abbreviation": "SAI"},
])


def test_driver_resolution_methods():
    r = DriverResolver(PARTS, DRIVERS)
    assert r.resolve("2024-01", 2024, "R", "1", "VER").method == "session_number"
    assert r.resolve("2024-01", 2024, "Q", "1", "VER").method == "event_number"
    res = r.resolve("2024-03", 2024, "R", "38", "BEA")
    assert (res.driver_id, res.method) == ("oliver-bearman", "season_number_abbr")
    assert r.resolve("2024-01", 2024, "R", "99", "XXX").method == "unresolved"
    by_abbr = r.resolve("2024-01", 2024, "R", None, "SAI")
    assert by_abbr.driver_id == "carlos-sainz-jr" and by_abbr.method == "season_abbr"
