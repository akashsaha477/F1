# Error analysis

_Generated 2026-10-26 18:57 UTC by `scripts/generate_reports.py` from `evaluation_runs/error_analysis_*.json`. Do not edit by hand; re-run the script._

## `pre_event` — LightGBM (Huber) (run `20261026T182248Z`)

Errors are in percentage points of the session reference lap (median clean lap of the session). Development = pooled walk-forward folds before the holdout season; holdout = final season, used once. Groups with fewer than 100 laps are omitted. Contrast intervals resample whole events. Wet-condition laps are rare; their intervals are wide.

### Contrasts (MAE difference, % points, event-cluster bootstrap 95% CI)

| Dimension | Groups | Estimate [95% CI] |
|---|---|---|
| condition | wet − dry | +0.478 [+0.305, +0.704] * |
| session_type | sprint − grand prix | +0.075 [-0.137, +0.257] |
| tyre_age | 26+ laps − 1-5 laps | +0.007 [-0.101, +0.105] |
| race_phase | final third − first third | +0.108 [-0.026, +0.294] |
| driver_experience | no earlier event − 10+ earlier events | +0.010 [-0.263, +0.400] |
| circuit_novelty | no earlier season at circuit − circuit seen before | +0.039 [-0.228, +0.291] |

### Holdout by condition

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| dry | 22,273 | 24 | 0.758 | -0.045 | 0.840 | 9.8% | 87.7% | 2.813 |
| wet | 918 | 3 | 1.286 | -0.177 | 1.219 | -5.5% | 73.7% | 3.620 |

### Holdout by compound

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| HARD | 9,570 | 24 | 0.764 | -0.076 | 0.817 | 6.5% | 86.5% | 2.813 |
| INTERMEDIATE | 918 | 3 | 1.286 | -0.177 | 1.219 | -5.5% | 73.7% | 3.620 |
| MEDIUM | 9,974 | 24 | 0.753 | -0.030 | 0.852 | 11.6% | 88.8% | 2.813 |
| SOFT | 2,742 | 17 | 0.755 | 0.008 | 0.876 | 13.8% | 87.9% | 2.813 |

### Holdout by session type

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| grand prix | 21,594 | 24 | 0.779 | -0.065 | 0.840 | 7.2% | 87.1% | 2.842 |
| sprint | 1,610 | 6 | 0.773 | 0.142 | 1.053 | 26.6% | 87.9% | 2.888 |

### Holdout by tyre age

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| 1-5 laps | 3,148 | 24 | 0.883 | 0.020 | 1.049 | 15.8% | 82.8% | 2.828 |
| 16-25 laps | 6,732 | 24 | 0.669 | -0.159 | 0.751 | 10.9% | 90.2% | 2.851 |
| 26+ laps | 3,566 | 23 | 0.902 | -0.347 | 0.920 | 1.9% | 80.6% | 2.847 |
| 6-15 laps | 9,739 | 24 | 0.776 | 0.110 | 0.841 | 7.7% | 88.8% | 2.847 |

### Holdout by race phase

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| final third | 7,983 | 24 | 0.916 | -0.006 | 0.996 | 8.0% | 84.6% | 2.829 |
| first third | 6,835 | 24 | 0.719 | -0.088 | 0.781 | 7.9% | 87.7% | 2.845 |
| middle third | 8,386 | 24 | 0.697 | -0.062 | 0.781 | 10.8% | 89.2% | 2.860 |

### Holdout by driver experience

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| 1-4 earlier events | 1,042 | 7 | 0.625 | -0.151 | 0.696 | 10.2% | 92.7% | 2.854 |
| 10+ earlier events | 20,682 | 24 | 0.768 | -0.032 | 0.842 | 8.8% | 87.7% | 2.844 |
| 5-9 earlier events | 1,222 | 10 | 1.074 | -0.280 | 1.162 | 7.5% | 73.2% | 2.826 |
| no earlier event | 258 | 2 | 0.857 | -0.056 | 1.090 | 21.4% | 85.7% | 2.979 |

### Holdout by circuit novelty

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| circuit seen before | 23,204 | 24 | 0.779 | -0.050 | 0.855 | 8.9% | 87.1% | 2.845 |

### Holdout by driver circuit history

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| no earlier-season race here | 6,050 | 24 | 0.764 | -0.121 | 0.863 | 11.5% | 86.7% | 2.836 |
| raced here in an earlier season | 17,154 | 24 | 0.784 | -0.026 | 0.852 | 8.0% | 87.3% | 2.849 |

### Largest event errors (holdout)

| Event | Name | Laps | MAE % | Bias | Baseline MAE | Wet share | × median event |
|---|---|---|---|---|---|---|---|
| 2025-12 | Formula 1 Qatar Airways British Grand Prix 2025 | 423 | 3.586 | 2.025 | 3.697 | 67.4% | 5.586 |
| 2025-08 | Formula 1 TAG Heuer Grand Prix de Monaco 2025 | 1,142 | 1.757 | -0.574 | 1.764 | 0.0% | 2.737 |
| 2025-01 | Formula 1 Louis Vuitton Australian Grand Prix 2025 | 518 | 1.646 | 0.392 | 1.514 | 93.8% | 2.565 |
| 2025-06 | Formula 1 Crypto.com Miami Grand Prix 2025 | 629 | 1.064 | -0.688 | 1.046 | 25.4% | 1.657 |
| 2025-18 | Formula 1 Singapore Airlines Singapore Grand Prix 2025 | 1,104 | 0.912 | -0.028 | 0.853 | 0.0% | 1.421 |
| 2025-15 | Formula 1 Heineken Dutch Grand Prix 2025 | 998 | 0.775 | 0.124 | 0.780 | 0.0% | 1.208 |
| 2025-14 | Formula 1 Lenovo Hungarian Grand Prix 2025 | 1,275 | 0.740 | -0.130 | 0.856 | 0.0% | 1.153 |
| 2025-21 | Formula 1 MSC Cruises Grande Prêmio de São Paulo 2025 | 1,377 | 0.735 | -0.267 | 0.831 | 0.0% | 1.146 |
| 2025-09 | Formula 1 Aramco Gran Premio de España 2025 | 980 | 0.727 | 0.002 | 0.789 | 0.0% | 1.133 |
| 2025-10 | Formula 1 Pirelli Grand Prix du Canada 2025 | 1,153 | 0.724 | 0.224 | 0.789 | 0.0% | 1.128 |

### Team bias by half-season (prediction − actual; positive = team faster than predicted)

| Season | Team | First half | Second half | Change | Laps |
|---|---|---|---|---|---|
| 2025 | mclaren | 0.454 | -0.072 | -0.526 | 2,451 |
| 2024 | mercedes | 0.457 | 0.032 | -0.424 | 2,531 |
| 2023 | mclaren | -0.031 | 0.368 | 0.399 | 2,122 |
| 2024 | mclaren | 0.535 | 0.179 | -0.356 | 2,608 |
| 2025 | ferrari | 0.084 | -0.248 | -0.332 | 2,362 |
| 2023 | aston-martin | 0.226 | -0.082 | -0.308 | 2,162 |
| 2025 | alpine | -0.154 | -0.429 | -0.274 | 2,235 |
| 2023 | red-bull | -0.014 | 0.233 | 0.247 | 2,199 |
| 2024 | red-bull | 0.138 | -0.108 | -0.247 | 2,439 |
| 2024 | williams | -0.364 | -0.127 | 0.237 | 2,155 |
| 2024 | aston-martin | -0.057 | -0.264 | -0.207 | 2,408 |
| 2024 | alpine | -0.058 | 0.104 | 0.161 | 2,361 |

### Ordering of drivers within a session (all walk-forward test seasons; Spearman of mean predicted vs actual pace)

| Model | Sessions | Median | q25 | q75 | Share < 0.5 |
|---|---|---|---|---|---|
| LightGBM (Huber) | 88 | 0.808 | 0.719 | 0.867 | 2.3% |
| Team-adjusted form baseline | 88 | 0.774 | 0.681 | 0.861 | 4.5% |
| Ridge | 88 | 0.812 | 0.729 | 0.868 | 3.4% |

## `pre_race` — LightGBM (Huber) (run `20261026T182248Z`)

Errors are in percentage points of the session reference lap (median clean lap of the session). Development = pooled walk-forward folds before the holdout season; holdout = final season, used once. Groups with fewer than 100 laps are omitted. Contrast intervals resample whole events. Wet-condition laps are rare; their intervals are wide.

### Contrasts (MAE difference, % points, event-cluster bootstrap 95% CI)

| Dimension | Groups | Estimate [95% CI] |
|---|---|---|
| condition | wet − dry | +0.522 [+0.353, +0.717] * |
| session_type | sprint − grand prix | +0.057 [-0.149, +0.248] |
| tyre_age | 26+ laps − 1-5 laps | +0.022 [-0.086, +0.113] |
| race_phase | final third − first third | +0.117 [-0.023, +0.298] |
| driver_experience | no earlier event − 10+ earlier events | +0.057 [-0.252, +0.392] |
| circuit_novelty | no earlier season at circuit − circuit seen before | +0.037 [-0.258, +0.282] |

### Holdout by condition

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| dry | 22,273 | 24 | 0.736 | -0.085 | 0.840 | 12.3% | 87.7% | 2.746 |
| wet | 918 | 3 | 1.283 | -0.272 | 1.219 | -5.2% | 74.3% | 3.651 |

### Holdout by compound

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| HARD | 9,570 | 24 | 0.734 | -0.098 | 0.817 | 10.1% | 86.4% | 2.746 |
| INTERMEDIATE | 918 | 3 | 1.283 | -0.272 | 1.219 | -5.2% | 74.3% | 3.651 |
| MEDIUM | 9,974 | 24 | 0.736 | -0.096 | 0.852 | 13.6% | 88.7% | 2.746 |
| SOFT | 2,742 | 17 | 0.747 | -0.006 | 0.876 | 14.7% | 88.4% | 2.746 |

### Holdout by session type

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| grand prix | 21,594 | 24 | 0.761 | -0.104 | 0.840 | 9.5% | 87.1% | 2.779 |
| sprint | 1,610 | 6 | 0.729 | 0.053 | 1.053 | 30.8% | 88.3% | 2.830 |

### Holdout by tyre age

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| 1-5 laps | 3,148 | 24 | 0.884 | -0.043 | 1.049 | 15.7% | 81.4% | 2.762 |
| 16-25 laps | 6,732 | 24 | 0.652 | -0.196 | 0.751 | 13.1% | 90.2% | 2.789 |
| 26+ laps | 3,566 | 23 | 0.870 | -0.360 | 0.920 | 5.4% | 80.7% | 2.784 |
| 6-15 laps | 9,739 | 24 | 0.751 | 0.058 | 0.841 | 10.7% | 89.2% | 2.784 |

### Holdout by race phase

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| final third | 7,983 | 24 | 0.897 | -0.023 | 0.996 | 9.9% | 84.2% | 2.764 |
| first third | 6,835 | 24 | 0.692 | -0.155 | 0.781 | 11.3% | 88.3% | 2.782 |
| middle third | 8,386 | 24 | 0.680 | -0.110 | 0.781 | 13.0% | 88.9% | 2.799 |

### Holdout by driver experience

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| 1-4 earlier events | 1,042 | 7 | 0.607 | -0.186 | 0.696 | 12.8% | 91.4% | 2.792 |
| 10+ earlier events | 20,682 | 24 | 0.748 | -0.074 | 0.842 | 11.1% | 87.8% | 2.781 |
| 5-9 earlier events | 1,222 | 10 | 1.007 | -0.304 | 1.162 | 13.3% | 73.8% | 2.760 |
| no earlier event | 258 | 2 | 1.008 | -0.267 | 1.090 | 7.5% | 81.8% | 2.932 |

### Holdout by circuit novelty

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| circuit seen before | 23,204 | 24 | 0.758 | -0.093 | 0.855 | 11.3% | 87.1% | 2.782 |

### Holdout by driver circuit history

| Group | Laps | Events | MAE % | Bias | Baseline MAE | Skill vs baseline | 90% PI coverage | PI width |
|---|---|---|---|---|---|---|---|---|
| no earlier-season race here | 6,050 | 24 | 0.747 | -0.187 | 0.863 | 13.4% | 86.2% | 2.772 |
| raced here in an earlier season | 17,154 | 24 | 0.762 | -0.060 | 0.852 | 10.5% | 87.5% | 2.786 |

### Largest event errors (holdout)

| Event | Name | Laps | MAE % | Bias | Baseline MAE | Wet share | × median event |
|---|---|---|---|---|---|---|---|
| 2025-12 | Formula 1 Qatar Airways British Grand Prix 2025 | 423 | 3.659 | 1.918 | 3.697 | 67.4% | 5.657 |
| 2025-08 | Formula 1 TAG Heuer Grand Prix de Monaco 2025 | 1,142 | 1.679 | -0.462 | 1.764 | 0.0% | 2.597 |
| 2025-01 | Formula 1 Louis Vuitton Australian Grand Prix 2025 | 518 | 1.600 | 0.357 | 1.514 | 93.8% | 2.473 |
| 2025-06 | Formula 1 Crypto.com Miami Grand Prix 2025 | 629 | 1.085 | -0.781 | 1.046 | 25.4% | 1.678 |
| 2025-18 | Formula 1 Singapore Airlines Singapore Grand Prix 2025 | 1,104 | 0.869 | -0.051 | 0.853 | 0.0% | 1.344 |
| 2025-15 | Formula 1 Heineken Dutch Grand Prix 2025 | 998 | 0.757 | 0.131 | 0.780 | 0.0% | 1.170 |
| 2025-21 | Formula 1 MSC Cruises Grande Prêmio de São Paulo 2025 | 1,377 | 0.743 | -0.356 | 0.831 | 0.0% | 1.149 |
| 2025-14 | Formula 1 Lenovo Hungarian Grand Prix 2025 | 1,275 | 0.734 | -0.191 | 0.856 | 0.0% | 1.134 |
| 2025-23 | Formula 1 Qatar Airways Qatar Grand Prix 2025 | 1,238 | 0.695 | -0.219 | 0.833 | 0.0% | 1.075 |
| 2025-09 | Formula 1 Aramco Gran Premio de España 2025 | 980 | 0.692 | -0.003 | 0.789 | 0.0% | 1.070 |

### Team bias by half-season (prediction − actual; positive = team faster than predicted)

| Season | Team | First half | Second half | Change | Laps |
|---|---|---|---|---|---|
| 2025 | mclaren | 0.353 | -0.091 | -0.444 | 2,451 |
| 2024 | mercedes | 0.366 | -0.036 | -0.402 | 2,531 |
| 2023 | mclaren | -0.168 | 0.153 | 0.321 | 2,122 |
| 2025 | ferrari | 0.070 | -0.223 | -0.293 | 2,362 |
| 2024 | mclaren | 0.380 | 0.098 | -0.281 | 2,608 |
| 2024 | red-bull | 0.082 | -0.167 | -0.249 | 2,439 |
| 2024 | aston-martin | -0.020 | -0.261 | -0.241 | 2,408 |
| 2024 | williams | -0.390 | -0.151 | 0.239 | 2,155 |
| 2025 | alpine | -0.198 | -0.430 | -0.232 | 2,235 |
| 2023 | aston-martin | 0.040 | -0.180 | -0.220 | 2,162 |
| 2024 | kick-sauber | -0.257 | -0.466 | -0.209 | 2,475 |
| 2023 | haas | -0.342 | -0.536 | -0.194 | 2,090 |

### Ordering of drivers within a session (all walk-forward test seasons; Spearman of mean predicted vs actual pace)

| Model | Sessions | Median | q25 | q75 | Share < 0.5 |
|---|---|---|---|---|---|
| LightGBM (Huber) | 88 | 0.861 | 0.763 | 0.900 | 1.1% |
| Team-adjusted form baseline | 88 | 0.774 | 0.681 | 0.861 | 4.5% |
| Ridge | 88 | 0.823 | 0.751 | 0.886 | 0.0% |

