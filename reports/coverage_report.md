# Data coverage report

Generated: 2026-10-26T18:57:15+00:00 (by `apexlens coverage`)

## Sources

| Source | Seasons | Licence / status |
|---|---|---|
| f1db | [1950, 2026] | CC BY 4.0 (attribution required) |
| tracinginsights | [2022, 2023, 2024, 2025] | Repositories declare the MIT licence. Timing/telemetry originates from the Formula 1 live timing service via FastF1 and is unofficial; use for non-commercial research. |
| fastf1 | [] | adapter implemented; host unreachable from build environment |
| jolpica | [] | adapter implemented; host unreachable from build environment |
| openf1 | [] | adapter implemented; host unreachable from build environment |

## Per season (lap-level sources)

| Season | F1DB sessions | Sessions with timing | % | Laps | Clean laps | % valid tyre | % weather | Q/SQ sessions w/ telemetry | Telemetry laps | Wet clean laps | Sessions w/ wet running |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | 110 | 110 | 100.0 | 59565 | 38129 | 97.2 | 100.0 | 22 (100.0%) | 435 | 2666 | 18 |
| 2023 | 110 | 110 | 100.0 | 59097 | 38666 | 98.2 | 99.4 | 28 (100.0%) | 555 | 2185 | 18 |
| 2024 | 120 | 120 | 100.0 | 64043 | 42973 | 99.0 | 100.0 | 30 (100.0%) | 594 | 2460 | 15 |
| 2025 | 120 | 120 | 100.0 | 65655 | 41832 | 99.1 | 99.7 | 30 (100.0%) | 594 | 1281 | 7 |

## Supported analyses

| Analysis | Supported | Evidence | Limitation |
|---|---|---|---|
| Historical results-only driver profiles | yes | F1DB seasons [1950, 2026] |  |
| Lap-time / relative pace modelling | yes | 161600 clean laps in 460 sessions |  |
| Tyre degradation (compound, tyre age, stints) | yes | compound and tyre age per lap available |  |
| Wet-weather performance | yes | 8592 clean laps on intermediate/wet tyres; sparse and confounded | Evidence is sparse; estimates are shrunk and many drivers return insufficient evidence. |
| Corner-level telemetry analysis | yes | 2178 telemetry laps (bounded: fastest qualifying laps) | Race-lap telemetry is not ingested by default; corner metrics describe qualifying laps. |
| Overtakes | no | Only OpenF1 provides overtakes; host unreachable from the build environment | Position changes are derived from grid vs. finish and lap positions instead. |
| Steering / brake pressure / tyre force | no | Not present in any source (brake is on/off only) |  |

## Data quality

| Check | Severity | Rows flagged |
|---|---|---|
| coordinate_discontinuity | warning | 2 |
| duplicate_laps | fatal | 129 |
| implausible_lap_time | warning | 183 |
| missing_lap_start_timestamp | warning | 170 |
| sample_gap | warning | 443 |
| sector_sum_mismatch | warning | 96 |
| session_time_not_increasing | warning | 21 |
| unresolved_driver_identity | fatal | 130 |
| weather_time_not_increasing | warning | 143 |

Partitions with fatal failures: 1
- `2023-11-FP1`: duplicate_laps, unresolved_driver_identity

## Entity mapping

Driver-session pairs resolved: 9160; methods: {'session_number': 9159, 'unresolved': 1}
Unresolved driver pairs: 1; unresolved events: 0

## Requests

Items: 4563, errors: 0, missing (404): 3
Missing by dataset: {'lap_telemetry': 3}

## Driver × circuit × condition coverage (clean race/sprint laps)

- Driver-circuit pairs: 1793
- With clean dry laps: 1761
- With clean wet laps: 284
- Driver-seasons without any clean wet race lap: 3 of 89
