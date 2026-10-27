# Driver performance profiles

_Generated 2026-10-27 08:09 UTC by `scripts/generate_reports.py` from `gold/driver_profiles`, `gold/driver_condition_effects`, `gold/driver_clusters`. Do not edit by hand; re-run the script._

## Method

Stage 1 removes, per session, the effects of compound, compound-specific tyre age and lap number from each driver's representative laps (OLS; non-identifiable terms dropped in a fixed order). Stage 2 fits crossed random effects for driver, driver-season and team-season with session fixed effects by REML:

`adj_pace ~ session (fixed) + (1|driver) + (1|driver:season) + (1|team:season)`  
`quali_gap_pct ~ event (fixed) + (1|driver) + (1|driver:season) + (1|team:season); dry, gap <= 5.0%`

## Variance components (%²)

| Component | Race pace | share | Qualifying gap | share |
|---|---|---|---|---|
| driver | 0.077 | 10.8% | 0.126 | 13.9% |
| driver-season | 0.003 | 0.5% | 0.003 | 0.3% |
| team-season | 0.501 | 70.1% | 0.454 | 50.0% |
| residual | 0.133 | 18.6% | 0.326 | 35.9% |

Race model: 2,471 driver-sessions; qualifying model: 1,996 driver-sessions. Team-mate differences are directly identified. The split of a team-season's mean pace into car and driver components relies on drivers who changed teams and on the estimated variance components; cross-team driver comparisons are therefore less certain than the intervals of a single effect suggest.

## Team-adjusted race pace, 2026

![Team-adjusted race pace with intervals](figures/profiles_race_pace.png)

21 of 22 adjacent pairs in this ordering have overlapping intervals; the ordering is not a ranking with that precision. Drivers with few races are wide by construction.

| Driver | Team | Dry races + sprints | Adj. pace % | lo | hi | Gap to team-mate % | Quali gap to team-mate % |
|---|---|---|---|---|---|---|---|
| max-verstappen | red-bull | 21 | -0.824 | -1.010 | -0.638 | -0.672 | -0.166 |
| lando-norris | mclaren | 22 | -0.371 | -0.605 | -0.137 | -0.197 | -0.095 |
| charles-leclerc | ferrari | 22 | -0.282 | -0.477 | -0.087 | -0.095 | -0.005 |
| sergio-perez | cadillac | 22 | -0.270 | -0.472 | -0.069 | -0.442 | -0.129 |
| kimi-antonelli | mercedes | 23 | -0.194 | -0.436 | 0.049 | -0.201 | -0.247 |
| pierre-gasly | alpine | 22 | -0.147 | -0.323 | 0.030 | -0.318 | -0.575 |
| oscar-piastri | mclaren | 21 | -0.127 | -0.371 | 0.116 | 0.197 | 0.095 |
| lewis-hamilton | ferrari | 22 | -0.123 | -0.325 | 0.079 | 0.095 | 0.005 |
| fernando-alonso | aston-martin | 23 | -0.123 | -0.335 | 0.089 | -0.176 | -0.758 |
| carlos-sainz-jr | williams | 23 | -0.119 | -0.309 | 0.071 | -0.124 | -0.329 |

_First ten rows of the ordering; the full table is served by `/api/driver-effects`._

## Condition-specific deviations

Deviation of a driver from their own dry, car-adjusted expectation, shrunk towards zero with empirical Bayes (`tau` = estimated between-driver SD of the deviation). A driver is only *distinguishable* when the 90% posterior interval excludes zero.

| dimension | drivers | tau | insufficient_evidence | not_distinguishable_from_zero |
|---|---|---|---|---|
| high_speed_circuit | 32 | 0.000 | 1 | 31 |
| slow_corner_circuit | 32 | 0.043 | 1 | 31 |
| street_circuit | 32 | 0.081 | 1 | 31 |
| wet_qualifying | 30 | 0.000 | 4 | 26 |
| wet_race | 32 | 0.142 | 7 | 25 |


## Corner-type specialisation

Is a driver's corner delta to their team-mate a repeatable trait? Each driver-season's qualifying sessions (≥ 8) are split into odd and even rounds and the halves are correlated across drivers; the two-sided permutation p-value shuffles drivers between halves.

| Measure | Driver-seasons | Split-half r | Spearman–Brown | Permutation p |
|---|---|---|---|---|
| overall corner delta to team-mate | 85 | 0.227 | 0.370 | 0.031 |
| slow-minus-fast corner specialisation | 85 | -0.011 | -0.022 | 0.923 |

## Clusters (exploratory)

| k | Silhouette | Bootstrap ARI |
|---|---|---|
| 2 | 0.177 | 0.808 |
| 3 | 0.172 | 0.551 |
| 4 | 0.126 | 0.477 |
| 5 | 0.139 | 0.415 |
| 6 | 0.142 | 0.435 |

Chosen k = 2 on 103 driver-seasons with ≥ 10 dry races. Exploratory only. Clusters are stable under resampling. The two groups mainly separate overall pace relative to team-mates (|r| = 0.75 with a combined pace score), i.e. one performance axis rather than distinct driving styles; solutions with three or more groups are unstable.

| cluster | size | description |
|---|---|---|
| 0 | 49 | lower race gap to team-mate (-0.8 SD); lower qualifying gap to team-mate (-0.8 SD); lower team-adjusted qualifying (negative = faster) (-0.6 SD) |
| 1 | 54 | higher race gap to team-mate (+0.7 SD); higher qualifying gap to team-mate (+0.7 SD); higher team-adjusted qualifying (negative = faster) (+0.6 SD) |
