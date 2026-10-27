# Explainability

_Generated 2026-10-27 08:09 UTC by `scripts/generate_reports.py` from `evaluation_runs/20261027T075133Z.json`, `models/*/explanation_validation.json`. Do not edit by hand; re-run the script._

All explanations describe how the fitted models use their inputs. They are associations learned from observational data and never causal effects.

## `pre_event`: global explanations (test season 2026 (model trained on 2022-2025), 15,000 laps)

![Grouped permutation importance](figures/explain_pre_event_permutation.png)

| Feature | Group | Mean \|SHAP\| % | Mean SHAP % |
|---|---|---|---|
| race_progress | race_context | 0.467 | 0.026 |
| drv_form_pace | driver | 0.286 | -0.005 |
| lap_number | race_context | 0.281 | 0.047 |
| tyre_life_laps | tyre | 0.192 | -0.023 |
| team_form_pace | team | 0.155 | -0.008 |
| team_season_form | team | 0.118 | -0.023 |
| drv_quali_form | driver | 0.087 | -0.005 |
| stint | tyre | 0.056 | 0.007 |
| is_sprint | race_context | 0.052 | -0.009 |
| humidity_pct | weather | 0.037 | 0.013 |
| air_temp_c | weather | 0.037 | 0.006 |
| track_temp_c | weather | 0.035 | 0.021 |

LightGBM vs Ridge importance ranking: Spearman 0.69 over 17 shared features.

![ALE curves](figures/explain_ale.png)

*ALE curves show the model's average response to one input, accounting for correlated inputs; they are not causal effects.*

### Explanation validation (`lap_pace_pre_event-lightgbm-20261027-6f07d7f246`, season 2026, 3,000 laps)

| Check | Result |
|---|---|
| Additivity (base + contributions − prediction), max abs | 1.1e-14 |
| TreeSHAP vs `shap` library, max abs difference | 0.0e+00 |
| Global ranking stability across 20 bootstrap refits (mean / min Spearman) | 0.90 / 0.78 |
| Top-5 feature sets across refits (mean Jaccard) | 0.89 |
| Local top-3 contribution sign agreement across refits | 0.997 |
| Mean SD of local top-3 contributions across refits (%) | 0.058 |
| Agreement with the other horizon's model (Spearman of importance) | 0.87 |
| Agreement with Ridge (Spearman of mean \|contribution\| / sign agreement) | 0.69 / 0.71 |

Top-5 frequency across refits: `race_progress` 100%, `drv_form_pace` 100%, `lap_number` 100%, `tyre_life_laps` 100%, `team_season_form` 80%.

Sensitivity (mean |Δprediction| % for ±5% SD perturbations): `race_progress` 0.027, `circuit_ref_lap_s` 0.021, `lap_number` 0.018, `drv_form_pace` 0.011, `drv_quali_form` 0.008.

Correlated pairs whose credit SHAP may split arbitrarily: `team_form_pace`/`team_quali_form` (0.96), `drv_form_pace`/`team_form_pace` (0.95), `team_form_pace`/`team_season_form` (0.95), `drv_quali_form`/`team_quali_form` (0.95), `team_season_form`/`team_quali_form` (0.94), `drv_form_pace`/`drv_quali_form` (0.94).

## `pre_race`: global explanations (test season 2026 (model trained on 2022-2025), 15,000 laps)

![Grouped permutation importance](figures/explain_pre_race_permutation.png)

| Feature | Group | Mean \|SHAP\| % | Mean SHAP % |
|---|---|---|---|
| race_progress | race_context | 0.474 | 0.036 |
| lap_number | race_context | 0.302 | 0.046 |
| evt_quali_gap | weekend | 0.268 | 0.034 |
| tyre_life_laps | tyre | 0.211 | -0.028 |
| drv_form_pace | driver | 0.204 | 0.008 |
| team_form_pace | team | 0.118 | -0.003 |
| team_season_form | team | 0.101 | -0.024 |
| circuit_ref_lap_s | track | 0.064 | 0.002 |
| humidity_pct | weather | 0.048 | 0.027 |
| track_temp_c | weather | 0.048 | 0.033 |
| stint | tyre | 0.047 | 0.009 |
| is_sprint | race_context | 0.047 | -0.007 |

LightGBM vs Ridge importance ranking: Spearman 0.69 over 19 shared features.

### Explanation validation (`lap_pace_pre_race-lightgbm-20261027-7befafcc5b`, season 2026, 3,000 laps)

| Check | Result |
|---|---|
| Additivity (base + contributions − prediction), max abs | 1.3e-14 |
| TreeSHAP vs `shap` library, max abs difference | 0.0e+00 |
| Global ranking stability across 20 bootstrap refits (mean / min Spearman) | 0.91 / 0.81 |
| Top-5 feature sets across refits (mean Jaccard) | 1.00 |
| Local top-3 contribution sign agreement across refits | 0.997 |
| Mean SD of local top-3 contributions across refits (%) | 0.062 |
| Agreement with the other horizon's model (Spearman of importance) | 0.87 |
| Agreement with Ridge (Spearman of mean \|contribution\| / sign agreement) | 0.69 / 0.58 |

Top-5 frequency across refits: `race_progress` 100%, `drv_form_pace` 100%, `evt_quali_gap` 100%, `lap_number` 100%, `tyre_life_laps` 100%.

Sensitivity (mean |Δprediction| % for ±5% SD perturbations): `evt_quali_gap` 0.031, `race_progress` 0.030, `circuit_ref_lap_s` 0.028, `lap_number` 0.019, `humidity_pct` 0.010.

Correlated pairs whose credit SHAP may split arbitrarily: `evt_quali_gap`/`evt_team_quali_gap` (0.97), `team_form_pace`/`team_quali_form` (0.96), `drv_form_pace`/`team_form_pace` (0.95), `team_form_pace`/`team_season_form` (0.95), `drv_quali_form`/`team_quali_form` (0.95), `team_season_form`/`team_quali_form` (0.94).

## Worked local explanation

Scenario: `isack-hadjar` before event `2026-18` (Americas), medium tyres 12 laps old, half race distance, `pre_event` model `lap_pace_pre_event-lightgbm-20261027-6f07d7f246`.

Prediction -0.691% of the reference lap (90% interval -2.56 … +1.18; model spread 0.107% SD across bootstrap refits).

| Input | Value | Contribution % |
|---|---|---|
| Driver's recent race pace | -0.569542 | -0.348 |
| Lap number | 28 | 0.200 |
| Team's race pace this season | -0.893451 | -0.149 |
| Team's recent race pace (car proxy) | -0.827501 | -0.124 |
| Tyre age | 12 | -0.098 |
| Driver's recent qualifying gap to pole | 0.835618 | -0.083 |
| Driver's recent gap to team-mate | 0.691692 | 0.056 |
| Air temperature | 29.2 | -0.038 |

> For Isack Hadjar at Americas, the model (lightgbm, pre-event horizon) predicts a representative race lap 0.69% faster than the session reference (about 0.70 s per lap). The 90% interval for a single lap is -2.56% to +1.18%; it reflects lap-to-lap variation as well as model error. Refitting the model on resampled races moves the expected value between -0.90% and -0.57% (model uncertainty). Relative to the model's average output, the largest contributions are driver's recent race pace (-0.35%), lap number (+0.20%), team's race pace this season (-0.15%). Contributions describe how the model uses its inputs; they are associations, not causal effects.

Warnings: none.

