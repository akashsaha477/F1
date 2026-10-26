Test fixtures are small, unmodified excerpts of real source files, used only to test parsing and
normalisation code. They are never used as model results.

- `f1db_repo/src/data/`: files from F1DB (https://github.com/f1db/f1db), CC BY 4.0.
- `tracinginsights/`: excerpts of the TracingInsights FastF1 export for the 2024 Bahrain Grand Prix
  (https://github.com/TracingInsights/2024, MIT): three drivers x eight laps of `session_laptimes.json`,
  the first 120 samples of one lap of telemetry, `corners.json`, and the first rows of weather and
  race-control files.
