import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import DriverComparisonPage from "../src/pages/DriverComparison";
import { drivers } from "./fixtures";
import { mockApi, renderPage } from "./helpers";

const profile = (driver_id: string, v: number) => ({
  driver_id, season: 2025, main_team: "team-a", teams: "team-a", n_dry_races: 20, n_laps: 900, race_pace_adj: v,
  race_pace_adj_sd: 0.1, race_pace_adj_lo: v - 0.16, race_pace_adj_hi: v + 0.16, race_pace_raw: v, team_effect: -0.2,
  team_effect_sd: 0.1, teammate_gap_race: 0.1, teammate_gap_race_lo: 0, teammate_gap_race_hi: 0.2, n_teammate_races: 3,
  consistency_sd: 0.4, consistency_lo: 0.3, consistency_hi: 0.5, quali_adj: -0.1, quali_adj_sd: 0.1, quali_gap_median: 0.5,
  quali_teammate_gap: 0.05, quali_teammate_gap_lo: 0, quali_teammate_gap_hi: 0.1, n_quali: 20, n_quali_teammate: 20,
  lap1_gain_mean: 0.2, n_lap1: 20, positions_gained_mean: 1, n_classified: 18, race_pace_adj_pctile: 80,
  consistency_pctile: 50, quali_adj_pctile: 60, rank_reference: "season drivers",
});

const compare = {
  drivers: ["a-driver", "b-driver"],
  profiles: { "a-driver": [profile("a-driver", -0.3)], "b-driver": [profile("b-driver", 0.1)] },
  conditions: {
    "a-driver": [{ driver_id: "a-driver", dimension: "wet_race", raw: -0.5, raw_se: 0.6, posterior_mean: 0, posterior_sd: 0, tau: 0,
      n_sessions: 1, n_laps: 12, status: "insufficient_evidence", unit: "% of lap", seasons: "2022-2025" }],
    "b-driver": [],
  },
  head_to_head: {
    sessions: [{ session_id: "2025-01-R", season: 2025, condition: "dry", same_team: false, diff: -0.2, se: 0.1 }],
    summary: { n_sessions: 1, n_same_team: 0, median_diff: -0.2, ci90: null, a_faster_share: 1, note: "Includes the car." },
  },
  meta: { identification_note: "", race_model: { variances: {}, n_obs: 1, formula: "" }, quali_model: { variances: {}, n_obs: 1, formula: "" }, thresholds: {}, seasons: [2022, 2025] },
};

describe("Driver comparison", () => {
  it("warns about insufficient comparable data and hides unsupported condition estimates", async () => {
    mockApi((url) => {
      if (url.pathname === "/api/drivers") return { body: { ...drivers, items: [...drivers.items, { ...drivers.items[0], driver_id: "b-driver", name: "Beta Driver" }] } };
      if (url.pathname === "/api/drivers/compare") return { body: compare };
      if (url.pathname === "/api/constructors") return { body: [{ constructor_id: "team-a", name: "Team A", full_name: null }] };
      if (url.pathname === "/api/seasons") return { body: [] };
      if (url.pathname === "/api/circuits") return { body: [] };
      return undefined;
    });
    renderPage(<DriverComparisonPage />, "/compare?a=a-driver&b=b-driver");
    expect(await screen.findByText(/share only 1 dry race session/)).toBeInTheDocument();
    expect(screen.getByText("insufficient evidence")).toBeInTheDocument();
    expect(screen.getByText(/no estimate is shown/)).toBeInTheDocument();
    expect(screen.getAllByText("Team A").length).toBeGreaterThan(0);
    expect(screen.getByText("−0.30%")).toBeInTheDocument();
  });
});
