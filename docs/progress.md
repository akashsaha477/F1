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

## Phase 2 — first vertical slice
- [x] Gold tables: `lap_features`, `driver_session_summary`, `driver_event_form`, `all_laps_relative`
- [x] Leakage-safe pre-event form features (shifted EWMA), verified by tests that perturb future events
- [x] Model A portfolio: historical group median, team-adjusted baseline, Ridge, spline GAM, LightGBM (Huber)
- [x] Walk-forward evaluation by season (2023, 2024 development folds; 2025 untouched holdout), event-held-out folds, cluster-bootstrap CIs, paired comparisons
- [x] Mondrian split-conformal intervals; event-bootstrap ensemble for model uncertainty
- [x] Versioned artifacts + experiment records (`data/models/`), production pointer
- [x] Local explanations (exact TreeSHAP / linear contributions), counterfactual scenarios, deterministic narratives
- [x] FastAPI backend (catalog, sessions, drivers, predictions, models, evaluation) with structured errors
- [x] React frontend: Overview, Driver explorer, Explain a prediction

Measured (lap pace, MAE in % of session reference lap, 2025 holdout): LightGBM 0.779 (pre-event) / 0.756
(pre-race); team-adjusted baseline 0.855; historical median 0.938; Ridge 0.811; spline GAM 0.801. Pre-event
LightGBM is significantly better than both baselines but not significantly better than Ridge/GAM on the
holdout. 90% conformal intervals cover 87% overall and only ~74% of wet laps (under-coverage reported).
Driver × circuit history adds no measurable accuracy (grouped permutation importance ≈ 0).

## Phase 3 — driver performance fingerprint
- [x] Stage 1 (`driver_profiles/session_adjust.py`): per-session OLS separating driver pace from compound, compound-specific tyre age and lap number; non-identifiable terms dropped in a fixed, recorded order; AR(1)-inflated standard errors
- [x] Stage 2 (`driver_profiles/mixed_model.py`): crossed random effects (driver, driver-season, team-season) with session fixed effects, REML via Henderson's equations; validated against statsmodels and on simulated data
- [x] Fingerprint per driver-season: team-adjusted race pace and qualifying (90% posterior intervals, within-season percentiles), team-mate gaps with bootstrap CIs, lap-to-lap consistency, lap-1 and grid-to-finish position changes, outcome categories (separate from pace)
- [x] Condition-specific deviations with empirical-Bayes shrinkage and evidence thresholds: wet races, wet qualifying (per-session regression residuals), street circuits
- [x] API: `/api/drivers/{id}/profile`, `/api/driver-effects?season=`, `/api/drivers/compare`
- [x] Frontend: fingerprint card, season effects chart on the overview, driver comparison page (profiles, head-to-head, condition evidence, model-based scenario comparison)

Findings (2022–2025): race-pace variance components — driver 0.104, driver-season 0.005, team-season 0.205,
residual 0.110 (%²). Once dry pace and car are accounted for, no driver's wet-race, wet-qualifying or
street-circuit deviation is distinguishable from zero (estimated between-driver variance ≈ 0 for street and wet
qualifying, τ ≈ 0.14% for wet races); the application reports these as such instead of ranking drivers.
