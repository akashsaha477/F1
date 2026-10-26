# ApexLens implementation plan and source audit (Phase 0)

## Environment audit (2026-10-26)

| Item | Finding |
|---|---|
| Repository | Empty (no commits). Everything is built from scratch. |
| OS / CPU / RAM | Linux x86_64, 4 cores, 15 GB RAM, ~30 GB free disk |
| Python | 3.13 (project supports >= 3.11), venv managed with `uv` |
| Node | 22.x, npm 10.x |
| Key Python libs | pandas 2.3, numpy 2.x, duckdb, pyarrow, scikit-learn 1.9, LightGBM 4.7, SHAP 0.54, statsmodels 0.15, FastAPI, FastF1 3.9 |

### Network reachability from the build environment

The build sandbox runs behind an egress policy. Measured on 2026-10-26:

| Host | Purpose | Reachable |
|---|---|---|
| `livetiming.formula1.com` | FastF1 timing/telemetry backend | **No** (HTTP 403 at proxy) |
| `api.jolpi.ca` | Jolpica-F1 (Ergast-compatible) API | **No** |
| `api.openf1.org` | OpenF1 API | **No** |
| `docs.fastf1.dev` | FastF1 documentation | **No** |
| `pypi.org`, `registry.npmjs.org` | Packages | Yes |
| `raw.githubusercontent.com` + anonymous git | Public GitHub repositories | Yes |

Consequence: the FastF1, Jolpica and OpenF1 adapters are implemented against their documented
interfaces and unit-tested with mocked responses, but they could not be exercised live here.
Real data for this build comes from two public GitHub-hosted sources (below). Nothing is synthesised.

## Data-source compatibility matrix

| Capability | F1DB (git / raw GitHub) | TracingInsights archive (FastF1 export on GitHub) | FastF1 (live) | Jolpica-F1 | OpenF1 |
|---|---|---|---|---|---|
| Licence / terms | CC BY 4.0 (verified in repository `LICENSE`) | MIT (verified in repository `LICENSE`); timing data originates from F1 live timing via FastF1 and is unofficial | MIT library; F1 timing data is unofficial | Ergast-compatible API with documented rate limits; terms could not be re-read from this environment | Unofficial provider; terms could not be re-read from this environment — review before public/commercial use |
| Seasons | 1950 – present | 2018 – present (one repository per season) | 2018 – present (telemetry) | 1950 – present | 2023 – present |
| Drivers, constructors, circuits | Yes (rich metadata) | Session-scoped abbreviations/teams only | Session-scoped | Yes | Session-scoped |
| Schedule / sessions | Yes (dates/times per session) | Implicit (directory layout) | Yes | Yes | Yes |
| Race, qualifying, grid, standings | Yes | No | Results only | Yes | Partial |
| Pit stops | Yes (stop lap and duration) | Via pit-in / pit-out times | Yes | Yes | Yes |
| Lap and sector timing | No (fastest laps only) | **Yes** (every lap, sectors, speed traps) | Yes | Lap times only | Yes |
| Tyre compound / age / stint | No | **Yes** | Yes | No | Yes (stints) |
| Track status per lap | No | **Yes** (TrackStatus code string per lap) | Yes | No | Via race control |
| Weather | No | **Yes** (session series + joined per lap) | Yes | No | Yes |
| Race-control messages | No | **Yes** | Yes | No | Yes |
| Car telemetry (speed, throttle, brake, gear, RPM, DRS) | No | **Yes** (per-lap files) | Yes | No | Yes |
| Position (X/Y/Z) | No | **Yes** (merged into telemetry) | Yes | No | Yes |
| Corner markers | No | **Yes** (`corners.json` = FastF1 `CircuitInfo`) | Yes | No | No |
| Overtakes | No | No | No | No | Yes (2024+) |
| Reachable in this build | **Yes** | **Yes** | No | No | No |

## Architecture decisions

* **Storage:** Parquet files in a bronze/silver/gold layout; DuckDB as an in-process query engine
  over Parquet (no database server needed). JSON files for manifests, provenance and model metadata.
* **Backend:** FastAPI + Pydantic, read-only access to gold tables and model artifacts.
* **Frontend:** React + TypeScript + Vite + Tailwind CSS, ECharts for charts, TanStack Query.
* **Canonical identity:** F1DB identifiers (`max-verstappen`, `red-bull`, `bahrain`) are the canonical
  driver / constructor / circuit IDs. Lap-level sources are mapped per session via
  (season, round, car number) with abbreviation cross-checks, never by name alone.
* **Default bounded dataset:** seasons 2022–2025 (one regulation era), all sessions' lap timing,
  and qualifying fastest-lap telemetry. Full race telemetry is never downloaded by default.

## Phases

0. Audit and scaffold (this document).
1. Data foundations: HTTP client with retries/backoff/rate-limit/cache, source adapters, provenance
   registry, idempotent bronze ingestion, silver normalisation, entity mapping, validation, coverage report.
2. Vertical slice: lap-level gold features, baselines + Ridge + LightGBM for relative clean-lap pace,
   walk-forward evaluation, SHAP explanation, API, frontend.
3. Driver fingerprint: team-season-adjusted driver effects via a crossed random-effects model,
   consistency, teammate gaps, tyre sensitivity, wet-weather deviations with shrinkage.
4. Track geometry and corners: telemetry alignment to a reference path, curvature segmentation
   validated against FastF1 markers, corner classes, driver-by-corner metrics.
5. Explainability and uncertainty: conformal intervals, global/local explanation, counterfactuals,
   explanation stability tests.
6. Tyre and weather laboratory: fuel-corrected degradation model, wet-weather module.
7. Full dashboard (9 pages).
8. Ablations, error analysis, generated reports.
9. Documentation, Docker, CI.

Progress against these phases is tracked in [`progress.md`](progress.md).
