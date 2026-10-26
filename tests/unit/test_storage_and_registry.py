import pandas as pd

from apexlens.data_sources.registry import ProvenanceRecord, ProvenanceRegistry
from apexlens.storage.io import read_partition, read_table, write_partition


def test_write_partition_is_idempotent(tmp_path):
    df = pd.DataFrame({"a": [1, 2], "b": ["x", "y"]})
    write_partition(tmp_path / "t", "s1", df)
    write_partition(tmp_path / "t", "s1", df)
    write_partition(tmp_path / "t", "s2", df.assign(a=[3, 4]))
    out = read_table(tmp_path / "t")
    assert len(out) == 4
    assert sorted(out["a"]) == [1, 2, 3, 4]
    assert len(read_partition(tmp_path / "t", "s2")) == 2
    assert not list((tmp_path / "t").glob(".*tmp"))


def test_mixed_object_column_is_stored_as_string(tmp_path):
    df = pd.DataFrame({"grid": [1, "PL", None]})
    write_partition(tmp_path / "t", "k", df)
    out = read_table(tmp_path / "t")
    assert out["grid"].tolist()[:2] == ["1", "PL"]


def test_registry_records_and_summarises(tmp_path):
    reg = ProvenanceRegistry(tmp_path)
    reg.record(ProvenanceRecord(provider="f1db", dataset="season_races", endpoint="u1", season=2024, n_bytes=10))
    reg.record(ProvenanceRecord(provider="f1db", dataset="season_races", endpoint="u2", season=2023, n_bytes=5))
    reg.record(ProvenanceRecord(provider="tracinginsights", dataset="weather", endpoint="u3", season=2024,
                                status="missing"))
    summary = {(s["provider"], s["dataset"]): s for s in reg.summary()}
    assert summary[("f1db", "season_races")]["seasons"] == [2023, 2024]
    assert summary[("f1db", "season_races")]["bytes"] == 15
    assert summary[("tracinginsights", "weather")]["n_missing"] == 1
    assert summary[("f1db", "season_races")]["licence"].startswith("CC BY")
