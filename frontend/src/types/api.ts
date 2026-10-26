// Response shapes of the ApexLens API (see src/apexlens/api in the backend).

export interface ApiErrorBody {
  error: { code: string; message: string };
}

export interface Season {
  season: number;
  events: number;
  era: string;
  has_lap_data: boolean;
  lap_sessions: number | null;
  laps: number | null;
}

export interface EventItem {
  event_id: string;
  season: number;
  round: number;
  date: string | null;
  grand_prix_id: string;
  official_name: string;
  circuit_id: string;
  circuit_name: string | null;
  circuit_type: string | null;
  laps: number | null;
  is_sprint_weekend: boolean;
  era: string;
  winner_id: string | null;
  lap_sessions?: number;
}

export interface Circuit {
  circuit_id: string;
  name: string;
  full_name: string;
  type: string;
  country_id: string;
  length_km: number | null;
  turns: number | null;
  events: number | null;
  first_season: number | null;
  last_season: number | null;
  has_lap_data: boolean;
}

export interface DriverIndexItem {
  driver_id: string;
  name: string;
  full_name: string | null;
  abbreviation: string | null;
  nationality_country_id: string | null;
  first_season: number;
  last_season: number;
  races: number;
  wins: number;
  latest_constructor_id: string | null;
  has_lap_data: boolean;
  constructors?: string[];
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Constructor {
  constructor_id: string;
  name: string;
  full_name: string | null;
}

export interface SessionItem {
  session_id: string;
  event_id: string;
  season: number;
  round: number;
  session_code: string;
  date: string | null;
  start_utc: string | null;
  quality_status?: string | null;
  n_laps?: number | null;
  n_clean_laps?: number | null;
  n_drivers?: number | null;
  warnings?: string[] | null;
  telemetry_laps: number;
}

export interface Lap {
  driver_id: string;
  driver_abbr: string;
  constructor_id: string;
  lap_number: number;
  lap_time_s: number | null;
  sector1_s: number | null;
  sector2_s: number | null;
  sector3_s: number | null;
  compound: string;
  tyre_life_laps: number | null;
  stint: number | null;
  position: number | null;
  track_status: string | null;
  is_clean: boolean;
  exclusion_reason: string | null;
  condition: string;
  is_pit_in_lap: boolean;
  is_pit_out_lap: boolean;
  deleted: boolean | null;
  is_personal_best: boolean | null;
  speed_st_kph: number | null;
  track_temp_c: number | null;
  rainfall: boolean | null;
  quali_segment: string | null;
}

export interface SessionLaps {
  session_id: string;
  quality: { quality_status: string | null; warnings: string[] | null; fatal: string[] | null };
  laps: Lap[];
}

export interface Contribution {
  feature: string;
  label: string;
  group: string;
  value: number | string | boolean | null;
  contribution_pct: number;
  contribution_s: number | null;
  direction: "faster" | "slower";
}

export interface GroupContribution {
  group: string;
  contribution_pct: number;
  contribution_s: number | null;
  direction: "faster" | "slower";
}

export interface ModelUncertainty {
  lo_pct: number;
  hi_pct: number;
  sd_pct: number;
  n_models: number;
  method: string;
  prob_a_faster?: number;
}

export interface MetricSubset {
  n: number;
  mae: number;
  rmse: number;
  r2: number;
  coverage: number;
  interval_width: number;
  mae_seconds: number;
  mae_ci?: [number, number];
}

export interface ExtrapolationFlag {
  feature: string;
  label: string;
  value: number;
  p01: number;
  p99: number;
  outside_observed_range: boolean;
}

export interface LapPrediction {
  task: "lap_time";
  horizon: string;
  model: string;
  model_version: string;
  target: string;
  target_definition: string;
  inputs: Record<string, unknown> & { driver_id: string; driver_name?: string; circuit_id: string; circuit_name?: string; form_as_of: string };
  prediction: {
    value_pct: number;
    value_s: number | null;
    interval: { lo_pct: number; hi_pct: number; lo_s: number | null; hi_s: number | null; level: number; method: string; condition_group: string };
    model_uncertainty: ModelUncertainty | null;
  };
  reference_lap_s: number | null;
  reference_description: string;
  baseline: { value_pct: number; description: string };
  contributions: Contribution[];
  group_contributions: GroupContribution[];
  assumptions: string[];
  evidence: Record<string, number | string>;
  extrapolation: ExtrapolationFlag[];
  warnings: string[];
  evaluation: { holdout: MetricSubset; development: MetricSubset; train_period: string };
  limitations: string[];
  narrative: string;
}

export interface ComparisonDriver {
  driver_id: string;
  name: string;
  constructor_id: string;
  prediction_pct: number;
  interval_pct: [number, number];
  evidence: Record<string, number | string>;
}

export interface ComparisonPrediction {
  task: "driver_comparison";
  horizon: string;
  model_version: string;
  target_definition: string;
  scenario: Record<string, unknown>;
  drivers: ComparisonDriver[];
  difference: {
    value_pct: number;
    value_s: number | null;
    model_uncertainty: ModelUncertainty | null;
    contributions: Contribution[];
    group_contributions: GroupContribution[];
  };
  reference_lap_s: number | null;
  warnings: string[];
  limitations: string[];
  counterfactuals: Record<string, { difference_pct?: number; description?: string; compound?: string; error?: string }>;
  narrative: string;
}

export interface ScenarioChange {
  change: string;
  feature: string;
  new_value: number | string;
  delta_pct: number;
  supported: boolean;
  curve?: { value: number; prediction_pct: number }[];
}

export interface ScenarioResult {
  base_prediction_pct: number;
  changes: ScenarioChange[];
  note: string;
}

export interface LapScenario {
  driver_id: string;
  circuit_id?: string | null;
  as_of_event_id?: string | null;
  horizon: "pre_event" | "pre_race";
  compound: string;
  tyre_life_laps: number;
  race_progress: number;
  track_temp_c?: number | null;
  air_temp_c?: number | null;
  humidity_pct?: number | null;
  rainfall: boolean;
  stint: number;
  is_sprint: boolean;
  constructor_override?: string | null;
  quali_gap_pct?: number | null;
}

export interface Overview {
  summary: Record<string, number | number[]>;
  per_season: Array<Record<string, number | null | Record<string, number>>>;
  analyses: Array<{ analysis: string; supported: boolean; evidence: string; limitation?: string }>;
  recent_races: Array<{
    event_id: string;
    season: number;
    round: number;
    date: string;
    circuit_id: string;
    official_name: string;
    podium: Array<{ position: number; driver_id: string; constructor_id: string }>;
    pole_driver_id: string | null;
    wet_race: boolean;
  }>;
  seasons_with_lap_data: number[];
  results_seasons: [number, number];
}

export interface ModelListItem {
  model_version: string;
  task: string;
  model: string;
  horizon: string;
  saved_at: string;
  train_period: string;
  is_production: boolean;
  target: string;
  test_metrics: { development: MetricSubset; holdout: MetricSubset };
}

export interface DriverPerformanceEvent {
  event_id: string;
  season: number;
  round: number;
  constructor_id: string;
  position: number | null;
  position_text: string | null;
  grid_position: number | null;
  points: number | null;
  outcome_category: string;
  reason_retired: string | null;
  date: string;
  circuit_id: string;
  grand_prix_id: string;
  quali_position: number | null;
  quali_best_s: number | null;
  med_rel_pace?: number | null;
  n_laps?: number | null;
  teammate_gap?: number | null;
  robust_sd?: number | null;
  is_wet_session?: boolean | null;
}

export interface DriverPerformance {
  driver: DriverIndexItem;
  results_summary: {
    starts: number;
    wins: number;
    podiums: number;
    points: number;
    poles: number;
    outcomes: Record<string, number>;
    mean_positions_gained: number | null;
    positions_gained_n: number;
    seasons: number[];
    note: string;
  };
  events: DriverPerformanceEvent[];
}

export interface ProfileSeason {
  driver_id: string;
  season: number;
  main_team: string;
  teams: string;
  n_dry_races: number;
  n_laps: number;
  race_pace_adj: number;
  race_pace_adj_sd: number;
  race_pace_adj_lo: number;
  race_pace_adj_hi: number;
  race_pace_raw: number;
  team_effect: number | null;
  team_effect_sd: number | null;
  teammate_gap_race: number | null;
  teammate_gap_race_lo: number | null;
  teammate_gap_race_hi: number | null;
  n_teammate_races: number;
  consistency_sd: number;
  consistency_lo: number | null;
  consistency_hi: number | null;
  quali_adj: number | null;
  quali_adj_sd: number | null;
  quali_gap_median: number | null;
  quali_teammate_gap: number | null;
  quali_teammate_gap_lo: number | null;
  quali_teammate_gap_hi: number | null;
  n_quali: number;
  n_quali_teammate: number;
  lap1_gain_mean: number | null;
  n_lap1: number | null;
  positions_gained_mean: number | null;
  n_classified: number | null;
  race_pace_adj_pctile: number | null;
  consistency_pctile: number | null;
  quali_adj_pctile: number | null;
  rank_reference: string;
  [k: string]: unknown;
}

export interface ConditionEffect {
  driver_id: string;
  dimension: string;
  raw: number;
  raw_se: number;
  posterior_mean: number;
  posterior_sd: number;
  tau: number;
  n_sessions: number;
  n_laps: number;
  status: "supported" | "not_distinguishable_from_zero" | "insufficient_evidence";
  unit: string;
  seasons: string;
}

export interface ProfileMeta {
  race_model: { variances: Record<string, number>; n_obs: number; formula: string };
  quali_model: { variances: Record<string, number>; n_obs: number; formula: string };
  identification_note: string;
  thresholds: Record<string, number>;
  seasons: number[];
}

export interface DriverProfile {
  driver_id: string;
  seasons: ProfileSeason[];
  conditions: ConditionEffect[];
  meta: ProfileMeta;
}

export interface SeasonEffects {
  season: number;
  drivers: ProfileSeason[];
  meta: ProfileMeta;
}

export interface DriverCompare {
  drivers: [string, string];
  profiles: Record<string, ProfileSeason[]>;
  conditions: Record<string, ConditionEffect[]>;
  head_to_head: {
    sessions: { session_id: string; season: number; condition: string; same_team: boolean; diff: number; se: number }[];
    summary: { n_sessions: number; n_same_team: number; median_diff: number | null; ci90: [number, number] | null; a_faster_share: number | null; note: string } | null;
  };
  meta: ProfileMeta;
}

export interface CornerDef {
  corner_id: string;
  method: string;
  n_markers: number;
  entry_s: number;
  apex_s: number;
  exit_s: number;
  length_m: number;
  heading_change_deg: number;
  direction: string;
  entry_speed_ref: number;
  min_speed_ref: number;
  exit_speed_ref: number;
  min_throttle_ref: number;
  x: number;
  y: number;
  category: "slow" | "medium" | "fast" | "flat_out";
  is_hairpin: boolean;
  is_chicane: boolean;
  is_esses?: boolean;
  is_sweeper: boolean;
  is_sequence: boolean;
  sector: number | null;
}

export interface TrackLayout {
  circuit_id: string;
  session_id: string;
  season: number;
  layout_id: string | null;
  rotation_deg: number;
  length_m: number;
  reference: { driver_id: string; lap: number; lap_time_s: number };
  segmentation_method: string;
  marker_validation: Record<string, number | string | null>;
  sector_bounds_m: [number, number] | null;
  track: { s: number; x: number; y: number; speed_ref: number | null; throttle_ref: number | null }[];
  corners: CornerDef[];
  inferred_segments: { segment_id: string; apex_s: number; heading_change_deg: number }[];
  sectors: { sector: number; length_m: number; frac_slow: number; frac_medium: number; frac_fast: number; full_throttle_frac: number }[];
  available_sessions: { session_id: string; season: number; circuit_layout_id: string; reference_driver: string; reference_lap_time_s: number }[];
  category_rules: Record<string, number>;
  notes: string[];
}

export interface CornerMetric {
  driver_id: string;
  constructor_id: string;
  lap_number: number;
  lap_time_s: number;
  corner_id: string;
  category: string;
  sector: number | null;
  segment_time_s: number;
  delta_to_best_s: number | null;
  delta_to_teammate_s: number | null;
  teammate_comparable: boolean;
  entry_speed_kph: number;
  min_speed_kph: number;
  exit_speed_kph: number;
  brake_onset_before_apex_m: number | null;
  braking_duration_s: number | null;
  full_throttle_delay_s: number | null;
  min_gear: number | null;
  max_decel_proxy_ms2: number | null;
  quality: string;
}

export interface TrackPerformance {
  circuit_id: string;
  session_id: string;
  corner_id: string | null;
  metrics: CornerMetric[];
  teammate_relative_history: { driver_id: string; mean_delta_to_teammate_s: number; n_corner_laps: number; n_sessions: number }[];
  measured_vs_derived: { measured: string[]; derived: string[] };
  notes: string[];
}

export interface TelemetryResponse {
  session_id: string;
  available_laps: { driver_id: string; lap_number: number; lap_time_s: number; selection: string; quality_status: string }[];
  samples?: { driver_id: string; lap_number: number; time_s: number; distance_m: number; speed_kph: number; throttle_pct: number; brake: boolean; gear: number }[];
  channels?: { measured: string[]; derived: string[]; unavailable: string[] };
  note?: string;
}
