# Model card — ApexLens lap-pace models (Model A)

_Generated 2026-10-26 18:58 UTC by `scripts/generate_reports.py` from `evaluation_runs/20261026T182248Z.json`, `models/*/metadata.json`. Do not edit by hand; re-run the script._

## Intended use

Research and education: estimating a driver's expected representative race-lap pace relative to the session reference under stated conditions, comparing drivers under a common scenario, and explaining which inputs the model relied on. **Not** for betting, safety, team operations, or any claim about causes of performance.

## Target

`rel_pace_pct` = 100 × (lap time / session reference − 1) for representative race and sprint laps, where the session reference is the median clean lap of all drivers in that session. Negative is faster. Seconds shown in the UI are a conversion using the circuit's median reference lap.

## `pre_event` — `lap_pace_pre_event-lightgbm-20261026-aac7e5be95`

* Model: LightGBM (Huber); selected by lowest MAE on development walk-forward folds (holdout season not used for selection).
* Training period: 2022-2025; calibration events: 14.
* Inputs: 27 numeric + 1 categorical (feature-set version `5d1847bbec`).
* Intervals: split-conformal (Mondrian by condition) at level 0.9, separate for dry and wet laps.
* Dataset version: `{"sessions_manifest_sha": "c99299aa68860462", "lap_features_sha": "f7963db59372bdee", "f1db_seasons": 77}`.

| Split | Laps | MAE % | RMSE | R² | Bias | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|
| development (pooled walk-forward) | 45,515 | 0.787 | 1.234 | 0.420 | -0.025 | 86.9% | 2.898 |
| holdout season 2025 | 23,204 | 0.779 | 1.235 | 0.435 | -0.050 | 87.1% | 2.845 |

| Condition (development) | Laps | MAE % | 90% PI coverage |
|---|---|---|---|
| dry | 43,862 | 0.771 | 87.7% |
| wet | 1,653 | 1.216 | 66.8% |

## `pre_race` — `lap_pace_pre_race-lightgbm-20261026-cfc083ad08`

* Model: LightGBM (Huber); selected by lowest MAE on development walk-forward folds (holdout season not used for selection).
* Training period: 2022-2025; calibration events: 14.
* Inputs: 29 numeric + 1 categorical (feature-set version `1d695ba323`).
* Intervals: split-conformal (Mondrian by condition) at level 0.9, separate for dry and wet laps.
* Dataset version: `{"sessions_manifest_sha": "c99299aa68860462", "lap_features_sha": "f7963db59372bdee", "f1db_seasons": 77}`.

| Split | Laps | MAE % | RMSE | R² | Bias | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|
| development (pooled walk-forward) | 45,515 | 0.767 | 1.218 | 0.435 | -0.118 | 87.3% | 2.870 |
| holdout season 2025 | 23,204 | 0.758 | 1.217 | 0.452 | -0.093 | 87.1% | 2.782 |

| Condition (development) | Laps | MAE % | 90% PI coverage |
|---|---|---|---|
| dry | 43,862 | 0.749 | 88.2% |
| wet | 1,653 | 1.252 | 63.5% |

## Known failure modes

* Intervals under-cover nominal 90% (most clearly on wet laps); treat them as optimistic. See `reports/model_comparison.md` and `reports/error_analysis.md`.
* Form features lag in-season car development; a team that upgrades strongly is predicted too slow for several events.
* New circuits, rookies and wet races have little or no history; the API flags these cases as extrapolation.
* `pre_event`: on the holdout season, LightGBM (Huber) is not significantly better than Ridge or Spline GAM; the simpler model would serve almost as well.
* Trained on 2022–2025 ground-effect cars; not valid for the 2026 regulations.

## Ethical and legal notes

Timing data is unofficial (FastF1 export); F1DB is CC BY 4.0. Driver comparisons are statistical summaries with uncertainty, not judgements of people. ApexLens is not associated with Formula 1, the FIA or any team.

