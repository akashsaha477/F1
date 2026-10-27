# Feature engineering

_Generated 2026-10-27 08:09 UTC by `scripts/generate_reports.py` from `gold/lap_features`, `features/definitions.py`. Do not edit by hand; re-run the script._

Model A inputs by group. *Availability* is the latest point in time at which a value is known (`pre_event` = only earlier events; `pre_race` = adds the same weekend's qualifying; `scenario` = a condition set by the user or observed on the lap). Statistics are over representative race laps.

| Feature | Group | Unit | Availability | Missing | p5 | Median | p95 |
|---|---|---|---|---|---|---|---|
| `drv_form_pace` | driver | % | pre_event | 1.4% | -1.29 | 0.20 | 1.11 |
| `drv_form_n` | driver | events | pre_event | 0.0% | 3.00 | 10.00 | 10.00 |
| `drv_teammate_gap_form` | driver | % | pre_event | 1.2% | -0.78 | -0.02 | 0.66 |
| `drv_quali_form` | driver | % gap to pole | pre_event | 1.2% | 0.27 | 1.61 | 3.91 |
| `team_form_pace` | team | % | pre_event | 1.2% | -1.29 | 0.23 | 1.08 |
| `team_season_form` | team | % | pre_event | 5.1% | -1.46 | 0.20 | 1.21 |
| `team_season_events` | team | events | pre_event | 0.0% | 1.00 | 10.00 | 21.00 |
| `team_quali_form` | team | % gap to pole | pre_event | 1.1% | 0.40 | 1.61 | 3.98 |
| `evt_quali_gap` | weekend | % gap to pole | pre_race | 1.0% | 0.00 | 1.27 | 4.11 |
| `evt_team_quali_gap` | weekend | % gap to pole | pre_race | 0.1% | 0.16 | 1.34 | 4.28 |
| `circuit_length_km` | track | km | static | 0.0% | 4.26 | 5.28 | 6.20 |
| `circuit_turns` | track | count | static | 0.0% | 10.00 | 16.00 | 20.00 |
| `circuit_is_street` | track | bool | static | 0.0% | 0.00 | 0.00 | 1.00 |
| `circuit_ref_lap_s` | track | s | pre_event | 21.6% | 71.39 | 87.17 | 109.88 |
| `circuit_frac_slow` | corner | fraction | static | 0.0% | 0.10 | 0.44 | 0.64 |
| `circuit_frac_fast` | corner | fraction | static | 0.0% | 0.00 | 0.25 | 0.50 |
| `circuit_full_throttle_frac` | corner | fraction | static | 0.0% | 0.61 | 0.72 | 0.81 |
| `tyre_life_laps` | tyre | laps | scenario | 0.3% | 3.00 | 13.00 | 34.00 |
| `fresh_tyre` | tyre | bool | scenario | 0.0% | 0.00 | 1.00 | 1.00 |
| `stint` | tyre | count | scenario | 0.0% | 1.00 | 2.00 | 4.00 |
| `track_temp_c` | weather | °C | scenario | 0.0% | 19.40 | 36.10 | 50.50 |
| `air_temp_c` | weather | °C | scenario | 0.0% | 16.30 | 25.00 | 31.50 |
| `humidity_pct` | weather | % | scenario | 0.0% | 21.50 | 53.00 | 77.00 |
| `rainfall` | weather | bool | scenario | 0.0% | 0.00 | 0.00 | 0.00 |
| `is_wet_compound` | weather | bool | scenario | 0.0% | 0.00 | 0.00 | 0.00 |
| `race_progress` | race_context | fraction | scenario | 0.0% | 0.09 | 0.51 | 0.95 |
| `lap_number` | race_context | lap | scenario | 0.0% | 4.00 | 28.00 | 61.00 |
| `is_sprint` | race_context | bool | static | 0.0% | 0.00 | 0.00 | 1.00 |
| `drv_circuit_hist` | interaction | % | pre_event | 36.4% | -1.25 | 0.00 | 0.93 |

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
| `drv_form_pace` | `team_form_pace` | 0.93 |
| `drv_form_pace` | `team_season_form` | 0.92 |
| `drv_quali_form` | `team_quali_form` | 0.91 |
| `evt_quali_gap` | `evt_team_quali_gap` | 0.90 |
| `race_progress` | `lap_number` | 0.89 |
| `team_form_pace` | `team_quali_form` | 0.83 |
| `circuit_length_km` | `circuit_ref_lap_s` | 0.82 |
| `team_season_form` | `team_quali_form` | 0.81 |
| `drv_form_pace` | `drv_quali_form` | 0.80 |
| `drv_form_pace` | `team_quali_form` | 0.78 |
| `drv_quali_form` | `team_form_pace` | 0.77 |
| `drv_quali_form` | `team_season_form` | 0.77 |
| `track_temp_c` | `air_temp_c` | 0.72 |
| `stint` | `lap_number` | 0.72 |
| `team_quali_form` | `evt_team_quali_gap` | 0.71 |
| `team_season_form` | `evt_team_quali_gap` | 0.70 |
| `team_form_pace` | `evt_team_quali_gap` | 0.70 |

Correlated inputs share credit arbitrarily in SHAP explanations; grouped permutation importance is reported alongside for that reason.
