# Model comparison

_Generated 2026-10-26 18:57 UTC by `scripts/generate_reports.py` from `evaluation_runs/20261026T182248Z.json`, `evaluation_runs/*.json`. Do not edit by hand; re-run the script._

Run `20261026T182248Z`; dataset version `{"sessions_manifest_sha": "c99299aa68860462", "lap_features_sha": "f7963db59372bdee", "f1db_seasons": 77}`; seed 42.

Protocol: walk-forward by season (train on all earlier seasons, calibrate conformal intervals on the most recent training events, test on the next season). The last season is a holdout reported once; model selection uses development folds only. Intervals are 95% event-cluster bootstrap; `*` marks an interval that excludes zero.

## Model A — lap pace, `pre_event`

| Test season | Model | Laps | MAE % | 95% CI | RMSE | R² | 90% PI coverage | PI width | MAE s |
|---|---|---|---|---|---|---|---|---|---|
| 2023 | Historical group median | 21,125 | 0.928 | [0.867, 0.988] | 1.250 | 0.235 | 85.6% | 3.327 | 0.820 |
| 2023 | Team-adjusted form baseline | 21,125 | 0.819 | [0.743, 0.892] | 1.162 | 0.339 | 87.8% | 3.203 | 0.722 |
| 2023 | Ridge | 21,125 | 0.927 | [0.863, 1.006] | 1.243 | 0.243 | 86.3% | 3.371 | 0.822 |
| 2023 | Spline GAM | 21,125 | 0.843 | [0.774, 0.938] | 1.155 | 0.347 | 86.7% | 3.158 | 0.745 |
| 2023 | LightGBM (Huber) | 21,125 | 0.757 | [0.673, 0.857] | 1.088 | 0.421 | 87.7% | 2.957 | 0.664 |
| 2024 | Historical group median | 24,390 | 0.947 | [0.810, 1.194] | 1.461 | 0.318 | 87.4% | 3.432 | 0.831 |
| 2024 | Team-adjusted form baseline | 24,390 | 0.884 | [0.727, 1.141] | 1.415 | 0.359 | 89.8% | 3.545 | 0.775 |
| 2024 | Ridge | 24,390 | 0.844 | [0.699, 1.090] | 1.349 | 0.418 | 87.1% | 3.082 | 0.739 |
| 2024 | Spline GAM | 24,390 | 0.832 | [0.671, 1.092] | 1.350 | 0.417 | 87.0% | 3.014 | 0.728 |
| 2024 | LightGBM (Huber) | 24,390 | 0.813 | [0.665, 1.080] | 1.349 | 0.419 | 86.3% | 2.848 | 0.712 |
| 2025 | Historical group median | 23,204 | 0.938 | [0.812, 1.127] | 1.388 | 0.287 | 85.6% | 3.297 | 0.826 |
| 2025 | Team-adjusted form baseline | 23,204 | 0.855 | [0.729, 1.030] | 1.306 | 0.368 | 87.3% | 3.178 | 0.752 |
| 2025 | Ridge | 23,204 | 0.811 | [0.673, 0.990] | 1.263 | 0.409 | 87.0% | 3.006 | 0.714 |
| 2025 | Spline GAM | 23,204 | 0.801 | [0.666, 0.976] | 1.253 | 0.419 | 87.4% | 2.997 | 0.706 |
| 2025 | LightGBM (Huber) | 23,204 | 0.779 | [0.645, 0.962] | 1.235 | 0.435 | 87.1% | 2.845 | 0.685 |

![MAE by fold and model](figures/models_pre_event_folds.png)

### Paired comparisons (MAE difference, % points)

| Split | MAE(a) − MAE(b) | Estimate [95% CI] |
|---|---|---|
| development | lightgbm − hist_group_median | -0.151 [-0.176, -0.125] * |
| development | lightgbm − team_adjusted_form | -0.067 [-0.094, -0.041] * |
| development | lightgbm − ridge | -0.095 [-0.140, -0.056] * |
| development | lightgbm − spline_gam | -0.050 [-0.085, -0.013] * |
| holdout | lightgbm − hist_group_median | -0.159 [-0.188, -0.126] * |
| holdout | lightgbm − team_adjusted_form | -0.076 [-0.105, -0.041] * |
| holdout | lightgbm − ridge | -0.032 [-0.067, +0.006] |
| holdout | lightgbm − spline_gam | -0.022 [-0.062, +0.014] |

Selected: **LightGBM (Huber)** — lowest MAE on development walk-forward folds (holdout season not used for selection).

Secondary split — event-held-out 5-fold (not temporal; shows how much the temporal split matters):

| Model | MAE % | 90% PI coverage |
|---|---|---|
| Ridge | 0.809 | 88.6% |
| LightGBM (Huber) | 0.783 | 88.8% |


## Model A — lap pace, `pre_race`

| Test season | Model | Laps | MAE % | 95% CI | RMSE | R² | 90% PI coverage | PI width | MAE s |
|---|---|---|---|---|---|---|---|---|---|
| 2023 | Historical group median | 21,125 | 0.928 | [0.867, 0.988] | 1.250 | 0.235 | 85.6% | 3.327 | 0.820 |
| 2023 | Team-adjusted form baseline | 21,125 | 0.819 | [0.743, 0.892] | 1.162 | 0.339 | 87.8% | 3.203 | 0.722 |
| 2023 | Ridge | 21,125 | 0.935 | [0.875, 1.009] | 1.250 | 0.235 | 86.3% | 3.385 | 0.828 |
| 2023 | Spline GAM | 21,125 | 0.850 | [0.786, 0.947] | 1.163 | 0.338 | 86.9% | 3.203 | 0.751 |
| 2023 | LightGBM (Huber) | 21,125 | 0.740 | [0.654, 0.831] | 1.073 | 0.436 | 88.1% | 2.935 | 0.648 |
| 2024 | Historical group median | 24,390 | 0.947 | [0.810, 1.194] | 1.461 | 0.318 | 87.4% | 3.432 | 0.831 |
| 2024 | Team-adjusted form baseline | 24,390 | 0.884 | [0.727, 1.141] | 1.415 | 0.359 | 89.8% | 3.545 | 0.775 |
| 2024 | Ridge | 24,390 | 0.843 | [0.695, 1.091] | 1.348 | 0.419 | 86.9% | 3.060 | 0.738 |
| 2024 | Spline GAM | 24,390 | 0.831 | [0.667, 1.086] | 1.350 | 0.418 | 86.8% | 2.992 | 0.726 |
| 2024 | LightGBM (Huber) | 24,390 | 0.790 | [0.635, 1.056] | 1.330 | 0.434 | 86.6% | 2.813 | 0.691 |
| 2025 | Historical group median | 23,204 | 0.938 | [0.812, 1.127] | 1.388 | 0.287 | 85.6% | 3.297 | 0.826 |
| 2025 | Team-adjusted form baseline | 23,204 | 0.855 | [0.729, 1.030] | 1.306 | 0.368 | 87.3% | 3.178 | 0.752 |
| 2025 | Ridge | 23,204 | 0.809 | [0.669, 0.988] | 1.261 | 0.412 | 87.0% | 3.008 | 0.712 |
| 2025 | Spline GAM | 23,204 | 0.799 | [0.666, 0.975] | 1.250 | 0.421 | 87.6% | 3.018 | 0.704 |
| 2025 | LightGBM (Huber) | 23,204 | 0.758 | [0.626, 0.937] | 1.217 | 0.452 | 87.1% | 2.782 | 0.667 |

![MAE by fold and model](figures/models_pre_race_folds.png)

### Paired comparisons (MAE difference, % points)

| Split | MAE(a) − MAE(b) | Estimate [95% CI] |
|---|---|---|
| development | lightgbm − hist_group_median | -0.171 [-0.197, -0.144] * |
| development | lightgbm − team_adjusted_form | -0.087 [-0.113, -0.061] * |
| development | lightgbm − ridge | -0.119 [-0.162, -0.077] * |
| development | lightgbm − spline_gam | -0.073 [-0.106, -0.038] * |
| holdout | lightgbm − hist_group_median | -0.180 [-0.207, -0.147] * |
| holdout | lightgbm − team_adjusted_form | -0.097 [-0.124, -0.065] * |
| holdout | lightgbm − ridge | -0.051 [-0.085, -0.018] * |
| holdout | lightgbm − spline_gam | -0.041 [-0.079, -0.009] * |

Selected: **LightGBM (Huber)** — lowest MAE on development walk-forward folds (holdout season not used for selection).

Secondary split — event-held-out 5-fold (not temporal; shows how much the temporal split matters):

| Model | MAE % | 90% PI coverage |
|---|---|---|
| Ridge | 0.805 | 88.7% |
| LightGBM (Huber) | 0.769 | 88.8% |


### Value of the same weekend's qualifying

MAE(pre_race) − MAE(pre_event), selected models: development -0.0200 [-0.0323, -0.0091] *, holdout -0.0205 [-0.0318, -0.0095] *.

## Feature-group ablations (LightGBM, pre-event)

Each configuration vs the full model (`driver+team+track+tyre+weather+race_context+interaction+corner`) on identical laps; positive = worse than full.

| Configuration | Kind | Features | Dev MAE | Δ vs full (dev) | Holdout MAE | Δ vs full (holdout) |
|---|---|---|---|---|---|---|
| driver | cumulative | 4 | 1.0791 | +0.2910 [+0.2431, +0.3272] * | 1.0911 | +0.3117 [+0.2473, +0.3828] * |
| driver + team | cumulative | 8 | 1.0918 | +0.3037 [+0.2591, +0.3376] * | 1.0941 | +0.3147 [+0.2531, +0.3868] * |
| driver + team + track | cumulative | 12 | 1.0907 | +0.3026 [+0.2539, +0.3380] * | 1.0883 | +0.3089 [+0.2418, +0.3846] * |
| driver + team + track + tyre | cumulative | 16 | 0.9231 | +0.1350 [+0.0995, +0.1754] * | 0.9316 | +0.1522 [+0.1046, +0.2003] * |
| driver + team + track + tyre + weather | cumulative | 21 | 0.9340 | +0.1459 [+0.1029, +0.1989] * | 0.9292 | +0.1498 [+0.1032, +0.2050] * |
| driver + team + track + tyre + weather + race_context | cumulative | 24 | 0.7809 | -0.0071 [-0.0133, +0.0009] | 0.7798 | +0.0004 [-0.0051, +0.0065] |
| driver + team + track + tyre + weather + race_context + interaction | cumulative | 25 | 0.7836 | -0.0045 [-0.0115, +0.0042] | 0.7786 | -0.0008 [-0.0072, +0.0067] |
| driver + team + track + tyre + weather + race_context + interaction + corner | cumulative | 28 | 0.7881 | – | 0.7794 | – |
| full_minus_driver | leave_one_out | 24 | 0.7933 | +0.0052 [+0.0013, +0.0095] * | 0.7992 | +0.0198 [+0.0138, +0.0264] * |
| full_minus_team | leave_one_out | 24 | 0.7822 | -0.0059 [-0.0173, +0.0053] | 0.7694 | -0.0101 [-0.0174, -0.0038] * |
| full_minus_track | leave_one_out | 24 | 0.7892 | +0.0011 [-0.0041, +0.0056] | 0.7797 | +0.0003 [-0.0059, +0.0070] |
| full_minus_tyre | leave_one_out | 24 | 0.8242 | +0.0361 [+0.0241, +0.0515] * | 0.8344 | +0.0550 [+0.0365, +0.0761] * |
| full_minus_weather | leave_one_out | 23 | 0.7954 | +0.0073 [-0.0037, +0.0200] | 0.7814 | +0.0020 [-0.0113, +0.0150] |
| full_minus_race_context | leave_one_out | 25 | 0.9283 | +0.1402 [+0.1022, +0.1782] * | 0.9298 | +0.1504 [+0.0945, +0.2079] * |
| full_minus_interaction | leave_one_out | 27 | 0.7868 | -0.0012 [-0.0047, +0.0023] | 0.7779 | -0.0016 [-0.0053, +0.0030] |
| full_minus_corner | leave_one_out | 25 | 0.7836 | -0.0045 [-0.0115, +0.0042] | 0.7786 | -0.0008 [-0.0072, +0.0067] |


## Model B — sector pace with driver corner profiles

| Model | Pooled MAE % |
|---|---|
| lgbm_base | 0.9402 |
| lgbm_profile | 0.9386 |
| ridge_base | 0.9896 |
| ridge_profile | 0.9898 |

Profile − base: LightGBM -0.0016 [-0.0037, +0.0005], Ridge +0.0001 [-0.0010, +0.0013]. Profile coverage 45.8% of sector rows.

## Model C — tyre degradation

walk-forward by season; first 5 laps of each stint (>= 14 laps) anchor the level; 45,098 predicted laps in 68 events.

| Slope model | MAE % | MAE s |
|---|---|---|
| flat | 1.0262 | 0.8817 |
| compound | 0.8785 | 0.7640 |
| compound_circuit | 0.8437 | 0.7379 |
| compound_circuit_driver | 0.8454 | 0.7394 |

| Comparison | MAE difference [95% CI] |
|---|---|
| compound − flat | -0.1477 [-0.2605, -0.0041] * |
| circuit − compound | -0.0348 [-0.0830, +0.0138] |
| driver − circuit | +0.0016 [-0.0008, +0.0041] |


## Model F — pre-event qualifying gap

Target: qualifying gap to pole, % (dry, <= 5%); 1,254 driver-events. Pre-event forecast; the weekend's practice and qualifying are not used. Wet qualifying sessions are excluded.

| Model | MAE % | Mean event Spearman | Pole hit rate | Top-3 overlap | Events |
|---|---|---|---|---|---|
| lightgbm | 0.572 | 0.709 | 0.438 | 0.562 | 64 |
| team_form_baseline | 0.722 | 0.652 | 0.438 | 0.583 | 64 |

LightGBM − baseline MAE: -0.149 [-0.226, -0.088] *.

