# Feature definitions

_Generated 2026-10-26 18:57 UTC by `scripts/generate_reports.py` from `src/apexlens/features/definitions.py`. Do not edit by hand; re-run the script._

Each feature with its meaning, unit, derivation, sources, availability and known limitations. Availability: `static` (known before the season), `pre_event` (only events that finished before the event's first session), `pre_race` (adds the same weekend's qualifying), `scenario` (a condition set by the user or observed on the lap), `target` (never an input).

## Target

| Feature | Unit | Availability | Description | Derivation | Sources | Limitations |
|---|---|---|---|---|---|---|
| `rel_pace_pct` | % of session reference | target | Lap time relative to the session reference: 100 * (lap / reference - 1). Negative is faster. | reference = median of all clean laps of all drivers in the same session | tracinginsights | Field composition shifts the reference slightly. |

## Driver

| Feature | Unit | Availability | Description | Derivation | Sources | Limitations |
|---|---|---|---|---|---|---|
| `drv_form_pace` | % | pre_event | Driver's exponentially weighted race pace over previous events | EWMA (half-life 4 events) of the driver's median representative-lap rel_pace_pct in previous races/sprints, strictly before the event | tracinginsights | Mixes driver and car performance. |
| `drv_form_n` | events | pre_event | Number of previous dry events contributing to drv_form_pace (capped at 10) | count of previous events, capped at 10 because the EWMA is saturated by then | tracinginsights | Counts only events inside the ingested seasons. |
| `drv_teammate_gap_form` | % | pre_event | Driver's EWMA race-pace gap to the team-mate in previous events | median rel pace minus team-mate's, previous events only | tracinginsights | Team-mates may run different strategies or setups. |
| `drv_quali_form` | % gap to pole | pre_event | Driver's EWMA qualifying gap to pole in previous events | F1DB best qualifying time / pole time - 1 | f1db | Q1 eliminees have fewer runs and less track evolution. |

## Interaction

| Feature | Unit | Availability | Description | Derivation | Sources | Limitations |
|---|---|---|---|---|---|---|
| `drv_circuit_hist` | % | pre_event | Driver's mean race pace at this circuit in previous seasons minus their season form at the time (driver x circuit interaction history) | previous seasons only; NaN when the driver has no history at the circuit | tracinginsights | At most a few observations per pair. |

## Team

| Feature | Unit | Availability | Description | Derivation | Sources | Limitations |
|---|---|---|---|---|---|---|
| `team_form_pace` | % | pre_event | Constructor's EWMA race pace (mean of its drivers) over previous events | EWMA half-life 4 events across seasons | tracinginsights | Car changes between seasons are only captured by team_season_events. |
| `team_season_form` | % | pre_event | Constructor's mean race pace over previous events of the same season | expanding mean, NaN at the first event of a season | tracinginsights |  |
| `team_season_events` | events | pre_event | Previous events of the constructor in this season | count | tracinginsights |  |
| `team_quali_form` | % gap to pole | pre_event | Constructor's EWMA qualifying gap to pole | F1DB qualifying | f1db |  |

## Weekend

| Feature | Unit | Availability | Description | Derivation | Sources | Limitations |
|---|---|---|---|---|---|---|
| `evt_quali_gap` | % gap to pole | pre_race | Driver's qualifying gap to pole at this event | F1DB qualifying | f1db | Only valid for a pre-race (post-qualifying) horizon. |
| `evt_team_quali_gap` | % gap to pole | pre_race | Mean qualifying gap of the constructor's drivers at this event | F1DB qualifying | f1db | Pre-race horizon only. |

## Track

| Feature | Unit | Availability | Description | Derivation | Sources | Limitations |
|---|---|---|---|---|---|---|
| `circuit_length_km` | km | static | Lap length | F1DB course length | f1db |  |
| `circuit_turns` | count | static | Number of turns | F1DB | f1db |  |
| `circuit_is_street` | bool | static | Street circuit | F1DB circuit type == STREET | f1db |  |
| `circuit_ref_lap_s` | s | pre_event | Median clean race lap at this circuit in previous seasons | previous seasons only | tracinginsights | NaN for circuits new to the dataset. |
| `circuit_frac_slow` | fraction | static | Share of identified corners classified slow (< 125 km/h minimum speed) | Corner analysis of qualifying telemetry (track property) | tracinginsights | Corner speeds depend on the car generation; treated as a static descriptor. |
| `circuit_frac_fast` | fraction | static | Share of identified corners classified fast (>= 200 km/h minimum speed) | as circuit_frac_slow | tracinginsights | as above |
| `circuit_full_throttle_frac` | fraction | static | Share of lap distance at >= 98% throttle on reference laps | qualifying telemetry | tracinginsights | as above |

## Tyre

| Feature | Unit | Availability | Description | Derivation | Sources | Limitations |
|---|---|---|---|---|---|---|
| `compound` | category | scenario | Normalised compound (SOFT/MEDIUM/HARD/INTERMEDIATE/WET) | source compound string | tracinginsights | SOFT/MEDIUM/HARD are relative names; the Pirelli C-number differs by event. |
| `tyre_life_laps` | laps | scenario | Tyre age at lap | FastF1 TyreLife | tracinginsights |  |
| `fresh_tyre` | bool | scenario | Set was new at fitting | FastF1 FreshTyre | tracinginsights |  |
| `stint` | count | scenario | Stint number | FastF1 Stint | tracinginsights |  |

## Weather

| Feature | Unit | Availability | Description | Derivation | Sources | Limitations |
|---|---|---|---|---|---|---|
| `track_temp_c` | °C | scenario | Track temperature | FastF1 weather sample joined to the lap | tracinginsights | One trackside sensor per circuit. |
| `air_temp_c` | °C | scenario | Air temperature | as track_temp_c | tracinginsights |  |
| `humidity_pct` | % | scenario | Relative humidity | as track_temp_c | tracinginsights |  |
| `rainfall` | bool | scenario | Rain detected | FastF1 Rainfall | tracinginsights | Binary; no intensity. |
| `is_wet_compound` | bool | scenario | Intermediate or full-wet tyre fitted | compound | tracinginsights |  |

## Race context

| Feature | Unit | Availability | Description | Derivation | Sources | Limitations |
|---|---|---|---|---|---|---|
| `race_progress` | fraction | scenario | Lap number / scheduled race distance (fuel-load proxy) | F1DB scheduled laps | f1db, tracinginsights | Fuel load is not observed; this is a proxy. |
| `lap_number` | lap | scenario | Lap number | FastF1 LapNumber | tracinginsights |  |
| `is_sprint` | bool | static | Sprint race session | session code | f1db |  |

