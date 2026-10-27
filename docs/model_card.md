# Model card — ApexLens lap-pace models (Model A)

_Generated 2026-10-27 08:10 UTC by `scripts/generate_reports.py` from `evaluation_runs/20261027T075133Z.json`, `models/*/metadata.json`. Do not edit by hand; re-run the script._

## Intended use

Research and education: estimating a driver's expected representative race-lap pace relative to the session reference under stated conditions, comparing drivers under a common scenario, and explaining which inputs the model relied on. **Not** for betting, safety, team operations, or any claim about causes of performance.

## Target

`rel_pace_pct` = 100 × (lap time / session reference − 1) for representative race and sprint laps, where the session reference is the median clean lap of all drivers in that session. Negative is faster. Seconds shown in the UI are a conversion using the circuit's median reference lap.

## `pre_event` — `lap_pace_pre_event-lightgbm-20261027-6f07d7f246`

* Model: LightGBM (Huber); selected by lowest MAE on development walk-forward folds (holdout season not used for selection).
* Training period: 2022-2026; calibration events: 16.
* Inputs: 27 numeric + 1 categorical (feature-set version `5d1847bbec`).
* Intervals: split-conformal (Mondrian by condition) at level 0.9, separate for dry and wet laps.
* Dataset version: `{"sessions_manifest_sha": "565045d5ae37a4f5", "lap_features_sha": "5c799359d1af068f", "f1db_seasons": 77}`.

| Split | Laps | MAE % | RMSE | R² | Bias | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|
| development (pooled walk-forward) | 68,719 | 0.780 | 1.232 | 0.428 | -0.033 | 86.7% | 2.832 |
| holdout season 2026 | 18,219 | 0.894 | 1.306 | 0.490 | -0.209 | 85.0% | 3.146 |

| Condition (development) | Laps | MAE % | 90% PI coverage |
|---|---|---|---|
| dry | 66,148 | 0.762 | 87.4% |
| wet | 2,571 | 1.244 | 68.6% |

## `pre_race` — `lap_pace_pre_race-lightgbm-20261027-7befafcc5b`

* Model: LightGBM (Huber); selected by lowest MAE on development walk-forward folds (holdout season not used for selection).
* Training period: 2022-2026; calibration events: 16.
* Inputs: 29 numeric + 1 categorical (feature-set version `1d695ba323`).
* Intervals: split-conformal (Mondrian by condition) at level 0.9, separate for dry and wet laps.
* Dataset version: `{"sessions_manifest_sha": "565045d5ae37a4f5", "lap_features_sha": "5c799359d1af068f", "f1db_seasons": 77}`.

| Split | Laps | MAE % | RMSE | R² | Bias | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|
| development (pooled walk-forward) | 68,719 | 0.763 | 1.215 | 0.443 | -0.109 | 86.7% | 2.790 |
| holdout season 2026 | 18,219 | 0.861 | 1.254 | 0.530 | -0.126 | 85.1% | 3.033 |

| Condition (development) | Laps | MAE % | 90% PI coverage |
|---|---|---|---|
| dry | 66,148 | 0.743 | 87.5% |
| wet | 2,571 | 1.268 | 66.7% |

## Known failure modes

* Intervals under-cover nominal 90% (most clearly on wet laps); treat them as optimistic. See `reports/model_comparison.md` and `reports/error_analysis.md`.
* Form features lag in-season car development; a team that upgrades strongly is predicted too slow for several events.
* New circuits, rookies and wet races have little or no history; the API flags these cases as extrapolation.
* `pre_event`: on the holdout season, LightGBM (Huber) is not significantly better than Team-adjusted form baseline or Ridge or Spline GAM; the simpler model would serve almost as well.
* `pre_race`: on the holdout season, LightGBM (Huber) is not significantly better than Team-adjusted form baseline or Ridge; the simpler model would serve almost as well.
* The 2026 season introduced new technical regulations. 2026 races are included as they happen, but most training laps come from 2022–2025 cars; compare the 2026 fold with earlier ones before relying on 2026 predictions.

## Ethical and legal notes

Timing data is unofficial (FastF1 export); F1DB is CC BY 4.0. Driver comparisons are statistical summaries with uncertainty, not judgements of people. ApexLens is not associated with Formula 1, the FIA or any team.

