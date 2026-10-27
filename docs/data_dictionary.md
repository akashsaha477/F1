# Data dictionary

_Generated 2026-10-27 08:09 UTC by `scripts/generate_reports.py` from `data/processed (silver)`, `data/features (gold)`. Do not edit by hand; re-run the script._

Generated from the stored Parquet tables: column, type, share non-null and an example value. Feature semantics are in `docs/feature_definitions.md`; sources and licences in `docs/data_sources.md`.

## Silver layer

### `events` — 1,172 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `event_id` | object | 100.0% | 1950-01 |
| `f1db_race_id` | int64 | 100.0% | 1 |
| `season` | int64 | 100.0% | 1950 |
| `round` | int64 | 100.0% | 1 |
| `slug` | object | 100.0% | 01-great-britain |
| `date` | object | 100.0% | 1950-05-13 |
| `grand_prix_id` | object | 100.0% | great-britain |
| `official_name` | object | 100.0% | 1950 RAC British Grand Prix |
| `circuit_id` | object | 100.0% | silverstone |
| `circuit_layout_id` | object | 100.0% | silverstone-1 |
| `circuit_type` | object | 100.0% | RACE |
| `direction` | object | 100.0% | CLOCKWISE |
| `course_length_km` | float64 | 100.0% | 4.649 |
| `turns` | int64 | 100.0% | 8 |
| `laps` | int64 | 100.0% | 70 |
| `distance_km` | float64 | 100.0% | 325.43 |
| `sprint_laps` | float64 | 2.6% | 17.0 |
| `qualifying_format` | object | 100.0% | TWO_SESSION |
| `sprint_qualifying_format` | object | 2.0% | SPRINT_SHOOTOUT |
| `is_sprint_weekend` | bool | 100.0% | False |
| `era` | object | 100.0% | early_front_engine |

### `sessions` — 4,280 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 1950-01-R |
| `event_id` | object | 100.0% | 1950-01 |
| `season` | int64 | 100.0% | 1950 |
| `round` | int64 | 100.0% | 1 |
| `session_code` | object | 100.0% | R |
| `date` | object | 34.0% | 1950-05-13 |
| `start_utc` | object | 34.0% | 1950-05-13 |
| `date_source` | object | 100.0% | f1db_schedule |

### `drivers` — 917 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `driver_id` | object | 100.0% | adderly-fong |
| `name` | object | 100.0% | Adderly Fong |
| `first_name` | object | 100.0% | Adderly |
| `last_name` | object | 100.0% | Fong |
| `full_name` | object | 100.0% | Adderly Fong Cheun-yue |
| `abbreviation` | object | 100.0% | FON |
| `permanent_number` | object | 3.1% | 23 |
| `gender` | object | 100.0% | MALE |
| `date_of_birth` | object | 100.0% | 1990-03-02 |
| `nationality_country_id` | object | 100.0% | hong-kong |
| `country_of_birth_id` | object | 100.0% | canada |

### `constructors` — 187 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `constructor_id` | object | 100.0% | adams |
| `name` | object | 100.0% | Adams |
| `full_name` | object | 100.0% | Adams |
| `country_id` | object | 100.0% | united-states-of-america |

### `circuits` — 78 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `circuit_id` | object | 100.0% | adelaide |
| `name` | object | 100.0% | Adelaide |
| `full_name` | object | 100.0% | Adelaide Street Circuit |
| `type` | object | 100.0% | STREET |
| `direction` | object | 100.0% | CLOCKWISE |
| `place_name` | object | 100.0% | Adelaide |
| `country_id` | object | 100.0% | australia |
| `latitude` | float64 | 100.0% | -34.9272 |
| `longitude` | float64 | 100.0% | 138.6172 |
| `length_km` | float64 | 100.0% | 3.78 |
| `turns` | int64 | 100.0% | 16 |

### `race_results` — 28,299 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `event_id` | object | 100.0% | 1950-01 |
| `season` | int64 | 100.0% | 1950 |
| `round` | int64 | 100.0% | 1 |
| `session_code` | object | 100.0% | R |
| `position` | float64 | 61.2% | 1.0 |
| `position_text` | object | 100.0% | 1 |
| `driver_id` | object | 100.0% | nino-farina |
| `constructor_id` | object | 100.0% | alfa-romeo |
| `driver_number` | object | 100.0% | 2 |
| `laps` | float64 | 93.2% | 70.0 |
| `time_s` | float64 | 30.9% | 8003.6 |
| `gap_s` | float64 | 26.7% | 2.6 |
| `time_penalty_s` | float64 | 1.1% | 60.0 |
| `points` | float64 | 31.2% | 9.0 |
| `grid_position` | float64 | 92.8% | 1.0 |
| `grid_text` | object | 93.7% | 1 |
| `reason_retired` | object | 35.9% | Oil pipe |
| `outcome_category` | object | 100.0% | finished |

### `qualifying_results` — 27,593 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `event_id` | object | 100.0% | 1950-01 |
| `season` | int64 | 100.0% | 1950 |
| `round` | int64 | 100.0% | 1 |
| `session_code` | object | 100.0% | Q |
| `position` | float64 | 99.5% | 1.0 |
| `position_text` | object | 100.0% | 1 |
| `driver_id` | object | 100.0% | nino-farina |
| `constructor_id` | object | 100.0% | alfa-romeo |
| `driver_number` | object | 100.0% | 2 |
| `q1_s` | float64 | 33.2% | 93.31 |
| `q2_s` | float64 | 24.4% | 92.025 |
| `q3_s` | float64 | 15.5% | 91.431 |
| `best_s` | float64 | 99.1% | 110.8 |
| `laps` | float64 | 49.5% | 22.0 |

### `laps` — 300,870 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-FP1 |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `round` | int64 | 100.0% | 1 |
| `session_code` | object | 100.0% | FP1 |
| `session_type` | object | 100.0% | practice |
| `driver_id` | object | 100.0% | alexander-albon |
| `constructor_id` | object | 100.0% | williams |
| `circuit_id` | object | 100.0% | bahrain |
| `driver_abbr` | object | 100.0% | ALB |
| `driver_number` | object | 100.0% | 23 |
| `team_name` | object | 99.6% | Williams |
| `lap_number` | Int64 | 100.0% | 1 |
| `lap_time_s` | float64 | 86.5% | 98.92 |
| `sector1_s` | float64 | 90.4% | 31.67 |
| `sector2_s` | float64 | 99.2% | 50.555 |
| `sector3_s` | float64 | 97.4% | 29.257 |
| `session_time_end_s` | float64 | 100.0% | 1144.929 |
| `lap_start_time_s` | float64 | 99.9% | 1030.741 |
| `lap_start_utc` | datetime64[ns, UTC] | 99.9% | 2022-03-18 12:02:10.754000+00:00 |
| `sector1_session_time_s` | float64 | 90.2% | 2333.612 |
| `sector2_session_time_s` | float64 | 99.2% | 1115.684 |
| `sector3_session_time_s` | float64 | 97.4% | 1144.929 |
| `pit_in_time_s` | float64 | 13.0% | 1143.055 |
| `pit_out_time_s` | float64 | 13.1% | 1030.741 |
| `speed_i1_kph` | float64 | 99.6% | 209.0 |
| `speed_i2_kph` | float64 | 98.9% | 234.0 |
| `speed_fl_kph` | float64 | 86.9% | 278.0 |
| `speed_st_kph` | float64 | 98.8% | 197.0 |
| `compound_raw` | object | 99.6% | HARD |
| `tyre_life_laps` | float64 | 99.5% | 1.0 |
| `fresh_tyre` | boolean | 100.0% | True |
| `stint` | Int64 | 99.8% | 1 |
| `position` | Int64 | 44.0% | 11 |
| `track_status` | object | 99.9% | 1 |
| `is_personal_best` | boolean | 99.9% | False |
| `deleted` | boolean | 99.9% | False |
| `deleted_reason` | object | 1.1% | TRACK LIMITS AT TURN 5 |
| `fastf1_generated` | boolean | 100.0% | False |
| `is_accurate` | boolean | 100.0% | False |
| `quali_segment` | object | 12.6% | Q1 |
| `weather_time_s` | float64 | 99.8% | 1134.3 |
| `air_temp_c` | float64 | 99.8% | 19.9 |
| `track_temp_c` | float64 | 99.8% | 36.0 |
| `humidity_pct` | float64 | 99.8% | 37.0 |
| `pressure_mbar` | float64 | 99.8% | 1016.0 |
| `rainfall` | boolean | 99.8% | False |
| `wind_dir_deg` | float64 | 99.8% | 359.0 |
| `wind_speed_ms` | float64 | 99.8% | 0.6 |
| `source` | object | 100.0% | tracinginsights |
| `compound` | object | 100.0% | HARD |
| `identity_method` | object | 100.0% | session_number |
| `status_known` | bool | 100.0% | True |
| `flag_green_only` | bool | 100.0% | True |
| `flag_yellow` | bool | 100.0% | False |
| `flag_sc` | bool | 100.0% | False |
| `flag_red` | bool | 100.0% | False |
| `flag_vsc` | bool | 100.0% | False |
| `is_pit_in_lap` | bool | 100.0% | True |
| `is_pit_out_lap` | bool | 100.0% | True |
| `is_first_lap` | boolean | 100.0% | False |
| `is_wet_compound` | bool | 100.0% | False |
| `condition` | object | 100.0% | dry |
| `exclusion_reason` | object | 35.4% | no_lap_time |
| `is_clean` | bool | 100.0% | False |

### `stints` — 41,820 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-FP1 |
| `driver_id` | object | 100.0% | alexander-albon |
| `driver_number` | object | 100.0% | 23 |
| `stint` | Int64 | 100.0% | 1 |
| `compound` | object | 100.0% | HARD |
| `n_compounds` | int64 | 100.0% | 1 |
| `start_lap` | Int64 | 100.0% | 1 |
| `end_lap` | Int64 | 100.0% | 1 |
| `n_laps` | Int64 | 100.0% | 1 |
| `n_clean_laps` | int64 | 100.0% | 0 |
| `tyre_life_start` | float64 | 99.8% | 1.0 |
| `tyre_life_end` | float64 | 99.8% | 1.0 |
| `fresh_tyre` | boolean | 100.0% | True |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `round` | int64 | 100.0% | 1 |
| `session_code` | object | 100.0% | FP1 |
| `constructor_id` | object | 100.0% | williams |

### `weather_observations` — 54,779 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-FP1 |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `session_time_s` | float64 | 100.0% | 54.194 |
| `air_temp_c` | float64 | 100.0% | 20.1 |
| `track_temp_c` | float64 | 100.0% | 36.9 |
| `humidity_pct` | float64 | 100.0% | 36.0 |
| `pressure_mbar` | float64 | 100.0% | 1016.2 |
| `rainfall` | boolean | 100.0% | False |
| `wind_dir_deg` | float64 | 100.0% | 3.0 |
| `wind_speed_ms` | float64 | 100.0% | 0.9 |

### `race_control_events` — 28,580 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-FP1 |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `time_utc` | datetime64[ns, UTC] | 100.0% | 2022-03-18 11:45:14+00:00 |
| `lap` | float64 | 45.5% | 1.0 |
| `category` | object | 100.0% | Other |
| `message` | object | 100.0% | RISK OF RAIN FOR F1 FIRST PRACTICE SESSI… |
| `status` | object | 3.5% | DISABLED |
| `flag` | object | 51.8% | YELLOW |
| `scope` | object | 51.8% | Sector |
| `sector` | float64 | 30.5% | 11.0 |
| `racing_number` | object | 14.9% | 16 |

### `track_status_events` — 15,260 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-FP1 |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `time_utc` | datetime64[ns, UTC] | 100.0% | 2022-03-18 11:56:42+00:00 |
| `lap` | float64 | 48.1% | 1.0 |
| `category` | object | 100.0% | Flag |
| `message` | object | 100.0% | YELLOW IN TRACK SECTOR 11 |
| `status` | object | 3.0% | DEPLOYED |
| `flag` | object | 97.0% | YELLOW |
| `scope` | object | 97.0% | Sector |
| `sector` | float64 | 57.0% | 11.0 |
| `racing_number` | object | 22.6% | 27 |

### `telemetry_laps` — 2,696 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-Q |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `session_code` | object | 100.0% | Q |
| `driver_id` | object | 100.0% | charles-leclerc |
| `constructor_id` | object | 100.0% | ferrari |
| `driver_abbr` | object | 100.0% | LEC |
| `lap_number` | int64 | 100.0% | 14 |
| `lap_time_s` | float64 | 100.0% | 90.558 |
| `compound` | object | 100.0% | SOFT |
| `selection` | object | 100.0% | fastest_clean |
| `selection_rank` | int64 | 100.0% | 1 |
| `n_samples` | int64 | 100.0% | 697 |
| `quality_status` | object | 100.0% | warning |

### `telemetry_samples` — 200,000 rows (first 200k sampled)

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-Q |
| `driver_id` | object | 100.0% | charles-leclerc |
| `constructor_id` | object | 100.0% | ferrari |
| `driver_abbr` | object | 100.0% | LEC |
| `lap_number` | int64 | 100.0% | 14 |
| `sample_idx` | int64 | 100.0% | 0 |
| `time_s` | float64 | 100.0% | 0.0 |
| `rpm` | float64 | 100.0% | 10508.4 |
| `speed_kph` | float64 | 100.0% | 292.7333 |
| `gear` | float64 | 100.0% | 7.0 |
| `throttle_pct` | float64 | 100.0% | 100.0 |
| `brake` | bool | 100.0% | False |
| `drs` | float64 | 100.0% | 1.0 |
| `distance_m` | float64 | 100.0% | 0.0342 |
| `rel_distance` | float64 | 99.7% | 0.0 |
| `driver_ahead` | object | 91.2% | 77 |
| `distance_to_ahead_m` | float64 | 92.4% | 591.0478 |
| `acc_x_derived` | float64 | 100.0% | 1.5432 |
| `acc_y_derived` | float64 | 100.0% | 0.337 |
| `acc_z_derived` | float64 | 100.0% | -7.516 |
| `x_m` | float64 | 100.0% | -38.0417 |
| `y_m` | float64 | 100.0% | 128.0327 |
| `z_m` | float64 | 100.0% | -15.9186 |
| `lap_key` | object | 100.0% | charles-leclerc:14 |

### `corner_markers` — 9,030 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-FP1 |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `circuit_id` | object | 100.0% | bahrain |
| `number` | int64 | 100.0% | 1 |
| `letter` | object | 100.0% |  |
| `x_m` | float64 | 100.0% | 4.2406 |
| `y_m` | float64 | 100.0% | 832.9203 |
| `angle_deg` | float64 | 100.0% | -246.6153 |
| `distance_m` | float64 | 100.0% | 709.5028 |
| `rotation_deg` | float64 | 100.0% | 92.0 |
| `source` | object | 100.0% | fastf1_circuit_info |

### `session_drivers` — 11,119 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-FP1 |
| `driver_abbr` | object | 100.0% | VER |
| `driver_number` | object | 89.2% | 1 |
| `team` | object | 100.0% | Red Bull Racing |
| `first_name` | object | 89.2% | Max |
| `last_name` | object | 89.2% | Verstappen |
| `team_colour` | object | 89.2% | 1e5bc6 |

## Gold layer

### `all_laps_relative` — 300,561 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-FP1 |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `round` | int64 | 100.0% | 1 |
| `session_code` | object | 100.0% | FP1 |
| `session_type` | object | 100.0% | practice |
| `circuit_id` | object | 100.0% | bahrain |
| `driver_id` | object | 100.0% | alexander-albon |
| `constructor_id` | object | 100.0% | williams |
| `driver_abbr` | object | 100.0% | ALB |
| `lap_number` | Int64 | 100.0% | 1 |
| `lap_time_s` | float64 | 86.5% | 98.92 |
| `sector1_s` | float64 | 90.4% | 31.67 |
| `sector2_s` | float64 | 99.2% | 50.555 |
| `sector3_s` | float64 | 97.4% | 29.257 |
| `compound` | object | 100.0% | HARD |
| `tyre_life_laps` | float64 | 99.5% | 1.0 |
| `fresh_tyre` | boolean | 100.0% | True |
| `stint` | Int64 | 99.8% | 1 |
| `position` | Int64 | 44.1% | 11 |
| `track_status` | object | 100.0% | 1 |
| `air_temp_c` | float64 | 99.9% | 19.9 |
| `track_temp_c` | float64 | 99.9% | 36.0 |
| `humidity_pct` | float64 | 99.9% | 37.0 |
| `rainfall` | boolean | 99.9% | False |
| `wind_speed_ms` | float64 | 99.9% | 0.6 |
| `is_clean` | bool | 100.0% | False |
| `exclusion_reason` | object | 35.3% | no_lap_time |
| `condition` | object | 100.0% | dry |
| `is_wet_compound` | bool | 100.0% | False |
| `is_pit_in_lap` | bool | 100.0% | True |
| `is_pit_out_lap` | bool | 100.0% | True |
| `deleted` | boolean | 100.0% | False |
| `quali_segment` | object | 12.6% | Q1 |
| `speed_st_kph` | float64 | 98.9% | 197.0 |
| `lap_start_utc` | object | 100.0% | 2022-03-18 12:02:10.754000+00:00 |
| `session_ref_s` | float64 | 100.0% | 98.864 |
| `session_ref_n` | float64 | 100.0% | 223.0 |
| `rel_pace_pct` | float64 | 86.5% | 0.0566 |
| `drv_session_median_s` | float64 | 99.4% | 98.92 |
| `is_representative` | bool | 100.0% | False |

### `lap_features` — 132,628 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-R |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `round` | int64 | 100.0% | 1 |
| `session_code` | object | 100.0% | R |
| `session_type` | object | 100.0% | race |
| `circuit_id` | object | 100.0% | bahrain |
| `driver_id` | object | 100.0% | alexander-albon |
| `constructor_id` | object | 100.0% | williams |
| `driver_abbr` | object | 100.0% | ALB |
| `lap_number` | Int64 | 100.0% | 1 |
| `lap_time_s` | float64 | 99.1% | 107.636 |
| `sector1_s` | float64 | 97.6% | 32.027 |
| `sector2_s` | float64 | 99.8% | 46.031 |
| `sector3_s` | float64 | 99.7% | 24.844 |
| `compound` | object | 100.0% | SOFT |
| `tyre_life_laps` | float64 | 99.0% | 1.0 |
| `fresh_tyre` | float64 | 100.0% | 1.0 |
| `stint` | Int64 | 99.7% | 1 |
| `position` | Int64 | 99.8% | 11 |
| `track_status` | object | 100.0% | 1 |
| `air_temp_c` | float64 | 100.0% | 23.9 |
| `track_temp_c` | float64 | 100.0% | 29.1 |
| `humidity_pct` | float64 | 100.0% | 25.0 |
| `rainfall` | float64 | 100.0% | 0.0 |
| `wind_speed_ms` | float64 | 100.0% | 0.5 |
| `is_clean` | bool | 100.0% | False |
| `exclusion_reason` | object | 18.7% | race_start_lap |
| `condition` | object | 100.0% | dry |
| `is_wet_compound` | float64 | 100.0% | 0.0 |
| `is_pit_in_lap` | bool | 100.0% | False |
| `is_pit_out_lap` | bool | 100.0% | False |
| `deleted` | boolean | 100.0% | False |
| `quali_segment` | object | 0.0% | None |
| `speed_st_kph` | float64 | 99.8% | 263.0 |
| `lap_start_utc` | object | 100.0% | 2022-03-20 15:03:34.889000+00:00 |
| `session_ref_s` | float64 | 100.0% | 99.3225 |
| `session_ref_n` | float64 | 100.0% | 854.0 |
| `rel_pace_pct` | float64 | 99.1% | 8.3702 |
| `drv_session_median_s` | float64 | 99.9% | 100.8 |
| `is_representative` | bool | 100.0% | False |
| `drv_form_pace` | float64 | 98.6% | 1.4876 |
| `drv_form_n` | int64 | 100.0% | 0 |
| `drv_teammate_gap_form` | float64 | 98.7% | -0.3202 |
| `drv_quali_form` | float64 | 98.7% | 2.3256 |
| `drv_circuit_hist` | float64 | 62.2% | -0.3096 |
| `team_form_pace` | float64 | 98.7% | 1.6477 |
| `team_quali_form` | float64 | 98.8% | 2.8611 |
| `team_season_form` | float64 | 95.0% | 1.6477 |
| `team_season_events` | int64 | 100.0% | 0 |
| `evt_quali_gap` | float64 | 99.0% | 2.3256 |
| `evt_team_quali_gap` | float64 | 99.9% | 2.8611 |
| `date` | datetime64[ns] | 100.0% | 2022-03-20 00:00:00 |
| `circuit_type` | object | 100.0% | RACE |
| `circuit_length_km` | float64 | 100.0% | 5.412 |
| `circuit_turns` | int64 | 100.0% | 15 |
| `laps` | int64 | 100.0% | 57 |
| `sprint_laps` | float64 | 30.5% | 21.0 |
| `circuit_ref_lap_s` | float64 | 76.8% | 99.3225 |
| `race_progress` | float64 | 100.0% | 0.0175 |
| `is_sprint` | bool | 100.0% | False |
| `circuit_is_street` | bool | 100.0% | False |
| `circuit_frac_slow` | float64 | 100.0% | 0.4444 |
| `circuit_frac_fast` | float64 | 100.0% | 0.2222 |
| `circuit_full_throttle_frac` | float64 | 100.0% | 0.7138 |

### `driver_session_summary` — 10,844 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-FP1 |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `round` | int64 | 100.0% | 1 |
| `session_code` | object | 100.0% | FP1 |
| `circuit_id` | object | 100.0% | bahrain |
| `driver_id` | object | 100.0% | alexander-albon |
| `constructor_id` | object | 100.0% | williams |
| `med_rel_pace` | float64 | 100.0% | -1.5668 |
| `mean_rel_pace` | float64 | 100.0% | -1.5129 |
| `n_laps` | int64 | 100.0% | 4 |
| `mad_rel_pace` | float64 | 100.0% | 1.3438 |
| `wet_share` | float64 | 100.0% | 0.0 |
| `session_ref_s` | float64 | 100.0% | 98.864 |
| `robust_sd` | float64 | 100.0% | 1.9923 |
| `se_rel_pace` | float64 | 100.0% | 1.2485 |
| `is_wet_session` | bool | 100.0% | False |
| `teammate_med_rel_pace` | float64 | 98.0% | -1.0934 |
| `teammate_gap` | float64 | 98.0% | -0.4734 |

### `driver_event_form` — 2,235 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `event_id` | object | 100.0% | 2022-01 |
| `driver_id` | object | 100.0% | alexander-albon |
| `constructor_id` | object | 100.0% | williams |
| `season` | int64 | 100.0% | 2022 |
| `round` | int64 | 100.0% | 1 |
| `date` | datetime64[ns] | 100.0% | 2022-03-20 00:00:00 |
| `circuit_id` | object | 100.0% | bahrain |
| `pace` | float64 | 97.0% | 1.4876 |
| `tm_gap` | float64 | 94.8% | -0.3202 |
| `is_wet` | object | 97.0% | False |
| `evt_quali_gap` | float64 | 98.9% | 2.3256 |
| `pace_dry` | float64 | 89.5% | 1.4876 |
| `drv_form_pace` | float64 | 98.4% | 1.4876 |
| `drv_form_n` | int64 | 100.0% | 0 |
| `drv_teammate_gap_form` | float64 | 98.5% | -0.3202 |
| `drv_quali_form` | float64 | 98.6% | 2.3256 |
| `team_form_pace` | float64 | 98.6% | 1.6477 |
| `team_quali_form` | float64 | 98.7% | 2.8611 |
| `team_season_form` | float64 | 94.5% | 1.6477 |
| `team_season_events` | int64 | 100.0% | 0 |
| `evt_team_quali_gap` | float64 | 99.9% | 2.8611 |
| `pace_vs_form` | float64 | 88.1% | -0.3096 |
| `drv_circuit_hist` | float64 | 60.7% | -0.3096 |

### `driver_profiles` — 112 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `driver_id` | object | 100.0% | alexander-albon |
| `season` | int64 | 100.0% | 2022 |
| `main_team` | object | 100.0% | williams |
| `teams` | object | 100.0% | williams |
| `n_dry_races` | int64 | 100.0% | 21 |
| `n_laps` | int64 | 100.0% | 838 |
| `race_pace_adj` | float64 | 100.0% | -0.011 |
| `race_pace_adj_sd` | float64 | 100.0% | 0.115 |
| `race_pace_adj_lo` | float64 | 100.0% | -0.2002 |
| `race_pace_adj_hi` | float64 | 100.0% | 0.1782 |
| `race_pace_raw` | float64 | 100.0% | 0.4518 |
| `team_effect` | float64 | 100.0% | 0.7887 |
| `team_effect_sd` | float64 | 100.0% | 0.2542 |
| `teammate_gap_race` | float64 | 100.0% | -0.6425 |
| `teammate_gap_race_lo` | float64 | 97.3% | -0.7298 |
| `teammate_gap_race_hi` | float64 | 97.3% | -0.5061 |
| `n_teammate_races` | int64 | 100.0% | 20 |
| `consistency_sd` | float64 | 100.0% | 0.4704 |
| `consistency_lo` | float64 | 97.3% | 0.3987 |
| `consistency_hi` | float64 | 97.3% | 0.5035 |
| `quali_adj` | float64 | 100.0% | -0.0459 |
| `quali_adj_sd` | float64 | 100.0% | 0.1394 |
| `quali_gap_median` | float64 | 100.0% | 2.5986 |
| `quali_teammate_gap` | float64 | 100.0% | -0.7032 |
| `quali_teammate_gap_lo` | float64 | 96.4% | -1.1096 |
| `quali_teammate_gap_hi` | float64 | 96.4% | -0.4053 |
| `n_quali` | int64 | 100.0% | 17 |
| `n_quali_teammate` | int64 | 100.0% | 17 |
| `lap1_gain_mean` | float64 | 100.0% | 0.7895 |
| `n_lap1` | int64 | 100.0% | 19 |
| `positions_gained_mean` | float64 | 100.0% | 2.6471 |
| `n_classified` | int64 | 100.0% | 17 |
| `outcome_collision_or_accident` | int64 | 100.0% | 4 |
| `outcome_damage_unspecified` | int64 | 100.0% | 0 |
| `outcome_did_not_start` | int64 | 100.0% | 0 |
| `outcome_disqualified_or_technical_infringement` | int64 | 100.0% | 0 |
| `outcome_finished` | int64 | 100.0% | 16 |
| `outcome_mechanical_or_reliability` | int64 | 100.0% | 1 |
| `outcome_other` | int64 | 100.0% | 0 |
| `outcome_tyre_or_puncture` | int64 | 100.0% | 0 |
| `outcome_unspecified` | int64 | 100.0% | 0 |
| `outcome_withdrawn_or_health` | int64 | 100.0% | 0 |
| `race_pace_adj_pctile` | float64 | 95.5% | 47.3684 |
| `consistency_pctile` | float64 | 95.5% | 47.3684 |
| `quali_adj_pctile` | float64 | 95.5% | 57.8947 |
| `rank_reference` | object | 100.0% | drivers of the same season with >= 5 dry… |

### `driver_condition_effects` — 158 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `driver_id` | object | 100.0% | alexander-albon |
| `raw` | float64 | 100.0% | 0.0291 |
| `n_sessions` | int64 | 100.0% | 7 |
| `n_laps` | int64 | 100.0% | 122 |
| `posterior_mean` | float64 | 100.0% | 0.0066 |
| `posterior_sd` | float64 | 100.0% | 0.125 |
| `tau` | float64 | 100.0% | 0.1421 |
| `raw_se` | float64 | 100.0% | 0.2635 |
| `dimension` | object | 100.0% | wet_race |
| `status` | object | 100.0% | not_distinguishable_from_zero |
| `unit` | object | 100.0% | % of lap |
| `seasons` | object | 100.0% | 2022-2026 |

### `driver_session_adjusted` — 2,637 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `driver_id` | object | 100.0% | alexander-albon |
| `adj_pace` | float64 | 100.0% | 1.1968 |
| `se` | float64 | 100.0% | 0.1689 |
| `n_laps` | int64 | 100.0% | 43 |
| `resid_robust_sd` | float64 | 100.0% | 0.4704 |
| `ref_compound` | object | 100.0% | SOFT |
| `adjusted_for` | object | 100.0% | compound+age+lap |
| `fuel_slope_pct_per_lap` | float64 | 83.4% | -0.0852 |
| `ar1_rho` | float64 | 100.0% | 0.4151 |
| `deg_soft_pct_per_lap` | float64 | 64.5% | 0.1808 |
| `deg_medium_pct_per_lap` | float64 | 92.2% | 0.1477 |
| `deg_hard_pct_per_lap` | float64 | 76.8% | 0.1585 |
| `constructor_id` | object | 100.0% | williams |
| `session_id` | object | 100.0% | 2022-01-R |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `session_code` | object | 100.0% | R |
| `circuit_id` | object | 100.0% | bahrain |
| `condition` | object | 100.0% | dry |
| `wet_share` | float64 | 100.0% | 0.0 |
| `date` | datetime64[ns] | 100.0% | 2022-03-20 00:00:00 |
| `deg_intermediate_pct_per_lap` | float64 | 6.3% | 0.0544 |
| `deg_wet_pct_per_lap` | float64 | 0.7% | 0.2264 |
| `teammate_gap` | float64 | 95.3% | -0.6445 |

### `team_season_effects` — 51 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `level` | object | 100.0% | alfa-romeo:2022 |
| `estimate` | float64 | 100.0% | 0.0935 |
| `pev` | float64 | 100.0% | 0.0704 |

### `driver_clusters` — 103 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `driver_id` | object | 100.0% | alexander-albon |
| `season` | int64 | 100.0% | 2022 |
| `main_team` | object | 100.0% | williams |
| `pc1` | float64 | 100.0% | -1.9557 |
| `pc2` | float64 | 100.0% | 1.3643 |
| `cluster` | int32 | 100.0% | 0 |

### `corner_definitions` — 1,391 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `corner_id` | object | 100.0% | T1-T2-T3 |
| `labels` | object | 100.0% | ['T1' 'T2' 'T3'] |
| `method` | object | 100.0% | marker |
| `n_markers` | int64 | 100.0% | 3 |
| `entry_s` | float64 | 100.0% | 538.0 |
| `apex_s` | float64 | 100.0% | 726.0 |
| `exit_s` | float64 | 100.0% | 1208.0 |
| `length_m` | float64 | 100.0% | 670.0 |
| `anchor_s` | float64 | 100.0% | 710.0 |
| `heading_change_deg` | float64 | 100.0% | -99.7684 |
| `direction` | object | 100.0% | right |
| `alternating` | bool | 100.0% | True |
| `entry_speed_ref` | float64 | 100.0% | 318.0 |
| `min_speed_ref` | float64 | 100.0% | 70.0 |
| `exit_speed_ref` | float64 | 100.0% | 286.7238 |
| `min_throttle_ref` | float64 | 100.0% | 0.0 |
| `x` | float64 | 100.0% | 18.7967 |
| `y` | float64 | 100.0% | 833.1122 |
| `category` | object | 100.0% | slow |
| `is_hairpin` | bool | 100.0% | False |
| `is_chicane` | bool | 100.0% | False |
| `is_esses` | bool | 100.0% | True |
| `is_sweeper` | bool | 100.0% | False |
| `is_sequence` | bool | 100.0% | False |
| `approx_radius_m` | float64 | 100.0% | 384.7728 |
| `sector` | int64 | 100.0% | 1 |
| `session_id` | object | 100.0% | 2022-01-Q |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `session_code` | object | 100.0% | Q |

### `corner_metrics` — 27,684 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `corner_id` | object | 100.0% | T1-T2-T3 |
| `segment_time_s` | float64 | 100.0% | 13.0507 |
| `entry_speed_kph` | float64 | 100.0% | 318.0 |
| `min_speed_kph` | float64 | 100.0% | 70.0 |
| `exit_speed_kph` | float64 | 100.0% | 286.7238 |
| `min_speed_s` | float64 | 100.0% | 726.0 |
| `brake_onset_before_apex_m` | float64 | 62.7% | 116.0 |
| `braking_duration_s` | float64 | 100.0% | 2.879 |
| `full_throttle_delay_s` | float64 | 88.3% | 3.641 |
| `full_throttle_after_apex_m` | float64 | 88.3% | 122.0 |
| `min_gear` | float64 | 100.0% | 2.0 |
| `gear_changes` | int64 | 100.0% | 9 |
| `max_decel_proxy_ms2` | float64 | 100.0% | 61.6319 |
| `n_samples` | int64 | 100.0% | 97 |
| `max_sample_gap_s` | float64 | 100.0% | 0.426 |
| `quality` | object | 100.0% | ok |
| `driver_id` | object | 100.0% | charles-leclerc |
| `constructor_id` | object | 100.0% | ferrari |
| `lap_number` | int64 | 100.0% | 14 |
| `lap_time_s` | float64 | 100.0% | 90.558 |
| `compound` | object | 100.0% | SOFT |
| `lap_session_time_s` | float64 | 100.0% | 4487.968 |
| `quali_segment` | object | 92.2% | Q3 |
| `session_id` | object | 100.0% | 2022-01-Q |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `session_code` | object | 100.0% | Q |
| `delta_to_best_s` | float64 | 100.0% | 0.0721 |
| `teammate_comparable` | bool | 100.0% | True |
| `delta_to_teammate_s` | float64 | 42.0% | 0.0115 |
| `min_speed_delta_to_teammate_kph` | float64 | 42.0% | -2.0 |
| `category` | object | 100.0% | slow |
| `is_hairpin` | bool | 100.0% | False |
| `is_chicane` | bool | 100.0% | False |
| `is_sweeper` | bool | 100.0% | False |
| `method` | object | 100.0% | marker |
| `sector` | int64 | 100.0% | 1 |

### `driver_corner_profiles` — 325 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `driver_id` | object | 100.0% | alexander-albon |
| `season` | int64 | 100.0% | 2022 |
| `category` | object | 100.0% | fast |
| `delta_pct` | float64 | 100.0% | -0.6061 |
| `ci_lo` | float64 | 93.2% | -2.6329 |
| `ci_hi` | float64 | 93.2% | 0.9061 |
| `min_speed_delta_kph` | float64 | 100.0% | -3.3026 |
| `n_sessions` | int64 | 100.0% | 7 |
| `n_corners` | int64 | 100.0% | 21 |

### `circuit_profiles` — 27 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `circuit_id` | object | 100.0% | austin |
| `circuit_layout_id` | object | 100.0% | austin-1 |
| `reference_session` | object | 100.0% | 2026-18-Q |
| `n_sessions` | int64 | 100.0% | 5 |
| `n_corners` | int64 | 100.0% | 16 |
| `n_flat_out` | int64 | 100.0% | 5 |
| `circuit_frac_slow` | float64 | 100.0% | 0.5455 |
| `circuit_frac_medium` | float64 | 100.0% | 0.1818 |
| `circuit_frac_fast` | float64 | 100.0% | 0.2727 |
| `circuit_full_throttle_frac` | float64 | 100.0% | 0.6528 |
| `mean_min_speed_kph` | float64 | 100.0% | 141.3062 |
| `length_m` | float64 | 100.0% | 5426.0 |
| `marker_precision` | float64 | 92.6% | 1.0 |
| `marker_recall` | float64 | 92.6% | 0.9 |

### `sector_profiles` — 330 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-Q |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `session_code` | object | 100.0% | Q |
| `sector` | int64 | 100.0% | 1 |
| `start_s` | float64 | 100.0% | 0.0 |
| `end_s` | float64 | 100.0% | 1761.0574 |
| `length_m` | float64 | 100.0% | 1761.0574 |
| `n_corners` | int64 | 100.0% | 2 |
| `frac_slow` | float64 | 100.0% | 1.0 |
| `frac_medium` | float64 | 100.0% | 0.0 |
| `frac_fast` | float64 | 100.0% | 0.0 |
| `full_throttle_frac` | float64 | 100.0% | 0.748 |
| `boundary_laps` | int64 | 100.0% | 20 |

### `track_maps` — 56,448 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `s` | float64 | 100.0% | 0.0 |
| `x` | float64 | 100.0% | -38.0145 |
| `y` | float64 | 100.0% | 128.343 |
| `speed_ref` | float64 | 100.0% | 292.7333 |
| `throttle_ref` | float64 | 100.0% | 100.0 |
| `session_id` | object | 100.0% | 2022-01-Q |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `session_code` | object | 100.0% | Q |

### `tyre_stints` — 5,058 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `session_id` | object | 100.0% | 2022-01-R |
| `event_id` | object | 100.0% | 2022-01 |
| `season` | int64 | 100.0% | 2022 |
| `session_code` | object | 100.0% | R |
| `driver_id` | object | 100.0% | alexander-albon |
| `constructor_id` | object | 100.0% | williams |
| `stint` | int64 | 100.0% | 1 |
| `compound` | object | 100.0% | SOFT |
| `n_laps` | int64 | 100.0% | 11 |
| `age_min` | float64 | 100.0% | 2.0 |
| `age_max` | float64 | 100.0% | 12.0 |
| `fresh` | bool | 100.0% | True |
| `slope_pct` | float64 | 100.0% | 0.3203 |
| `slope_se` | float64 | 100.0% | 0.0563 |
| `level_at_age0` | float64 | 100.0% | -1.1884 |
| `track_temp_c` | float64 | 100.0% | 28.3545 |
| `fuel_slope` | float64 | 100.0% | -0.0852 |
| `session_ref_s` | float64 | 100.0% | 99.3225 |
| `date` | datetime64[ns] | 100.0% | 2022-03-20 00:00:00 |
| `circuit_id` | object | 100.0% | bahrain |

### `tyre_degradation` — 15 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `season` | int64 | 100.0% | 2022 |
| `compound` | object | 100.0% | HARD |
| `slope_pct` | float64 | 100.0% | 0.0411 |
| `ci_lo` | float64 | 100.0% | 0.0295 |
| `ci_hi` | float64 | 100.0% | 0.0558 |
| `n_stints` | int64 | 100.0% | 279 |
| `n_sessions` | int64 | 100.0% | 20 |
| `slope_s_per_lap` | float64 | 100.0% | 0.0375 |

### `tyre_degradation_circuit` — 79 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `circuit_id` | object | 100.0% | austin |
| `compound` | object | 100.0% | HARD |
| `slope_pct` | float64 | 100.0% | 0.0488 |
| `ci_lo` | float64 | 79.7% | 0.0326 |
| `ci_hi` | float64 | 79.7% | 0.0649 |
| `n_stints` | int64 | 100.0% | 83 |
| `n_sessions` | int64 | 100.0% | 5 |

### `driver_tyre_effects` — 329 rows

| Column | Type | Non-null | Example |
|---|---|---|---|
| `driver_id` | object | 100.0% | alexander-albon |
| `season` | int64 | 100.0% | 2022 |
| `raw` | float64 | 100.0% | 0.0016 |
| `n_stints` | int64 | 100.0% | 12 |
| `n_sessions` | int64 | 100.0% | 10 |
| `posterior_mean` | float64 | 100.0% | 0.0004 |
| `posterior_sd` | float64 | 100.0% | 0.0074 |
| `tau` | float64 | 100.0% | 0.0083 |
| `raw_se` | float64 | 100.0% | 0.0157 |
| `compound` | object | 100.0% | HARD |
| `status` | object | 100.0% | not_distinguishable_from_zero |

