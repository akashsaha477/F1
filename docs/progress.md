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

## Phase 4 — track geometry and corner analysis
- [x] Reference path per qualifying session from the fastest telemetry lap: uniform 2 m resampling, Savitzky–Golay smoothing, heading and curvature (`track_geometry/geometry.py`)
- [x] Lap alignment by guided projection (nearest point within ±150 m of the lap's own integrated distance) — robust to self-crossing circuits; median lateral offset ≈ 0.5 m
- [x] Corner segmentation: FastF1 corner markers (gated: rejected when off the driven path) and an independent curvature method used for validation and as fallback; close markers grouped into complexes; unique corner IDs
- [x] Explicit, adjustable category rules (slow / medium / fast / flat-out; hairpin, chicane, esses, sweeper, sequence flags) — ApexLens conventions, not FIA classifications
- [x] Per-lap corner metrics (segment time, entry/min/exit speed, braking onset and duration from the on/off channel, minimum-speed-to-full-throttle time, gears, dv/dt proxy) with sample-density and plausibility quality flags
- [x] Team-mate corner deltas only for comparable runs (same qualifying segment / within 15 min, lap times within 1.5%)
- [x] Sector boundaries from sector times on the telemetry laps; sector corner composition; circuit profiles feeding Model A and the fingerprint
- [x] Model B (sector pace): driver corner-category profile vs. no profile, walk-forward
- [x] API: `/api/circuits/{id}/layout|corners|performance`, `/api/drivers/{id}/corner-profile`, `/api/corner-analysis`
- [x] Frontend: Track explorer (SVG map with speed shading and two-driver colouring, corner table, corner detail, speed/throttle traces)

Validation and findings (92 qualifying sessions, 2022–2025): marker sets used in 91 sessions (1 rejected as
off-path: 2022 São Paulo); curvature-inferred corners match markers with precision 0.96 / recall 0.85, median
apex error 10 m. Overall team-mate corner deltas are only weakly repeatable (split-half r = 0.24, permutation
p ≈ 0.07); slow-vs-fast corner *specialisation* is not repeatable (r = −0.06, p ≈ 0.63). Adding driver
corner-category profiles to the sector model does not reduce error (ΔMAE −0.002 pp, 95% CI −0.004…+0.0005).
No driver × circuit-type deviation (street, high-speed, slow-corner circuits) is distinguishable from zero.

## Phase 5 — explainability and uncertainty
- [x] Exact TreeSHAP (LightGBM `pred_contrib`) and exact linear contributions; grouped feature contributions
- [x] Global: mean |contribution|, grouped permutation importance on the holdout, ALE curves
- [x] Local: plain-language narrative, counterfactuals (same car, conditions switched), evidence counts, range warnings
- [x] Uncertainty: dry/wet split-conformal intervals, 20-model event-bootstrap ensemble (model spread reported separately)
- [x] Explanation validation (`explainability/validation.py`): additivity, agreement with the `shap` library, stability across bootstrap refits, sensitivity to small perturbations, agreement across horizons and with Ridge, correlated-input pairs
- [x] API: `/api/explain`, `/api/models/{v}/explanation-validation`, `/api/experiments`

## Phase 6 — tyre and weather lab
- [x] Model C (`modeling/tyre_model.py`): fuel-corrected stint slopes (stints >= 14 laps, first 5 laps anchor the level), precision-weighted compound/season/circuit summaries with session-cluster bootstrap intervals, driver degradation deviations with shrinkage, track-temperature association
- [x] Predictive test, walk-forward: flat < compound < compound+circuit; adding driver slopes does not help
- [x] API: `/api/tyres/degradation`, `/api/predict/tyre-degradation` (curve with blended interval)
- [x] Frontend: Tyre & weather lab (compound/season rates, circuit ranking, degradation curve, temperature association)

Findings: compound-specific slopes beat a flat slope (ΔMAE −0.15 pp, 95% CI −0.26…−0.004); circuit-specific
slopes do not significantly improve on compound only (−0.03 pp, CI −0.08…+0.01); driver-specific slopes add
nothing (+0.002 pp). Soft degrades faster than medium and hard in every season; the season-level intervals overlap.

## Phase 7 — full dashboard and remaining models
- [x] Model E (`driver_profiles/clustering.py`): PCA + k-means over 81 driver-seasons with bootstrap ARI. k = 2 is stable (ARI 0.82) but mainly separates pace relative to team-mates (|r| = 0.76); k >= 3 is unstable (ARI <= 0.58). Reported as exploratory, no style labels
- [x] Model F (`modeling/quali_model.py`): pre-event qualifying gap to pole; LightGBM beats the team-form baseline on MAE (−0.15 pp, CI −0.23…−0.09), event Spearman 0.71 vs 0.65, pole hit rate equal (0.44)
- [x] Feature-group ablations (`modeling/ablation.py`), cumulative and leave-one-group-out
- [x] Methodology service (`/api/methodology`) as the single source for cleaning rules, model descriptions, leakage controls and limitations
- [x] Frontend pages: Tyre & weather lab, Race & lap explorer (lap times with exclusion reasons, stints, weather, results, race control), Scenario laboratory, Data & methodology — all nine pages in place
- [x] Frontend tests for the new pages; backend tests for tyre slopes and clustering

## Phase 8 — evaluation and error analysis
- [x] Stored walk-forward predictions now keep lap context (tyre age, lap number, race phase, sprint flag, driver experience, circuit history) for error analysis
- [x] Error analysis (`evaluation/error_analysis.py`): errors, bias, skill vs baseline and interval coverage by condition, compound, session type, tyre age, race phase, driver experience and circuit novelty; group contrasts with event-cluster bootstrap CIs; largest event errors; per-team half-season bias; within-session driver ordering (Spearman)
- [x] Feature-group ablations (cumulative and leave-one-group-out) and explanation validation re-run on the final models
- [x] Data-quality tests: every check fires on its defect (synthetic edits of real fixtures) and invariants of the ingested dataset (unique lap keys, clean/exclusion consistency, reference = median clean lap, target definition, form uses only earlier events)
- [x] Model registry: `is_production` follows the production pointer, so superseded versions are no longer listed as production

Findings (run 20261026T182248Z): retraining reproduces the same versions and metrics. Wet laps are the one
significantly worse group (MAE +0.48 pp vs dry, CI +0.31…+0.70; holdout coverage 74%). Differences by tyre age,
race phase, sprint vs grand prix, driver experience and circuit novelty are not significant. Form features lag
car development: e.g. McLaren 2023 is predicted 0.37% too slow in the second half of the season. Within a
session LightGBM orders drivers with median Spearman 0.81 (pre-event) and 0.86 (pre-race). Ablations: race
context and tyre features carry most of the signal; dropping team features slightly *improves* the 2025
holdout (−0.010 pp, CI −0.017…−0.004), consistent with driver form already containing the car; corner and
driver × circuit features add nothing. Explanations are exact (additivity error 1e-14, identical to the `shap`
library), stable across bootstrap refits (top-3 sign agreement 0.998) and only moderately aligned with Ridge
(Spearman 0.50), as expected with correlated team-form inputs.
