import math

from apexlens.cleaning.results import classify_retirement
from apexlens.data_sources.f1db import F1DBSource, load_yaml_text
from apexlens.ingestion.f1db_ingest import entity_tables, season_tables


def test_yaml_loader_keeps_clock_times_as_strings():
    d = load_yaml_text("time: 15:00\nlaps: 57\nlength: 5.412\ndate: 2024-03-02\n")
    assert d["time"] == "15:00" and d["laps"] == 57 and d["length"] == 5.412
    assert str(d["date"]) == "2024-03-02"


def test_f1db_source_reads_fixture(fixtures_dir):
    src = F1DBSource(local_path=fixtures_dir / "f1db_repo")
    assert src.seasons() == [2024]
    races = src.season_races(2024)
    assert races[0]["slug"] == "01-bahrain"
    assert races[0]["race"]["time"] == "15:00"


def test_season_tables(fixtures_dir):
    src = F1DBSource(local_path=fixtures_dir / "f1db_repo")
    tables = season_tables(2024, src.season_races(2024))
    ev = tables["events"].iloc[0]
    assert ev.event_id == "2024-01" and ev.circuit_id == "bahrain" and ev.era == "ground_effect"
    sessions = tables["sessions"].set_index("session_code")
    assert sessions.loc["R", "start_utc"] == "2024-03-02T15:00:00Z"
    assert sessions.loc["Q", "session_id"] == "2024-01-Q"
    rr = tables["race_results"]
    ver = rr[(rr.driver_id == "max-verstappen") & (rr.session_code == "R")].iloc[0]
    assert ver.position == 1 and ver.time_s == 5504.742 and ver.outcome_category == "finished"
    q = tables["qualifying_results"]
    assert q[q.driver_id == "max-verstappen"].best_s.iloc[0] == 89.179
    pits = tables["pit_stops"]
    assert (pits.duration_s > 0).all()
    parts = tables["session_participants"]
    assert set(parts.session_code) >= {"R", "Q", "FP1"}


def test_entity_tables(fixtures_dir):
    src = F1DBSource(local_path=fixtures_dir / "f1db_repo")
    ents = {k: src.entities(k) for k in ["drivers", "constructors", "circuits", "grands-prix", "countries"]}
    t = entity_tables(ents)
    assert t["drivers"].set_index("driver_id").loc["max-verstappen", "abbreviation"] == "VER"
    assert not math.isnan(t["circuits"].iloc[0].length_km)
    assert "bahrain-1" in set(t["circuit_layouts"].layout_id)


def test_retirement_classification():
    assert classify_retirement("Collision damage", "DNF") == "collision_or_accident"
    assert classify_retirement("Engine", "DNF") == "mechanical_or_reliability"
    assert classify_retirement("Front wing", "DNF") == "damage_unspecified"
    assert classify_retirement("Illegal skid block wear", "DSQ") == "disqualified_or_technical_infringement"
    assert classify_retirement(None, "1") == "finished"
    assert classify_retirement(None, "DNS") == "did_not_start"
    assert classify_retirement("Puncture", "DNF") == "tyre_or_puncture"
    assert classify_retirement("Overheating", "DNF") == "mechanical_or_reliability"
