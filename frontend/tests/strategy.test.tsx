import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import RaceStrategyPage from "../src/pages/RaceStrategy";
import { drivers } from "./fixtures";
import { mockApi, renderPage } from "./helpers";

const ci = (estimate: number, lo: number, hi: number) => ({ estimate, lo, hi, n: 50 });
const plan = (label: string, sequence: string[], stint_laps: number[], delta_s: number) => ({
  label, sequence, stint_laps, stops: sequence.length - 1, delta_s, strategy_cost_s: 30 + delta_s, calibration_cost_s: 10,
  pit_laps: stint_laps.slice(0, -1).map((_, i) => stint_laps.slice(0, i + 1).reduce((a, b) => a + b, 0)),
  pit_windows: stint_laps.slice(0, -1).map((_, i) => {
    const l = stint_laps.slice(0, i + 1).reduce((a, b) => a + b, 0);
    return { stop: i + 1, best_lap: l, from_lap: l - 3, to_lap: l + 2 };
  }),
  equivalent_orders: [],
});
const trace = (n: number) => Array.from({ length: n }, (_, i) => ({ lap: i + 1, compound: i < 30 ? "MEDIUM" : "HARD", stint: i < 30 ? 1 : 2,
  tyre_age: (i % 30) + 1, lap_time_s: 80 + i * 0.01, pit: i === 29 ? "in" : i === 30 ? "out" : null }));

const response = {
  event: { event_id: "2025-20", name: "Formula 1 Test Grand Prix 2025", circuit_id: "test", circuit_name: "Test Ring", date: "2025-10-26",
    season: 2025, laps: 71, mode: "past" },
  driver: { driver_id: "a-driver", name: "Alpha Driver", constructor_id: "team-a", car_override: null },
  weather: {
    weekend_sessions: [{ session_id: "2025-20-Q", session_code: "Q", start_utc: null, air_temp_c: 22, track_temp_c: 40, humidity_pct: 40, rain_share: 0 }],
    circuit_history: { races: 3, track_temp_range_c: [35, 48], rain_race_share: 0 }, forecast: null,
    race_actual: { air_temp_c: 23, track_temp_c: 42, humidity_pct: 38, rain_share: 0 },
    assumed: { values: { track_temp_c: 40, air_temp_c: 22, humidity_pct: 40, rain_risk: 0, wet_race_likely: false },
      source: { track_temp_c: "mean of this weekend's sessions", rain_risk: "rain in this weekend's sessions / circuit history" } },
  },
  parameters: { laps: 71, ref_lap_s: 80, ref_source: "qualifying", pit_loss_s: 23.1, start_age: 0, fuel_pct_per_lap: -0.06,
    slope_s_per_lap: { SOFT: 0.09, MEDIUM: 0.05, HARD: 0.04 }, offset_s: { SOFT: -0.2, MEDIUM: 0, HARD: 0.05 },
    max_stint: { SOFT: 20, MEDIUM: 35, HARD: 45 }, sc_prob: 0.5, vsc_prob: 0.4, red_prob: 0.1, rule_notes: [],
    evidence: { races_at_circuit: 3, races_total: 60, pit_stops_at_circuit: 80, degradation: { SOFT: { stints_at_circuit: 5, stints_total: 400 } } } },
  calibration: { stop_s: 10, soft_stint_s: 27.5, races: 50, agreement: 0.55 },
  plans: [plan("M-H (1 stop)", ["MEDIUM", "HARD"], [30, 41], 0), plan("M-H-H (2 stops)", ["MEDIUM", "HARD", "HARD"], [20, 25, 26], 6.2)],
  best: plan("M-H (1 stop)", ["MEDIUM", "HARD"], [30, 41], 0),
  robustness: { n: 25, best_share: [{ label: "M-H (1 stop)", share: 0.84 }, { label: "M-H-H (2 stops)", share: 0.16 }],
    first_stop_lap: { p10: 27, median: 30, p90: 33 } },
  trace: { best: trace(71), alternative: null, alternative_label: null },
  expected_race_time_s: 5712.3,
  prediction: { pace_model: "lap-pace model trained on 2022–2024 only", base_pct: -0.6, grid: 2, grid_source: "actual starting grid",
    predicted_position: 1, blend_weight: 0.35, blend_weight_races: 50,
    field: [{ driver_id: "a-driver", name: "Alpha Driver", constructor_id: "team-a", grid: 2, base_pct: -0.6, pace_rank: 1, predicted_position: 1, actual_position: 1 },
      { driver_id: "b-driver", name: "Beta Driver", constructor_id: "team-b", grid: 1, base_pct: -0.2, pace_rank: 2, predicted_position: 2, actual_position: null }] },
  actual: {
    driver_strategy: { sequence: ["SOFT", "MEDIUM"], label: "S-M (1 stop)", stops: 1, pit_laps: [28], stint_laps: [28, 43], dry_only: true, start_tyre_age: 1 },
    result: { position: 1, position_text: "1", grid: 2, time_s: 5700, outcome: "finished", reason_retired: null },
    race: { winner: null, safety_car: true, virtual_safety_car: false, red_flag: false, wet: false, top_modal_plan: "1|HARD+MEDIUM",
      top: [{ driver_id: "a-driver", position: 1, constructor_id: "team-a", sequence: ["SOFT", "MEDIUM"], label: "S-M (1 stop)", stops: 1,
        pit_laps: [28], stint_laps: [28, 43], dry_only: true, start_tyre_age: 1 }] },
    laps: [{ lap: 2, lap_time_s: 81, compound: "SOFT", clean: true, reason: null }],
    replay_trace: trace(71),
    comparison: { same_stop_count: true, same_compounds: false, first_stop_in_window: true, winner_same_stop_count: true,
      matches_most_common_top10_plan: true },
  },
  backtest: { races: 70, strategy_races: 57, plan_match: ci(0.4, 0.28, 0.54), stops_match: ci(0.6, 0.47, 0.72), start_match: ci(0.84, 0.74, 0.93),
    window_hit: ci(0.47, 0.36, 0.57), previous_edition: { stops_match: ci(0.61, 0.47, 0.74), plan_match: ci(0.45, 0.31, 0.59), start_match: ci(0.96, 0.9, 1) },
    finishing_order: { blend: { spearman: ci(0.78, 0.74, 0.82), winner_correct: ci(0.57, 0.46, 0.69), podium_overlap: ci(0.66, 0.6, 0.72) },
      grid_order: { spearman: ci(0.74, 0.7, 0.79), winner_correct: ci(0.63, 0.51, 0.74), podium_overlap: ci(0.71, 0.66, 0.77) } },
    lap_replay: { model_mae_s: ci(2.87, 1.9, 3.9), constant_pace_mae_s: ci(3.08, 2.1, 4.1) } },
  warnings: ["Rule: something"],
  limitations: ["Dry-race strategies only: if it rains, intermediate/wet tyre strategies are not optimised."],
};

describe("Race week planner", () => {
  it("plans a race and compares it with what happened", async () => {
    const fetchMock = mockApi((url, init) => {
      if (url.pathname === "/api/strategy/race-weeks") return { body: { race_weeks: [
        { event_id: "2025-20", season: 2025, round: 20, name: "Formula 1 Test Grand Prix 2025", circuit_id: "test", date: "2025-10-26", status: "past" },
        { event_id: "2026-19", season: 2026, round: 19, name: "Formula 1 Future Grand Prix 2026", circuit_id: "test", date: "2026-11-01", status: "upcoming" },
      ] } };
      if (url.pathname === "/api/drivers") return { body: drivers };
      if (url.pathname === "/api/constructors") return { body: [{ constructor_id: "team-b", name: "Team B", full_name: null }] };
      if (url.pathname === "/api/strategy/plan" && init?.method === "POST") return { body: response };
      return undefined;
    });
    renderPage(<RaceStrategyPage />, "/race-week?event=2025-20&driver=a-driver");
    const button = await screen.findByRole("button", { name: "Plan the race" });
    await screen.findByRole("option", { name: "Alpha Driver" });
    await userEvent.click(button);
    expect(await screen.findByText("What actually happened")).toBeInTheDocument();
    const body = JSON.parse(String(fetchMock.mock.calls.find((c) => String(c[0]).includes("/strategy/plan"))?.[1]?.body));
    expect(body).toMatchObject({ event_id: "2025-20", driver_id: "a-driver", max_stops: 3, rain: null });
    expect(screen.getAllByText("P1").length).toBeGreaterThan(1);
    expect(screen.getByText("1:35:12.3")).toBeInTheDocument();
    expect(screen.getByText("first stop inside the window")).toBeInTheDocument();
    expect(screen.getByText("Track record on past races")).toBeInTheDocument();
    expect(screen.getByText("84%")).toBeInTheDocument(); // robustness share
    expect(screen.getAllByText(/Copy last year/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Rule: something/)).toBeInTheDocument();
  });

  it("flags races without timing data", async () => {
    mockApi((url) => {
      if (url.pathname === "/api/strategy/race-weeks") return { body: { race_weeks: [
        { event_id: "2026-21", season: 2026, round: 21, name: "Formula 1 Missing Grand Prix 2026", circuit_id: "x", date: "2026-10-01", status: "no_timing_data" },
      ] } };
      if (url.pathname === "/api/drivers") return { body: drivers };
      if (url.pathname === "/api/constructors") return { body: [] };
      return undefined;
    });
    renderPage(<RaceStrategyPage />, "/race-week?event=2026-21&driver=a-driver");
    expect(await screen.findByText(/no timing data yet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Plan the race" })).toBeDisabled();
  });
});
