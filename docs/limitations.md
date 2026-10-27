# Limitations

What ApexLens cannot tell you, and why. The dashboard's *Data & methodology* page shows the same list
(`services/methodology.py`), and model-specific failure modes are quantified in
`reports/error_analysis.md`.

## Data

* **Unofficial timing source.** Official F1 live timing, Jolpica and OpenF1 were unreachable from the
  build environment. Lap-level data comes from a public FastF1 export (TracingInsights). The FastF1,
  Jolpica and OpenF1 adapters exist but are only tested against recorded/mocked responses.
* **Five seasons.** Lap-level data covers 2022–2026 (2026 up to the last ingested race). F1DB results go
  back to 1950 but are not used for lap-level models. 2026 introduced new technical regulations: form
  and tyre-wear estimates weight recent races most, but most training laps come from 2022–2025 cars,
  so check the 2026 fold of the evaluation before trusting 2026 predictions.
* **Telemetry is thin.** One lap per driver and qualifying session (the fastest clean lap). Corner
  metrics therefore describe single-lap qualifying pace, not race pace or tyre management.
* **Missing channels.** Brake is on/off only; there is no brake pressure, steering angle, tyre
  temperature, fuel load, ERS deployment or setup information.
* **Relative compound names.** SOFT/MEDIUM/HARD map to different Pirelli compounds (C1–C6) at different
  events; the C-number is not in the data.
* **One weather sensor** per circuit, about once a minute; rain is a binary flag.

## Modelling

* **Driver vs car.** The two are only separable through team-mate comparisons and drivers who changed
  teams. Cross-team driver comparisons inherit that uncertainty (see the identification note in
  `reports/driver_profiles.md`).
* **Form lags development.** Pre-event form features are exponentially weighted over previous events, so
  rapid in-season car upgrades are picked up several events late; this is visible as half-season team
  bias in the error analysis.
* **Sparse conditions.** Wet races, wet qualifying and new circuits have little data; the corresponding
  estimates are shrunk and usually reported as insufficient or indistinguishable from zero.
* **Interval calibration.** Conformal intervals assume the calibration events resemble the test events.
  Coverage on later seasons is below the nominal 90%, most clearly in the wet; read the intervals as
  optimistic.
* **Unobserved context.** Traffic, dirty air, damage, team orders and strategy instructions are not
  observed. Lap filters (representative laps) and race-phase features are proxies.
* **Model differences are small.** LightGBM is the selected model; for pre-event forecasts its advantage
  over Ridge and the spline GAM on the holdout season is within sampling uncertainty (it is significant
  only once the weekend's qualifying is known). See `reports/model_comparison.md`.

## Race week planner

* Plans are for dry races; intermediate/wet strategies are not optimised, and the rain risk is shown instead.
* Safety cars and VSCs are not simulated; the historical frequency is shown. Real strategies react to them.
* Every stint after the start is assumed to be on new tyres; real tyre allocations and used sets differ.
* The backtest shows the planner's stop count and tyre choice agree with the top-10 about as often as
  simply copying the previous race at the same circuit, and less often for the starting compound.
* The finishing order does not predict retirements, penalties or first-lap incidents.
* For upcoming races the line-up and form are those after the last ingested race.

## Interpretation

* **Associations, not causes.** Feature contributions, ALE curves and counterfactuals describe the
  fitted models. They do not say what *caused* a lap time.
* **No personality labels.** Driver clusters are exploratory, described only by measured features, and
  reported as unstable when resampling says so.
* **Rankings carry uncertainty.** Orderings of drivers are shown with intervals; most adjacent pairs
  overlap and should not be read as strict ranks.

## Licensing and use

* F1DB data is CC BY 4.0 and requires attribution.
* The TracingInsights repositories declare MIT (2022–2024) or Apache 2.0 (2025–2026); the underlying timing data originates from the F1
  live-timing service and is unofficial. Use for non-commercial research.
* F1, FORMULA ONE and related marks are trademarks of Formula One Licensing B.V. ApexLens is not
  associated with Formula 1, the FIA or any team, and is not intended for betting.
