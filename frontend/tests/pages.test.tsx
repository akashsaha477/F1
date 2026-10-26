import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import TyreWeatherLabPage from "../src/pages/TyreWeatherLab";
import RaceExplorerPage from "../src/pages/RaceExplorer";
import ScenarioLabPage from "../src/pages/ScenarioLab";
import MethodologyPage from "../src/pages/Methodology";
import { drivers, seasons } from "./fixtures";
import { mockApi, renderPage } from "./helpers";

const tyres = {
  by_compound: [{ season: 2025, compound: "MEDIUM", slope_pct: 0.06, ci_lo: 0.05, ci_hi: 0.07, n_stints: 100, n_sessions: 20, slope_s_per_lap: 0.05 }],
  by_circuit: [], temperature: [{ compound: "MEDIUM", slope_per_degC: 0.001, se: 0.001, ci_lo: -0.001, ci_hi: 0.003, intercept: 0, n_sessions: 50, temp_min: 20, temp_max: 50 }],
  session_points: [], stints: [],
  driver_effects: [{ driver_id: "a-driver", season: 2025, compound: "MEDIUM", raw: 0.01, raw_se: 0.01, posterior_mean: 0, posterior_sd: 0, tau: 0, n_stints: 2, n_sessions: 2, status: "insufficient_evidence" }],
  evaluation: { n_predicted_laps: 100, n_events: 5, mae_pct: { flat: 1.0, compound: 0.9 }, mae_s: { flat: 0.9, compound: 0.8 },
    comparisons: { compound_vs_flat: { estimate: -0.1, lo: -0.2, hi: -0.01, significant: true }, driver_vs_circuit: { estimate: 0.001, lo: -0.001, hi: 0.003, significant: false } },
    protocol: "walk-forward" },
  definitions: { slope_pct: "Fuel-corrected change" }, limitations: ["a", "SOFT/MEDIUM/HARD are relative", "Temperature is confounded"],
};

describe("Tyre & weather lab", () => {
  it("shows degradation evidence, prediction checks and insufficient-evidence states", async () => {
    mockApi((url) => {
      if (url.pathname === "/api/tyres/degradation") return { body: tyres };
      if (url.pathname === "/api/conditions") return { body: { dimension: "wet_race", definition: "wet races", tau: 0, thresholds: {},
        rows: [{ driver_id: "a-driver", dimension: "wet_race", raw: -0.2, raw_se: 0.3, posterior_mean: 0, posterior_sd: 0, tau: 0, n_sessions: 1, n_laps: 10, status: "insufficient_evidence", unit: "%", seasons: "2022-2025" }] } };
      if (url.pathname === "/api/circuits") return { body: [] };
      if (url.pathname === "/api/drivers") return { body: drivers };
      return undefined;
    });
    renderPage(<TyreWeatherLabPage />, "/tyres-weather");
    expect(await screen.findByText("Does driver-specific degradation help prediction?")).toBeInTheDocument();
    expect(await screen.findByText(/compound vs flat/)).toBeInTheDocument();
    expect(screen.getAllByText("improves").length).toBe(1);
    expect(await screen.findByText(/no driver-to-driver differences beyond noise/)).toBeInTheDocument();
    expect(screen.getAllByText("insufficient evidence").length).toBeGreaterThan(0);
  });
});

describe("Race & lap explorer", () => {
  it("prompts for an event and lists events with lap data", async () => {
    mockApi((url) => {
      if (url.pathname === "/api/events") return { body: [{ event_id: "2025-01", season: 2025, round: 1, circuit_id: "x", circuit_name: "Test Ring", lap_sessions: 5 },
        { event_id: "2025-02", season: 2025, round: 2, circuit_id: "y", circuit_name: "No Data", lap_sessions: 0 }] };
      return undefined;
    });
    renderPage(<RaceExplorerPage />, "/races");
    expect(await screen.findByText("Select an event.")).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: "1. Test Ring" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "2. No Data" })).not.toBeInTheDocument();
  });
});

describe("Scenario laboratory", () => {
  it("shows single-change responses with the non-causal note", async () => {
    mockApi((url, init) => {
      if (url.pathname === "/api/seasons") return { body: seasons };
      if (url.pathname === "/api/circuits") return { body: [{ circuit_id: "silverstone", name: "Silverstone", has_lap_data: true }] };
      if (url.pathname === "/api/drivers") return { body: drivers };
      if (url.pathname === "/api/scenarios" && init?.method === "POST") return { body: { base_prediction_pct: -0.5, note: "They describe the model's response, not the causal effect of an intervention.",
        changes: [{ change: "compound -> SOFT", feature: "compound", new_value: "SOFT", delta_pct: -0.3, supported: true },
          { change: "Tyre age -> 30.0", feature: "tyre_life_laps", new_value: 30, delta_pct: 0.4, supported: true, curve: [{ value: 1, prediction_pct: -0.6 }, { value: 30, prediction_pct: -0.1 }] }] } };
      return undefined;
    });
    renderPage(<ScenarioLabPage />, "/scenarios");
    await screen.findByRole("option", { name: "Alpha Driver" });
    await userEvent.selectOptions(screen.getByLabelText("Driver"), "a-driver");
    await userEvent.click(screen.getByRole("button", { name: /explore changes/i }));
    expect(await screen.findByText(/They describe the model.s response/)).toBeInTheDocument();
    expect(screen.getByText("Sweep: tyre life laps")).toBeInTheDocument();
  });
});

describe("Methodology", () => {
  it("renders limitations and licences from the API", async () => {
    mockApi((url) => {
      if (url.pathname === "/api/methodology") return { body: { cleaning: { lap_exclusions: { pit_in_lap: "Lap ended in the pit lane" }, clean_lap: "Clean.", representative_lap: "Rep.", session_reference: "Ref.", fatal_vs_warning: "Fatal." },
        limitations: ["Brake data is on/off only."], licences: { f1db: "CC BY 4.0" } } };
      if (url.pathname === "/api/models") return { body: { production: {}, models: [] } };
      return { status: 404, body: { error: { code: "not_found", message: "missing" } } };
    });
    renderPage(<MethodologyPage />, "/methodology");
    expect(await screen.findByText("Brake data is on/off only.")).toBeInTheDocument();
    expect(screen.getByText(/CC BY 4.0/)).toBeInTheDocument();
    expect(screen.getByText("Lap ended in the pit lane")).toBeInTheDocument();
  });
});
