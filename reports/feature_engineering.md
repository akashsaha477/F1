# Feature engineering

_Generated 2026-10-26 18:57 UTC by `scripts/generate_reports.py` from `gold/lap_features`, `features/definitions.py`. Do not edit by hand; re-run the script._

Model A inputs by group. *Availability* is the latest point in time at which a value is known (`pre_event` = only earlier events; `pre_race` = adds the same weekend's qualifying; `scenario` = a condition set by the user or observed on the lap). Statistics are over representative race laps.

| Feature | Group | Unit | Availability | Missing | p5 | Median | p95 |
|---|---|---|---|---|---|---|---|
| `drv_form_pace` | driver | % | pre_event | 1.6% | -1.25 | 0.18 | 1.01 |
| `drv_form_n` | driver | events | pre_event | 0.0% | 3.00 | 10.00 | 10.00 |
| `drv_teammate_gap_form` | driver | % | pre_event | 1.4% | -0.78 | -0.02 | 0.68 |
| `drv_quali_form` | driver | % gap to pole | pre_event | 1.4% | 0.24 | 1.60 | 3.91 |
| `team_form_pace` | team | % | pre_event | 1.4% | -1.26 | 0.21 | 0.97 |
| `team_season_form` | team | % | pre_event | 5.2% | -1.34 | 0.21 | 0.98 |
| `team_season_events` | team | events | pre_event | 0.0% | 1.00 | 11.00 | 21.00 |
| `team_quali_form` | team | % gap to pole | pre_event | 1.2% | 0.40 | 1.60 | 3.67 |
| `evt_quali_gap` | weekend | % gap to pole | pre_race | 1.0% | 0.00 | 1.22 | 3.81 |
| `evt_team_quali_gap` | weekend | % gap to pole | pre_race | 0.2% | 0.17 | 1.30 | 4.09 |
| `circuit_length_km` | track | km | static | 0.0% | 4.26 | 5.28 | 6.20 |
| `circuit_turns` | track | count | static | 0.0% | 10.00 | 16.00 | 20.00 |
| `circuit_is_street` | track | bool | static | 0.0% | 0.00 | 0.00 | 1.00 |
| `circuit_ref_lap_s` | track | s | pre_event | 24.4% | 71.39 | 87.17 | 109.88 |
| `circuit_frac_slow` | corner | fraction | static | 0.0% | 0.18 | 0.43 | 0.67 |
| `circuit_frac_fast` | corner | fraction | static | 0.0% | 0.00 | 0.25 | 0.57 |
| `circuit_full_throttle_frac` | corner | fraction | static | 0.0% | 0.61 | 0.71 | 0.81 |
| `tyre_life_laps` | tyre | laps | scenario | 0.2% | 3.00 | 13.00 | 34.00 |
| `fresh_tyre` | tyre | bool | scenario | 0.0% | 0.00 | 1.00 | 1.00 |
| `stint` | tyre | count | scenario | 0.0% | 1.00 | 2.00 | 4.00 |
| `track_temp_c` | weather | °C | scenario | 0.0% | 19.90 | 35.30 | 49.20 |
| `air_temp_c` | weather | °C | scenario | 0.0% | 16.90 | 24.40 | 30.90 |
| `humidity_pct` | weather | % | scenario | 0.0% | 21.00 | 54.00 | 78.00 |
| `rainfall` | weather | bool | scenario | 0.0% | 0.00 | 0.00 | 0.00 |
| `is_wet_compound` | weather | bool | scenario | 0.0% | 0.00 | 0.00 | 0.00 |
| `race_progress` | race_context | fraction | scenario | 0.0% | 0.09 | 0.52 | 0.95 |
| `lap_number` | race_context | lap | scenario | 0.0% | 5.00 | 29.00 | 61.00 |
| `is_sprint` | race_context | bool | static | 0.0% | 0.00 | 0.00 | 1.00 |
| `drv_circuit_hist` | interaction | % | pre_event | 40.0% | -1.34 | 0.00 | 0.94 |

LightGBM handles missing values natively; the linear models impute training medians and winsorise inputs at the 1st/99th training percentiles. Full definitions: `docs/feature_definitions.md`.

## Leakage controls

* Form features are exponentially weighted means (half-life 4 events) of results from events that finished before the event's first session (shifted EWMA); `drv_form_n` counts those events, capped at 10.
* `circuit_ref_lap_s` and `drv_circuit_hist` use earlier seasons only.
* Circuit corner profiles come from qualifying telemetry; for evaluation they are a fixed track descriptor.
* `tests/modeling/test_leakage.py` perturbs future events and asserts that earlier features do not change; the walk-forward splitter raises if training data reaches the test period.

## Strongly correlated inputs (|Spearman| ≥ 0.7)

| Feature | Feature | Spearman |
|---|---|---|
| `team_form_pace` | `team_season_form` | 0.97 |
| `drv_form_pace` | `team_form_pace` | 0.92 |
| `drv_form_pace` | `team_season_form` | 0.91 |
| `drv_quali_form` | `team_quali_form` | 0.90 |
| `race_progress` | `lap_number` | 0.89 |
| `evt_quali_gap` | `evt_team_quali_gap` | 0.88 |
| `circuit_length_km` | `circuit_ref_lap_s` | 0.81 |
| `team_form_pace` | `team_quali_form` | 0.79 |
| `team_season_form` | `team_quali_form` | 0.77 |
| `drv_form_pace` | `drv_quali_form` | 0.76 |
| `drv_form_pace` | `team_quali_form` | 0.74 |
| `drv_quali_form` | `team_form_pace` | 0.74 |
| `drv_quali_form` | `team_season_form` | 0.73 |
| `stint` | `lap_number` | 0.72 |

Correlated inputs share credit arbitrarily in SHAP explanations; grouped permutation importance is reported alongside for that reason.
