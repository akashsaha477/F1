# Architecture

ApexLens is a batch data and modelling pipeline with a read-mostly API and a single-page dashboard.
Everything the API serves is computed ahead of time by scripts, except predictions and explanations,
which are computed per request from the trained, versioned models.

```
 providers                bronze (raw)          silver (clean)            gold (features)             models
 ─────────                ────────────          ──────────────            ───────────────             ──────
 F1DB (git) ───────────▶ data/raw/f1db ───▶ events, sessions, results ─┐
 TracingInsights (HTTP) ▶ data/raw/ti   ───▶ laps, stints, weather,    ├─▶ all_laps_relative ─────▶ lap_pace_* (A)
 FastF1 / Jolpica /                          race control, telemetry  │   lap_features             sector model (B)
 OpenF1 (adapters)                           corner markers           │   driver_event_form        tyre model (C)
                                                                      │   corner_* / track_maps    quali model (F)
           provenance.jsonl, sessions_ingested.json, quality/*.json   │   driver_profiles (+meta)  clusters (E)
                                                                      └─▶ tyre_* / circuit_profiles
                                                                                      │
                               FastAPI (src/apexlens/api) ◀── services (data, profiles, tracks, tyres, predictions)
                                          │
                               React dashboard (frontend/)  ·  reports/ (scripts/generate_reports.py)
```

## Layers

| Layer | Location | Format | Written by |
|---|---|---|---|
| Cache | `data/cache/` | HTTP responses keyed by URL hash (incl. 404 negative cache) | `data_sources/http.py` |
| Bronze | `data/raw/` | Provider payloads as retrieved | `ingestion/*` |
| Silver | `data/processed/<table>/<partition>.parquet` | Typed, canonical IDs, one partition per season or session | `ingestion/*`, `cleaning/*` |
| Gold | `data/features/<table>/` | Analysis tables and model features (+ `meta.json` where needed) | `features/*`, `driver_profiles/*`, `modeling/tyre_model.py` |
| Models | `data/models/<version>/` | `model.joblib`, `metadata.json`, `ensemble.joblib`, explanation files | `modeling/train_pipeline.py` |
| Evaluation | `data/models/evaluation_runs/`, `data/models/evaluation/` | Run summaries (JSON), stored walk-forward predictions (Parquet) | training and `scripts/evaluate_models.py` |
| Manifests | `data/manifests/` | Provenance registry (JSONL), ingestion manifest, quality reports, identity mapping, coverage | ingestion |

Partitions are written atomically (temp file + rename) and re-running a step overwrites its partitions,
so every step is idempotent. DuckDB (`storage/duckdb_store.py`) exposes the Parquet tables as views for
ad-hoc SQL.

## Packages (`src/apexlens/`)

| Package | Responsibility |
|---|---|
| `config` | Settings from environment (`APEXLENS_*`, `.env`), regulation eras |
| `data_sources` | One adapter per provider; HTTP client with caching, retries, backoff, `Retry-After`, rate limiting and bounded concurrency; source catalogue and provenance registry |
| `ingestion` | Orchestration: F1DB entities and results, lap timing per session, telemetry selection, coverage report, CLI |
| `cleaning` | Parsing of provider formats, canonical entity mapping, lap normalisation and flags, retirement classification, data-quality checks |
| `features` | Feature registry, lap features with leakage-safe form, form state for scenarios, corner metrics and circuit profiles |
| `track_geometry` | Reference paths, curvature, guided projection, corner detection and classification |
| `driver_profiles` | Two-stage driver fingerprint (session adjustment + crossed random effects), condition effects, clustering |
| `modeling` | Model portfolio, walk-forward training, conformal intervals, bootstrap ensemble, registry, Models B/C/F, ablations |
| `evaluation` | Metrics with event-cluster bootstrap, temporal splits, error analysis |
| `explainability` | Global (SHAP, permutation, ALE), local narratives and counterfactuals, explanation validation |
| `predictions` | Scenario construction from historical form, prediction payloads, comparisons |
| `services` | Read models for the API (catalogue, sessions, profiles, tracks, tyres, methodology) |
| `schemas` | Pydantic request models |
| `api` | FastAPI app, routes, dependency wiring, structured errors |
| `reporting` | Report and generated-doc builders |

## Request path

`POST /api/predict/lap-time` → `PredictionService.build_row` reconstructs the feature row exactly as the
training pipeline would have seen it before the chosen event (form as of that date, circuit history,
scenario conditions) → production model for the horizon → conformal interval for the condition group →
bootstrap-ensemble spread → exact TreeSHAP contributions → evidence counts, extrapolation flags and a
plain-language narrative. Nothing in the request path retrains or reads future data.

## Frontend (`frontend/`)

React 18 + TypeScript + Vite + Tailwind, TanStack Query for data fetching, ECharts for charts and SVG for
the track map. Nine pages (`src/pages/`) share typed API hooks (`src/api/hooks.ts`) and a small set of
chart components (`src/charts/`). The dev server and the production nginx container proxy `/api` to the
backend.

## Reproducibility

* Dataset version = hashes of the ingestion manifest and gold lap features, recorded with every model.
* Model versions are content-addressed (`<task>-<model>-<date>-<config hash>`); the production pointer
  lives in `data/models/production.json`.
* Seeds are fixed; retraining on the same data reproduces the same versions and metrics.
* Reports and generated docs are rebuilt from stored outputs by `scripts/generate_reports.py`.
