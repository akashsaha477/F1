# Progress log

Checklist of implemented work, open limitations and next priorities. Updated at the end of each phase.

## Phase 0 — repository and source audit
- [x] Environment audit (Python, Node, packages, network reachability)
- [x] Data-source compatibility matrix ([implementation_plan.md](implementation_plan.md))
- [x] Repository scaffold (`pyproject.toml`, `.gitignore`, `.env.example`)

## Phase 1 — data foundations
- [x] Settings (`APEXLENS_*` env vars), bronze/silver/gold layout, atomic Parquet partitions
- [x] HTTP client: timeouts, exponential backoff + Retry-After, rate limiter, disk cache, 404 negative cache, bounded concurrency
- [x] Provenance registry (`data/manifests/provenance.jsonl`) and source catalogue
- [x] Adapters: F1DB (working), TracingInsights FastF1 archive (working), FastF1 / Jolpica / OpenF1 (implemented, mock-tested; hosts blocked in build sandbox)
- [x] Canonical IDs = F1DB IDs; per-session driver/constructor resolution with audit trail; event-name matching
- [x] Silver tables: drivers, constructors, circuits, circuit_layouts, grands_prix, seasons, events, sessions, session_participants, race_results (with outcome category), qualifying_results, starting_grids, pit_stops, fastest_laps, practice_results, driver/constructor standings, laps (+ validity flags), stints, weather_observations, race_control_events, track_status_events, corner_markers, session_drivers, telemetry_samples, telemetry_laps
- [x] Data-quality checks (fatal vs warning) per partition; fatal partitions excluded downstream
- [x] Coverage report (`reports/coverage_report.md`)
- [x] Real data ingested: F1DB 1950–2026; lap timing for 460 sessions (2022–2025, 248,360 laps); 2,178 fastest-lap qualifying telemetry traces

Commands run: `apexlens ingest-f1db --all-history`, `apexlens ingest-laps --seasons 2022-2025`,
`apexlens ingest-telemetry --seasons 2022-2025 --sessions Q,SQ`, `apexlens coverage`. 58 unit tests pass.
