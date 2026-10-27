# Error analysis

_Generated 2026-10-27 08:09 UTC by `scripts/generate_reports.py` from `evaluation_runs/error_analysis_*.json`. Do not edit by hand; re-run the script._

## `pre_event` — LightGBM (Huber) (run `20261027T075133Z`)

Errors are in percentage points of the session reference lap (median clean lap of the session). Development = pooled walk-forward folds before the holdout season; holdout = final season, used once. Groups with fewer than 100 laps are omitted. Contrast intervals resample whole events. Wet-condition laps are rare; their intervals are wide.

### Contrasts (MAE difference, % points, event-cluster bootstrap 95% CI)

| Dimension | Groups | Estimate [95% CI] |
|---|---|---|
| condition | wet − dry | +0.423 [+0.212, +0.603] * |
| session_type | sprint − grand prix | +0.035 [-0.085, +0.179] |
| tyre_age | 26+ laps − 1-5 laps | -0.016 [-0.107, +0.059] |
| race_phase | final third − first third | +0.067 [-0.050, +0.209] |
| driver_experience | no earlier event − 10+ earlier events | -0.003 [-0.213, +0.332] |
| circuit_novelty | no earlier season at circuit − circuit seen before | +0.081 [-0.118, +0.259] |

### Holdout by condition

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| damp | 142 | 1 | 1.007 | -0.389 | 0.925 | -8.8% | 78.9% | 3.120 |
| dry | 17,915 | 18 | 0.895 | -0.206 | 0.897 | 0.3% | 84.9% | 3.120 |
| wet | 162 | 1 | 0.696 | -0.454 | 0.972 | 28.4% | 100.0% | 5.947 |

### Holdout by compound

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| HARD | 7,431 | 16 | 0.850 | -0.174 | 0.855 | 0.6% | 86.5% | 3.120 |
| INTERMEDIATE | 162 | 1 | 0.696 | -0.454 | 0.972 | 28.4% | 100.0% | 5.947 |
| MEDIUM | 7,065 | 18 | 0.851 | -0.168 | 0.870 | 2.2% | 85.6% | 3.120 |
| SOFT | 3,561 | 17 | 1.079 | -0.354 | 1.040 | -3.8% | 80.0% | 3.120 |

### Holdout by session type

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| grand prix | 16,224 | 18 | 0.905 | -0.239 | 0.888 | -1.9% | 84.4% | 3.120 |
| sprint | 1,995 | 6 | 0.802 | 0.030 | 0.976 | 17.8% | 89.4% | 3.350 |

### Holdout by tyre age

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| 1-5 laps | 2,721 | 18 | 1.026 | -0.307 | 1.077 | 4.8% | 80.6% | 3.125 |
| 16-25 laps | 4,921 | 18 | 0.791 | -0.120 | 0.787 | -0.5% | 88.5% | 3.148 |
| 26+ laps | 2,421 | 18 | 0.946 | -0.369 | 0.962 | 1.7% | 83.6% | 3.120 |
| 6-15 laps | 7,997 | 18 | 0.894 | -0.178 | 0.883 | -1.3% | 84.8% | 3.159 |

### Holdout by race phase

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| final third | 5,736 | 18 | 0.892 | -0.289 | 0.889 | -0.4% | 85.5% | 3.151 |
| first third | 5,933 | 18 | 0.934 | -0.190 | 0.927 | -0.7% | 82.4% | 3.120 |
| middle third | 6,550 | 18 | 0.859 | -0.157 | 0.879 | 2.4% | 86.9% | 3.164 |

### Holdout by driver experience

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| 1-4 earlier events | 155 | 4 | 0.660 | -0.194 | 0.757 | 12.9% | 94.2% | 3.120 |
| 10+ earlier events | 17,754 | 18 | 0.895 | -0.211 | 0.898 | 0.4% | 84.9% | 3.146 |
| 5-9 earlier events | 262 | 5 | 0.936 | -0.123 | 0.967 | 3.2% | 87.4% | 3.120 |

### Holdout by circuit novelty

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| circuit seen before | 16,721 | 16 | 0.883 | -0.197 | 0.891 | 1.0% | 85.2% | 3.148 |
| no earlier season at circuit | 1,498 | 2 | 1.015 | -0.349 | 0.970 | -4.6% | 83.0% | 3.120 |

### Holdout by driver circuit history

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| no earlier-season race here | 3,430 | 18 | 0.846 | -0.123 | 0.868 | 2.6% | 88.4% | 3.129 |
| raced here in an earlier season | 14,789 | 16 | 0.905 | -0.230 | 0.905 | -0.0% | 84.2% | 3.149 |

### Largest event errors (holdout)

| Event | Name | Laps | MAE % | Bias | Baseline MAE | Wet share | × median event |
|---|---|---|---|---|---|---|---|
| 2026-06 | Formula 1 Louis Vuitton Grand Prix de Monaco 2026 | 1,131 | 1.334 | -0.149 | 1.460 | 0.0% | 1.612 |
| 2026-05 | Formula 1 Lenovo Grand Prix du Canada 2026 | 1,299 | 1.299 | -0.649 | 1.075 | 0.0% | 1.570 |
| 2026-01 | Formula 1 Qatar Airways Australian Grand Prix 2026 | 828 | 1.206 | -0.245 | 1.143 | 0.0% | 1.456 |
| 2026-14 | Formula 1 TAG Heuer Gran Premio de España 2026 | 951 | 1.061 | -0.509 | 0.906 | 0.0% | 1.282 |
| 2026-07 | Formula 1 MSC Cruises Gran Premio de Barcelona-Catalunya 2026 | 1,016 | 0.988 | -0.388 | 0.999 | 0.0% | 1.193 |
| 2026-16 | Formula 1 Gulf Air Bahrain Grand Prix in Malaysia 2026 | 547 | 0.935 | -0.069 | 1.082 | 0.0% | 1.129 |
| 2026-04 | Formula 1 Crypto.com Miami Grand Prix 2026 | 1,126 | 0.870 | -0.212 | 0.785 | 0.0% | 1.050 |
| 2026-12 | Formula 1 Heineken Dutch Grand Prix 2026 | 1,545 | 0.847 | -0.087 | 0.964 | 9.2% | 1.023 |
| 2026-17 | Formula 1 Singapore Airlines Singapore Grand Prix 2026 | 1,198 | 0.834 | -0.269 | 0.906 | 13.5% | 1.008 |
| 2026-08 | Formula 1 Lenovo Austrian Grand Prix 2026 | 1,142 | 0.821 | -0.353 | 0.846 | 0.0% | 0.992 |

### Team bias by half-season (prediction − actual; positive = team faster than predicted)

| Season | Team | First half | Second half | Change | Laps |
|---|---|---|---|---|---|
| 2026 | aston-martin | -1.792 | -0.727 | 1.066 | 1,340 |
| 2026 | mercedes | 0.669 | 0.048 | -0.621 | 1,823 |
| 2026 | haas | -0.522 | 0.020 | 0.542 | 1,710 |
| 2025 | mclaren | 0.457 | -0.075 | -0.532 | 2,451 |
| 2024 | mercedes | 0.456 | 0.023 | -0.433 | 2,531 |
| 2023 | mclaren | -0.039 | 0.356 | 0.395 | 2,122 |
| 2024 | mclaren | 0.528 | 0.171 | -0.357 | 2,608 |
| 2025 | ferrari | 0.082 | -0.255 | -0.338 | 2,362 |
| 2026 | audi | -0.189 | 0.143 | 0.332 | 1,608 |
| 2023 | aston-martin | 0.224 | -0.070 | -0.295 | 2,162 |
| 2026 | ferrari | 0.505 | 0.234 | -0.271 | 1,816 |
| 2025 | alpine | -0.151 | -0.414 | -0.263 | 2,235 |

### Ordering of drivers within a session (all walk-forward test seasons; Spearman of mean predicted vs actual pace)

| Model | Sessions | Median | q25 | q75 | Share < 0.5 |
|---|---|---|---|---|---|
| LightGBM (Huber) | 112 | 0.809 | 0.746 | 0.877 | 1.8% |
| Team-adjusted form baseline | 112 | 0.818 | 0.714 | 0.876 | 3.6% |
| Ridge | 112 | 0.832 | 0.740 | 0.888 | 2.7% |

## `pre_race` — LightGBM (Huber) (run `20261027T075133Z`)

Errors are in percentage points of the session reference lap (median clean lap of the session). Development = pooled walk-forward folds before the holdout season; holdout = final season, used once. Groups with fewer than 100 laps are omitted. Contrast intervals resample whole events. Wet-condition laps are rare; their intervals are wide.

### Contrasts (MAE difference, % points, event-cluster bootstrap 95% CI)

| Dimension | Groups | Estimate [95% CI] |
|---|---|---|
| condition | wet − dry | +0.467 [+0.238, +0.611] * |
| session_type | sprint − grand prix | +0.021 [-0.105, +0.163] |
| tyre_age | 26+ laps − 1-5 laps | -0.006 [-0.105, +0.063] |
| race_phase | final third − first third | +0.075 [-0.045, +0.217] |
| driver_experience | no earlier event − 10+ earlier events | +0.042 [-0.201, +0.339] |
| circuit_novelty | no earlier season at circuit − circuit seen before | +0.091 [-0.122, +0.286] |

### Holdout by condition

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| damp | 142 | 1 | 0.961 | -0.350 | 0.925 | -3.8% | 79.6% | 3.004 |
| dry | 17,915 | 18 | 0.862 | -0.123 | 0.897 | 3.9% | 85.0% | 3.004 |
| wet | 162 | 1 | 0.659 | -0.339 | 0.972 | 32.2% | 100.0% | 6.285 |

### Holdout by compound

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| HARD | 7,431 | 16 | 0.808 | -0.112 | 0.855 | 5.5% | 86.7% | 3.004 |
| INTERMEDIATE | 162 | 1 | 0.659 | -0.339 | 0.972 | 32.2% | 100.0% | 6.285 |
| MEDIUM | 7,065 | 18 | 0.831 | -0.059 | 0.870 | 4.5% | 85.3% | 3.004 |
| SOFT | 3,561 | 17 | 1.040 | -0.282 | 1.040 | -0.1% | 80.6% | 3.004 |

### Holdout by session type

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| grand prix | 16,224 | 18 | 0.873 | -0.152 | 0.888 | 1.7% | 84.5% | 3.004 |
| sprint | 1,995 | 6 | 0.760 | 0.082 | 0.976 | 22.1% | 89.8% | 3.270 |

### Holdout by tyre age

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| 1-5 laps | 2,721 | 18 | 0.969 | -0.202 | 1.077 | 10.0% | 81.5% | 3.009 |
| 16-25 laps | 4,921 | 18 | 0.776 | -0.049 | 0.787 | 1.4% | 88.7% | 3.036 |
| 26+ laps | 2,421 | 18 | 0.877 | -0.285 | 0.962 | 8.8% | 84.1% | 3.004 |
| 6-15 laps | 7,997 | 18 | 0.868 | -0.096 | 0.883 | 1.7% | 84.6% | 3.049 |

### Holdout by race phase

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| final third | 5,736 | 18 | 0.858 | -0.248 | 0.889 | 3.5% | 85.3% | 3.039 |
| first third | 5,933 | 18 | 0.899 | -0.063 | 0.927 | 3.0% | 82.8% | 3.004 |
| middle third | 6,550 | 18 | 0.829 | -0.078 | 0.879 | 5.8% | 87.1% | 3.054 |

### Holdout by driver experience

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| 1-4 earlier events | 155 | 4 | 0.544 | -0.089 | 0.757 | 28.1% | 97.4% | 3.004 |
| 10+ earlier events | 17,754 | 18 | 0.863 | -0.127 | 0.898 | 3.9% | 85.0% | 3.034 |
| 5-9 earlier events | 262 | 5 | 0.855 | -0.147 | 0.967 | 11.6% | 84.0% | 3.004 |

### Holdout by circuit novelty

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| circuit seen before | 16,721 | 16 | 0.847 | -0.114 | 0.891 | 5.0% | 85.6% | 3.036 |
| no earlier season at circuit | 1,498 | 2 | 1.016 | -0.267 | 0.970 | -4.8% | 79.2% | 3.004 |

### Holdout by driver circuit history

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| no earlier-season race here | 3,430 | 18 | 0.816 | -0.057 | 0.868 | 6.1% | 86.6% | 3.014 |
| raced here in an earlier season | 14,789 | 16 | 0.871 | -0.143 | 0.905 | 3.7% | 84.7% | 3.037 |

### Largest event errors (holdout)

| Event | Name | Laps | MAE % | Bias | Baseline MAE | Wet share | × median event |
|---|---|---|---|---|---|---|---|
| 2026-06 | Formula 1 Louis Vuitton Grand Prix de Monaco 2026 | 1,131 | 1.356 | 0.104 | 1.460 | 0.0% | 1.707 |
| 2026-05 | Formula 1 Lenovo Grand Prix du Canada 2026 | 1,299 | 1.199 | -0.730 | 1.075 | 0.0% | 1.509 |
| 2026-01 | Formula 1 Qatar Airways Australian Grand Prix 2026 | 828 | 1.121 | 0.037 | 1.143 | 0.0% | 1.411 |
| 2026-14 | Formula 1 TAG Heuer Gran Premio de España 2026 | 951 | 1.047 | -0.516 | 0.906 | 0.0% | 1.318 |
| 2026-16 | Formula 1 Gulf Air Bahrain Grand Prix in Malaysia 2026 | 547 | 0.964 | 0.168 | 1.082 | 0.0% | 1.213 |
| 2026-07 | Formula 1 MSC Cruises Gran Premio de Barcelona-Catalunya 2026 | 1,016 | 0.917 | -0.370 | 0.999 | 0.0% | 1.154 |
| 2026-04 | Formula 1 Crypto.com Miami Grand Prix 2026 | 1,126 | 0.835 | -0.026 | 0.785 | 0.0% | 1.051 |
| 2026-17 | Formula 1 Singapore Airlines Singapore Grand Prix 2026 | 1,198 | 0.809 | -0.176 | 0.906 | 13.5% | 1.018 |
| 2026-12 | Formula 1 Heineken Dutch Grand Prix 2026 | 1,545 | 0.805 | -0.102 | 0.964 | 9.2% | 1.013 |
| 2026-11 | Formula 1 AWS Hungarian Grand Prix 2026 | 1,218 | 0.784 | -0.042 | 0.919 | 0.0% | 0.987 |

### Team bias by half-season (prediction − actual; positive = team faster than predicted)

| Season | Team | First half | Second half | Change | Laps |
|---|---|---|---|---|---|
| 2026 | aston-martin | -1.549 | -0.627 | 0.921 | 1,340 |
| 2025 | mclaren | 0.364 | -0.078 | -0.442 | 2,451 |
| 2026 | haas | -0.334 | 0.107 | 0.441 | 1,710 |
| 2024 | mercedes | 0.357 | -0.030 | -0.387 | 2,531 |
| 2026 | mercedes | 0.494 | 0.133 | -0.361 | 1,823 |
| 2023 | mclaren | -0.188 | 0.135 | 0.323 | 2,122 |
| 2025 | ferrari | 0.080 | -0.228 | -0.308 | 2,362 |
| 2026 | audi | -0.106 | 0.166 | 0.273 | 1,608 |
| 2024 | mclaren | 0.354 | 0.105 | -0.250 | 2,608 |
| 2024 | williams | -0.391 | -0.142 | 0.249 | 2,155 |
| 2025 | alpine | -0.199 | -0.431 | -0.232 | 2,235 |
| 2024 | red-bull | 0.073 | -0.149 | -0.222 | 2,439 |

### Ordering of drivers within a session (all walk-forward test seasons; Spearman of mean predicted vs actual pace)

| Model | Sessions | Median | q25 | q75 | Share < 0.5 |
|---|---|---|---|---|---|
| LightGBM (Huber) | 112 | 0.867 | 0.801 | 0.911 | 1.8% |
| Team-adjusted form baseline | 112 | 0.818 | 0.714 | 0.876 | 3.6% |
| Ridge | 112 | 0.845 | 0.759 | 0.902 | 0.0% |

