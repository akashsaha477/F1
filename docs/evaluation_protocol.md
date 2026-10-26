# Evaluation protocol

How every reported number is produced, and how to reproduce it.

## Principles

1. **Temporal validation first.** Models are trained only on seasons before the one they are tested on
   (walk-forward by season). Random lap-level splits are never used: laps of one race share the car,
   track, weather and strategy and would leak.
2. **One holdout, used once.** The final season (2025) is reported but never used for selection or
   tuning. Development folds are 2023 (train 2022) and 2024 (train 2022–2023).
3. **Uncertainty on every comparison.** Metrics come with 95% intervals from an event-cluster
   bootstrap (whole events resampled, 200–300 replicates). Model differences are *paired* on
   identical laps; a difference is called significant only when its interval excludes zero.
4. **Baselines are reported next to every model.** A complex model must beat the team-adjusted form
   baseline and the simpler models to be worth its complexity.
5. **Leakage checks are tests.** `split.check_temporal` raises if training data reaches the test period;
   `tests/modeling/test_leakage.py` perturbs future events and asserts that earlier features do not change.

## Splits

| Split | Train | Calibration | Test | Used for |
|---|---|---|---|---|
| `walk_forward_2023` | 2022, first 80% of events | last 20% of 2022 events | 2023 | development |
| `walk_forward_2024` | 2022–2023, first 80% of events | last 20% of those events | 2024 | development |
| `walk_forward_2025` | 2022–2024, first 80% of events | last 20% of those events | 2025 | holdout |
| `event_group_kfold_5` | 4/5 of events | inside train | 1/5 of events | secondary: how much does time order matter |

The calibration events are the most recent ones before the test season so that conformal intervals are
calibrated on the conditions closest to the test period. The production model is refitted on all
seasons with the most recent 15% of events held out for calibration.

## Metrics

* Lap pace: MAE (primary, % of the reference lap and seconds), RMSE, R², bias, 90% interval coverage and
  mean width, by condition (dry/wet).
* Within-session ordering: Spearman correlation between predicted and actual mean driver pace per session.
* Qualifying (Model F): MAE of the gap to pole, mean per-event Spearman, pole hit rate, top-3 overlap.
* Tyre degradation (Model C): MAE of lap-time predictions inside held-out stints.
* Clusters (Model E): silhouette and bootstrap adjusted Rand index (stability).
* Explanations: see `docs/methodology.md` §7.

## Experiments

| Experiment | Code | Output |
|---|---|---|
| Model A portfolio, both horizons | `modeling/train_pipeline.py` | `evaluation_runs/<run_id>.json`, stored predictions |
| Horizon gain (pre-race vs pre-event) | `train_pipeline.horizon_gain` | same run file |
| Feature-group ablations (cumulative and leave-one-out) | `modeling/ablation.py` | `evaluation_runs/ablations.json` |
| Corner profiles in the sector model (B) and specialisation reliability | `train_pipeline.run_corner_experiments` | `evaluation_runs/corner_experiments.json` |
| Tyre degradation (C) | `modeling/tyre_model.py` | `evaluation_runs/tyre_degradation.json` |
| Qualifying gap (F) | `modeling/quali_model.py` | `evaluation_runs/quali_model.json` |
| Explanation validation | `explainability/validation.py` | `models/<version>/explanation_validation.json` |
| Error analysis | `evaluation/error_analysis.py` | `evaluation_runs/error_analysis_<horizon>.json` |

## Reproducing

```bash
make ingest          # F1DB + lap timing for 2022–2025 + qualifying telemetry (cached HTTP)
make features        # corner tables, lap features, profiles, tyre tables, clusters
make train           # Model A, both horizons; writes a new run id and production pointers
make evaluate        # explanation validation, ablations, Models B/F, error analysis
make reports         # reports/*.md, docs/data_dictionary.md, docs/feature_definitions.md, docs/model_card.md
```

Seeds are fixed. Re-running `make train` on unchanged data reproduces the same model versions and
metrics; the run id (a timestamp) is the only difference.

## Adding an experiment

1. Put the computation in a function under `src/apexlens/` that reads gold tables through `DataPaths`
   and writes one JSON file to `data/models/evaluation_runs/`.
2. Use `evaluation.splits.walk_forward_by_season` and `evaluation.metrics.paired_mae_difference` (or
   `cluster_bootstrap`) so the protocol above holds.
3. Register it as a step in `scripts/evaluate_models.py` and add a section to
   `reporting/reports.py` that reads the JSON — never type results into a report.
