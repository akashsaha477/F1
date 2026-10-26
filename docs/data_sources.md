# Data sources

ApexLens never synthesises data. Every stored record traces back to one of the providers below through
the provenance registry (`data/manifests/provenance.jsonl`), which logs the provider, dataset, endpoint,
season/event/session, retrieval time, schema version, status, error, content hash and bronze path of each
retrieval. `GET /api/data-coverage` and the *Data & methodology* page expose a summary.

| Provider | Role | Access in this build | Licence / terms |
|---|---|---|---|
| [F1DB](https://github.com/f1db/f1db) | Canonical identities (drivers, constructors, circuits, grands prix), schedules, race/sprint/qualifying/practice results, grids, pit stops, standings, 1950–present | Local git checkout (`APEXLENS_F1DB_LOCAL_PATH`) or automatic sparse clone | CC BY 4.0 — attribution required |
| [TracingInsights archive](https://github.com/TracingInsights) | Per-session FastF1 exports: every lap with sectors, speed traps, tyre compound/age/stint, track status, deletions, per-lap weather; weather series; race-control messages; FastF1 `CircuitInfo` corner markers; per-lap car + position telemetry | `raw.githubusercontent.com` (cached), file discovery via blob-less git listing | Repositories declare MIT; underlying timing data comes from the F1 live-timing service via FastF1 and is unofficial. Non-commercial research use. |
| [FastF1](https://docs.fastf1.dev/) | Same data directly from live timing | Adapter implemented (`data_sources/fastf1_source.py`), mock-tested. `livetiming.formula1.com` is blocked in the build sandbox | MIT library; unofficial data |
| [Jolpica-F1](https://github.com/jolpica/jolpica-f1) | Ergast-compatible results API | Adapter implemented with pagination and a 4 req/s, 500 req/h limiter; mock-tested. Host blocked in the build sandbox | Check provider documentation |
| [OpenF1](https://openf1.org/) | Supplementary (overtakes, stints, intervals) | Adapter implemented, mock-tested. Host blocked in the build sandbox | Unofficial provider; review terms before public/commercial deployment |

## Why the TracingInsights archive

FastF1's backend was unreachable from the environment in which ApexLens was built. The TracingInsights
repositories contain FastF1 outputs serialised to JSON with the original FastF1 column semantics
(`LapTime`, `Sector1Time`, `TyreLife`, `TrackStatus`, `IsAccurate`, …). ApexLens maps them back to FastF1
column names (`cleaning/laps.py:TI_LAP_KEYS`) so both sources share a single normaliser; switching to live
FastF1 only requires the FastF1 adapter.

Known properties of this source, verified during ingestion:

* Position coordinates are in 1/10 m (path length ≈ 10 × integrated distance); ApexLens converts to metres.
* `acc_x/acc_y/acc_z` in telemetry files are computed by the archive author, not measured; stored as
  `*_derived` and not used as measurements.
* `brake` is binary (on/off). There is no brake pressure, steering angle or tyre temperature.
* One 2023 session (Hungarian GP FP1) contains 130 laps without a driver number; the quality gate marks
  the session as failed and it is excluded from modelling.

## Identity mapping

Canonical identifiers are F1DB IDs. Lap-level rows are resolved per session from (event, session, car
number) against F1DB's entry lists, with abbreviation cross-checks and explicit fallbacks
(`cleaning/entity_mapping.py`). Event names are matched to F1DB grands prix by full name, an explicit
override table (e.g. "Mexico City Grand Prix" → `mexico`) and a token-overlap fallback. Every resolution
method is stored in `data/manifests/identity_mapping/` and summarised in the coverage report.

## Bounded downloads

* `apexlens ingest-laps --seasons 2024 --max-events 3` — small initial dataset (≈15 sessions).
* `apexlens ingest-telemetry` — by default each driver's fastest clean lap in each qualifying/sprint
  qualifying session only (`--laps-per-driver` to increase). Race telemetry is never downloaded by default.
* All HTTP requests go through `data_sources/http.py`: timeouts, retries with exponential backoff and
  `Retry-After`, client-side rate limiting, bounded concurrency, and an on-disk cache so identical
  requests are never repeated.
