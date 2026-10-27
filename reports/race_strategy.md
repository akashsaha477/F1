# Race strategy planner — backtest

_Generated 2026-10-27 07:52 UTC by `scripts/generate_reports.py` from `evaluation_runs/strategy_backtest.json`. Do not edit by hand; re-run the script._

Every race from the second ingested season on is planned with data available before its start (strategy parameters from earlier races, a lap-pace model trained on earlier seasons, weather from the weekend's sessions) and compared with what happened. Method: `docs/methodology.md` §6, code: `src/apexlens/strategy/`.

70 races; 57 dry races without a red flag are used for the strategy comparison (excluded: wet 2023-06, 2023-13, 2024-09, 2024-12, 2024-21, 2025-01, 2025-12, 2025-13; red flag 2023-03, 2023-19, 2023-20, 2024-04, 2024-08).

## All evaluated races (57 races)

| Measure | Planner (lap-time costs only) | Planner (calibrated) | Copy previous race here | Most common stop count so far |
|---|---|---|---|---|
| Stop count = top-10's most common | 58% [46, 70] | 60% [47, 72] | 61% [47, 73] | 40% [28, 53] |
| Stops + set of compounds = top-10's most common | 28% [18, 39] | 40% [28, 54] | 45% [31, 59] | – |
| Starting compound = top-10's most common | 68% [56, 79] | 84% [74, 93] | 96% [90, 100] | – |
| Stop count = winner's | 60% [47, 72] | 61% [49, 74] | – | – |
| First stop vs top-10 with that stop count (laps) | 5.30 [3.93, 6.92] | 5.49 [4.23, 7.00] | 5.77 [3.72, 8.20] | – |
| Top-10 first stops inside the planned window | 38% [27, 49] | 47% [36, 57] | – | – |

| Paired difference (same races) | Estimate [95% CI] |
|---|---|
| calibrated − previous race: stops match | -0.020 [-0.163, +0.143] |
| calibrated − previous race: plan match | -0.061 [-0.224, +0.102] |
| calibrated − previous race: start match | -0.143 [-0.265, -0.041] * |
| calibrated − physical: stops match | +0.018 [-0.053, +0.105] |
| calibrated − physical: plan match | +0.123 [+0.000, +0.246] |
| calibrated − physical: start match | +0.158 [+0.018, +0.298] * |
| calibrated − physical: first stop error | +0.295 [-0.830, +1.534] |

## Races without safety car or VSC (22 races)

| Measure | Planner (lap-time costs only) | Planner (calibrated) | Copy previous race here | Most common stop count so far |
|---|---|---|---|---|
| Stop count = top-10's most common | 59% [36, 77] | 64% [45, 82] | 62% [43, 81] | 41% [23, 59] |
| Stops + set of compounds = top-10's most common | 27% [9, 45] | 41% [23, 59] | 43% [24, 62] | – |
| Starting compound = top-10's most common | 77% [59, 95] | 91% [77, 100] | 95% [86, 100] | – |
| Stop count = winner's | 64% [41, 82] | 68% [50, 86] | – | – |
| First stop vs top-10 with that stop count (laps) | 4.71 [3.18, 6.21] | 4.83 [3.33, 6.39] | 3.19 [2.04, 4.46] | – |
| Top-10 first stops inside the planned window | 37% [24, 52] | 50% [36, 64] | – | – |

| Paired difference (same races) | Estimate [95% CI] |
|---|---|
| calibrated − previous race: stops match | +0.000 [-0.238, +0.238] |
| calibrated − previous race: plan match | -0.048 [-0.286, +0.190] |
| calibrated − previous race: start match | -0.048 [-0.190, +0.095] |
| calibrated − physical: stops match | +0.045 [+0.000, +0.136] |
| calibrated − physical: plan match | +0.136 [-0.091, +0.364] |
| calibrated − physical: start match | +0.136 [-0.091, +0.364] |
| calibrated − physical: first stop error | +0.294 [-0.882, +1.706] |

## Races with a safety car or VSC (35 races)

| Measure | Planner (lap-time costs only) | Planner (calibrated) | Copy previous race here | Most common stop count so far |
|---|---|---|---|---|
| Stop count = top-10's most common | 57% [40, 74] | 57% [40, 71] | 61% [43, 79] | 40% [26, 57] |
| Stops + set of compounds = top-10's most common | 29% [14, 46] | 40% [23, 57] | 46% [29, 64] | – |
| Starting compound = top-10's most common | 63% [49, 80] | 80% [66, 91] | 96% [89, 100] | – |
| Stop count = winner's | 57% [40, 74] | 57% [40, 71] | – | – |
| First stop vs top-10 with that stop count (laps) | 5.67 [3.74, 7.67] | 5.91 [4.02, 8.14] | 7.75 [4.32, 11.38] | – |
| Top-10 first stops inside the planned window | 39% [25, 54] | 45% [30, 60] | – | – |

| Paired difference (same races) | Estimate [95% CI] |
|---|---|
| calibrated − previous race: stops match | -0.036 [-0.250, +0.179] |
| calibrated − previous race: plan match | -0.071 [-0.286, +0.143] |
| calibrated − previous race: start match | -0.214 [-0.357, -0.071] * |
| calibrated − physical: stops match | +0.000 [-0.114, +0.114] |
| calibrated − physical: plan match | +0.114 [-0.029, +0.257] |
| calibrated − physical: start match | +0.171 [-0.029, +0.343] |
| calibrated − physical: first stop error | +0.296 [-1.352, +2.370] |

## Calibration

Hidden costs fitted on earlier races (latest fit, 56 races): 10.0 s per pit stop (track position, traffic) and 27.5 s per SOFT stint (set availability after qualifying, graining). Agreement with the top-10's most common plan on those races: 54.5%.

## Finishing order

| Prediction | Rank correlation | Winner correct | Podium overlap | Position error |
|---|---|---|---|---|
| Planner (grid + pace blend) | 0.78 [0.74, 0.81] | 57% [46, 69] | 66% [60, 72] | 2.37 [2.21, 2.54] |
| Grid order | 0.74 [0.70, 0.79] | 63% [51, 74] | 71% [66, 77] | 2.52 [2.30, 2.72] |
| Pace order | 0.76 [0.72, 0.80] | 57% [46, 69] | 63% [57, 69] | 2.49 [2.32, 2.67] |

Blend − grid order, rank correlation: +0.038 [+0.016, +0.060] *. Classified finishers only.

## Lap times

The top-10's actual tyre sequences replayed through the model (570 driver-races, 28,507 representative laps): mean absolute error 2.87 [1.95, 3.95] s per lap vs 3.08 [2.16, 4.13] s for a constant lap time at the predicted pace (difference -0.207 [-0.277, -0.129] *). Most of the remaining error is the level of the race's lap times (estimated from qualifying), not the shape over the race.

## Temperature

Adding a within-circuit track-temperature adjustment to the degradation slopes changed held-out stint predictions by +0.1052 [+0.0452, +0.1749] * % points (positive = worse), so the planner does not adjust tyre wear for temperature.

## Race by race

| Race | Circuit | Planned (calibrated) | Top-10 most common | Winner | Match | Neutralised |
|---|---|---|---|---|---|---|
| 2023-01 | bahrain | S-S-H (2 stops) | 2 stop(s): HARD+SOFT | S-S-H (2 stops) | yes | SC/VSC |
| 2023-02 | jeddah | S-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | no | SC/VSC |
| 2023-03 | melbourne | M-H (1 stop) | – | – | not evaluated | SC/VSC |
| 2023-04 | baku | H-S (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | no | SC/VSC |
| 2023-05 | miami | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | H-M (1 stop) | yes |  |
| 2023-06 | monaco | M-H (1 stop) | – | – | not evaluated |  |
| 2023-07 | catalunya | S-S-M (2 stops) | 2 stop(s): HARD+MEDIUM+SOFT | M-H-S (2 stops) | no |  |
| 2023-08 | montreal | M-H (1 stop) | 2 stop(s): HARD+MEDIUM | M-H-M (2 stops) | no | SC/VSC |
| 2023-09 | spielberg | M-S-M (2 stops) | 3 stop(s): HARD+MEDIUM | M-M-H-M-S (4 stops) | no | SC/VSC |
| 2023-10 | silverstone | M-H (1 stop) | 1 stop(s): MEDIUM+SOFT | M-S (1 stop) | no | SC/VSC |
| 2023-11 | hungaroring | M-S-M (2 stops) | 2 stop(s): HARD+MEDIUM | M-H-M (2 stops) | no |  |
| 2023-12 | spa-francorchamps | M-M-H (2 stops) | 2 stop(s): MEDIUM+SOFT | S-M-S (2 stops) | no |  |
| 2023-13 | zandvoort | M-H-H (2 stops) | – | – | not evaluated | SC/VSC |
| 2023-14 | monza | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes |  |
| 2023-15 | marina-bay | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes | SC/VSC |
| 2023-16 | suzuka | M-H (1 stop) | 2 stop(s): HARD+MEDIUM | M-M-H (2 stops) | no | SC/VSC |
| 2023-17 | lusail | M-M-M-H (3 stops) | 3 stop(s): HARD+MEDIUM | M-M-H-M (3 stops) | yes | SC/VSC |
| 2023-18 | austin | M-M-H (2 stops) | 2 stop(s): HARD+MEDIUM | M-M-H (2 stops) | yes |  |
| 2023-19 | mexico-city | M-H (1 stop) | – | – | not evaluated | SC/VSC |
| 2023-20 | interlagos | M-H-M (2 stops) | – | – | not evaluated | SC/VSC |
| 2023-21 | las-vegas | M-H (1 stop) | 2 stop(s): HARD+MEDIUM | M-H-H (2 stops) | no | SC/VSC |
| 2023-22 | yas-marina | M-H (1 stop) | 2 stop(s): HARD+MEDIUM | M-H-H (2 stops) | no |  |
| 2024-01 | bahrain | M-H-H (2 stops) | 2 stop(s): HARD+SOFT | S-H-S (2 stops) | no |  |
| 2024-02 | jeddah | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes | SC/VSC |
| 2024-03 | melbourne | M-H (1 stop) | 2 stop(s): HARD+MEDIUM | M-H-H (2 stops) | no | SC/VSC |
| 2024-04 | suzuka | M-H-H (2 stops) | – | – | not evaluated |  |
| 2024-05 | shanghai | M-H (1 stop) | 2 stop(s): HARD+MEDIUM | M-H-H (2 stops) | no | SC/VSC |
| 2024-06 | miami | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes | SC/VSC |
| 2024-07 | imola | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes |  |
| 2024-08 | monaco | M-H (1 stop) | – | – | not evaluated | SC/VSC |
| 2024-09 | montreal | M-H (1 stop) | – | – | not evaluated | SC/VSC |
| 2024-10 | catalunya | M-H-H (2 stops) | 2 stop(s): MEDIUM+SOFT | S-M-S (2 stops) | no |  |
| 2024-11 | spielberg | M-M-H (2 stops) | 2 stop(s): HARD+MEDIUM | M-M-H (2 stops) | yes | SC/VSC |
| 2024-12 | silverstone | M-H (1 stop) | – | – | not evaluated |  |
| 2024-13 | hungaroring | M-M-H (2 stops) | 2 stop(s): HARD+MEDIUM | M-H-M (2 stops) | yes |  |
| 2024-14 | spa-francorchamps | M-M-H (2 stops) | 2 stop(s): HARD+MEDIUM | M-H-H (2 stops) | yes |  |
| 2024-15 | zandvoort | M-H-H (2 stops) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | no |  |
| 2024-16 | monza | M-H (1 stop) | 2 stop(s): HARD+MEDIUM | M-H (1 stop) | no |  |
| 2024-17 | baku | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes | SC/VSC |
| 2024-18 | marina-bay | M-S-M (2 stops) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | no |  |
| 2024-19 | austin | M-M-H (2 stops) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | no | SC/VSC |
| 2024-20 | mexico-city | M-M-H (2 stops) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | no | SC/VSC |
| 2024-21 | interlagos | S-M-M (2 stops) | – | – | not evaluated | SC/VSC |
| 2024-22 | las-vegas | M-H (1 stop) | 2 stop(s): HARD+MEDIUM | M-H-H (2 stops) | no |  |
| 2024-23 | lusail | S-H-H (2 stops) | 3 stop(s): HARD+MEDIUM | M-H-H-H (3 stops) | no | SC/VSC |
| 2024-24 | yas-marina | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes | SC/VSC |
| 2025-01 | melbourne | M-H (1 stop) | – | – | not evaluated | SC/VSC |
| 2025-02 | shanghai | M-H-H (2 stops) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | no |  |
| 2025-03 | suzuka | M-M-H (2 stops) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | no |  |
| 2025-04 | bahrain | M-H-H (2 stops) | 2 stop(s): MEDIUM+SOFT | S-M-M (2 stops) | no | SC/VSC |
| 2025-05 | jeddah | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes | SC/VSC |
| 2025-06 | miami | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes | SC/VSC |
| 2025-07 | imola | M-H (1 stop) | 2 stop(s): HARD+MEDIUM | M-H-H (2 stops) | no | SC/VSC |
| 2025-08 | monaco | M-H-H (2 stops) | 2 stop(s): HARD+MEDIUM | M-H-H (2 stops) | yes | SC/VSC |
| 2025-09 | catalunya | M-M-H (2 stops) | 3 stop(s): MEDIUM+SOFT | S-M-S-S (3 stops) | no | SC/VSC |
| 2025-10 | montreal | M-H (1 stop) | 5 stop(s): HARD+MEDIUM | M-H-H-H-H-H (5 stops) | no | SC/VSC |
| 2025-11 | spielberg | M-M-H (2 stops) | 2 stop(s): HARD+MEDIUM | M-H-M (2 stops) | yes | SC/VSC |
| 2025-12 | silverstone | M-H (1 stop) | – | – | not evaluated | SC/VSC |
| 2025-13 | spa-francorchamps | M-H-H (2 stops) | – | – | not evaluated | SC/VSC |
| 2025-14 | hungaroring | M-M-H (2 stops) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | no |  |
| 2025-15 | zandvoort | M-H (1 stop) | 2 stop(s): HARD+MEDIUM | M-H-H (2 stops) | no | SC/VSC |
| 2025-16 | monza | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes |  |
| 2025-17 | baku | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | H-M (1 stop) | yes | SC/VSC |
| 2025-18 | marina-bay | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes |  |
| 2025-19 | austin | M-H (1 stop) | 1 stop(s): MEDIUM+SOFT | M-S (1 stop) | no | SC/VSC |
| 2025-20 | mexico-city | M-H (1 stop) | 1 stop(s): MEDIUM+SOFT | S-M (1 stop) | no | SC/VSC |
| 2025-21 | interlagos | M-H (1 stop) | 2 stop(s): MEDIUM+SOFT | M-S-M (2 stops) | no | SC/VSC |
| 2025-22 | las-vegas | M-H-H (2 stops) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | no | SC/VSC |
| 2025-23 | lusail | M-H-H (2 stops) | 2 stop(s): HARD+MEDIUM | M-M-H (2 stops) | yes | SC/VSC |
| 2025-24 | yas-marina | M-H (1 stop) | 1 stop(s): HARD+MEDIUM | M-H (1 stop) | yes |  |
