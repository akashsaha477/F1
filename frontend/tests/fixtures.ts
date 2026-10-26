// Small API payloads used to exercise the UI. They are test inputs, not results.
export const seasons = [
  { season: 2025, events: 24, era: "ground_effect", has_lap_data: true, lap_sessions: 120, laps: 1000 },
  { season: 1950, events: 7, era: "early_front_engine", has_lap_data: false, lap_sessions: null, laps: null },
];

export const events2025 = [
  { event_id: "2025-12", season: 2025, round: 12, date: "2025-07-06", grand_prix_id: "great-britain", official_name: "Test GP",
    circuit_id: "silverstone", circuit_name: "Silverstone", circuit_type: "RACE", laps: 52, is_sprint_weekend: false,
    era: "ground_effect", winner_id: "a-driver", lap_sessions: 5 },
];

export const drivers = {
  items: [
    { driver_id: "a-driver", name: "Alpha Driver", abbreviation: "ALP", first_season: 2022, last_season: 2025, races: 80, wins: 3,
      latest_constructor_id: "team-a", has_lap_data: true, full_name: null, nationality_country_id: null },
    { driver_id: "old-driver", name: "Old Driver", abbreviation: null, first_season: 1950, last_season: 1955, races: 20, wins: 2,
      latest_constructor_id: "team-x", has_lap_data: false, full_name: null, nationality_country_id: null },
  ],
  total: 2, limit: 200, offset: 0,
};

export const prediction = {
  task: "lap_time", horizon: "pre_event", model: "lightgbm", model_version: "lap_pace_pre_event-lightgbm-test",
  target: "rel_pace_pct", target_definition: "Relative pace",
  inputs: { driver_id: "a-driver", driver_name: "Alpha Driver", circuit_id: "silverstone", circuit_name: "Silverstone", form_as_of: "before 2025-12" },
  prediction: {
    value_pct: -0.71, value_s: -0.66,
    interval: { lo_pct: -2.05, hi_pct: 0.63, lo_s: -1.9, hi_s: 0.59, level: 0.9, method: "split-conformal", condition_group: "dry" },
    model_uncertainty: { lo_pct: -0.9, hi_pct: -0.45, sd_pct: 0.1, n_models: 20, method: "bootstrap" },
  },
  reference_lap_s: 93.1, reference_description: "",
  baseline: { value_pct: -0.11, description: "" },
  contributions: [
    { feature: "drv_form_pace", label: "Driver's recent race pace", group: "driver", value: -0.9, contribution_pct: -0.52, contribution_s: -0.48, direction: "faster" },
    { feature: "lap_number", label: "Lap number", group: "race_context", value: 26, contribution_pct: 0.27, contribution_s: 0.25, direction: "slower" },
  ],
  group_contributions: [{ group: "driver", contribution_pct: -0.52, contribution_s: -0.48, direction: "faster" }],
  assumptions: ["Form features as they stood before 2025-12."],
  evidence: { driver_representative_laps: 3962, driver_events: 78, driver_wet_laps: 4, cutoff: "2025-07-06" },
  extrapolation: [],
  warnings: ["Insufficient wet-weather evidence for this driver (4 representative wet laps)."],
  evaluation: { holdout: { n: 1, mae: 0.779, rmse: 1, r2: 0.3, coverage: 0.87, interval_width: 2.8, mae_seconds: 0.685 },
    development: { n: 1, mae: 0.78, rmse: 1, r2: 0.3, coverage: 0.87, interval_width: 2.8, mae_seconds: 0.69 }, train_period: "2022-2025" },
  limitations: ["Contributions are not causal effects."],
  narrative: "For Alpha Driver at Silverstone, the model predicts a representative race lap 0.71% faster than the session reference.",
};
