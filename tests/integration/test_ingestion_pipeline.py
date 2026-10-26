from apexlens.ingestion.laps_ingest import ingest_lap_timing
from apexlens.storage.io import read_partition, read_table


def test_pipeline_writes_bronze_silver_and_provenance(ingested):
    ctx, statuses = ingested
    assert [s["session_id"] for s in statuses] == ["2024-01-R"]
    st = statuses[0]
    assert st["quality_status"] in ("ok", "warning") and st["n_laps"] == 24 and st["n_unresolved_laps"] == 0
    laps = read_partition(ctx.paths.silver("laps"), "2024-01-R")
    assert set(laps["driver_id"]) == {"max-verstappen", "sergio-perez", "charles-leclerc"}
    assert set(laps["constructor_id"]) == {"red-bull", "ferrari"}
    assert (ctx.paths.raw / "tracinginsights" / "2024" / "2024-01" / "R" / "session_laptimes.json").exists()
    prov = ctx.registry.load()
    by_ds = prov.groupby("dataset")["status"].first().to_dict()
    assert by_ds["session_laptimes"] == "ok" and by_ds["drivers"] == "missing"
    assert len(read_table(ctx.paths.silver("weather_observations"))) == 20
    assert len(read_table(ctx.paths.silver("corner_markers"))) == 15
    assert (ctx.paths.manifests / "quality" / "2024-01-R.json").exists()


def test_rerun_is_idempotent(ingested):
    ctx, _ = ingested
    before = read_table(ctx.paths.silver("laps"))
    ingest_lap_timing(ctx, 2024, codes=("R",))
    after = read_table(ctx.paths.silver("laps"))
    assert len(before) == len(after)
    assert not after.duplicated(["session_id", "driver_number", "lap_number"]).any()


def test_failed_download_keeps_previous_data(ingested, provider):
    ctx, _ = ingested
    provider.fail["session_laptimes.json"] = 503
    statuses = ingest_lap_timing(ctx, 2024, codes=("R",))
    assert statuses[0]["quality_status"] == "missing"
    assert len(read_partition(ctx.paths.silver("laps"), "2024-01-R")) == 24
    errors = ctx.registry.load()
    assert (errors["status"] == "error").any()


def test_f1db_tables(ingested):
    ctx, _ = ingested
    ev = read_table(ctx.paths.silver("events"))
    assert ev["event_id"].tolist() == ["2024-01"]
    rr = read_table(ctx.paths.silver("race_results"))
    assert rr[rr.position == 1]["driver_id"].iloc[0] == "max-verstappen"


def test_coverage_report(ingested):
    ctx, _ = ingested
    from apexlens.storage.io import read_json

    rep = read_json(ctx.paths.manifests / "coverage_report.json")
    assert rep["summary"]["sessions_with_timing"] == 1
    assert rep["per_season"][0]["laps"] == 24
    assert (ctx.paths.root.parent / "reports" / "coverage_report.md").exists()
