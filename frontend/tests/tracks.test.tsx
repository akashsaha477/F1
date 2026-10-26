import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import TrackExplorerPage from "../src/pages/TrackExplorer";
import { mockApi, renderPage } from "./helpers";

const corner = (id: string, x: number, category: string) => ({
  corner_id: id, method: "marker", n_markers: 1, entry_s: x * 10, apex_s: x * 10 + 50, exit_s: x * 10 + 100, length_m: 100,
  heading_change_deg: 90, direction: "left", entry_speed_ref: 300, min_speed_ref: category === "slow" ? 90 : 250,
  exit_speed_ref: 280, min_throttle_ref: 0, x, y: x, category, is_hairpin: false, is_chicane: false, is_sweeper: false,
  is_sequence: false, sector: 1,
});

const layout = {
  circuit_id: "test-ring", session_id: "2025-01-Q", season: 2025, layout_id: "x", rotation_deg: 0, length_m: 1000,
  reference: { driver_id: "a-driver", lap: 10, lap_time_s: 80 }, segmentation_method: "marker",
  marker_validation: { status: "markers_used", precision: 1, recall: 0.9, median_apex_error_m: 10, median_marker_offset_m: 0.6 },
  sector_bounds_m: null,
  track: Array.from({ length: 50 }, (_, i) => ({ s: i * 20, x: Math.cos(i / 8) * 100, y: Math.sin(i / 8) * 100, speed_ref: 100 + i, throttle_ref: 100 })),
  corners: [corner("T1", 10, "slow"), corner("T2", 40, "fast")], inferred_segments: [], sectors: [],
  available_sessions: [{ session_id: "2025-01-Q", season: 2025, circuit_layout_id: "x", reference_driver: "a-driver", reference_lap_time_s: 80 }],
  category_rules: { slow_max_kph: 125, fast_min_kph: 200, flat_out_min_throttle: 95 }, notes: ["Markers from FastF1."],
};

const metric = (driver: string, t: number) => ({
  driver_id: driver, constructor_id: "team-a", lap_number: 5, lap_time_s: 80, corner_id: "T1", category: "slow", sector: 1,
  segment_time_s: t, delta_to_best_s: t - 3, delta_to_teammate_s: null, teammate_comparable: false, entry_speed_kph: 300,
  min_speed_kph: 90, exit_speed_kph: 250, brake_onset_before_apex_m: 80, braking_duration_s: 1.2, full_throttle_delay_s: 1.5,
  min_gear: 3, max_decel_proxy_ms2: 40, quality: "ok",
});

describe("Track explorer", () => {
  it("shows segmentation quality and corner detail on selection", async () => {
    mockApi((url) => {
      if (url.pathname === "/api/circuits") return { body: [{ circuit_id: "test-ring", name: "Test Ring", has_lap_data: true }] };
      if (url.pathname === "/api/circuits/test-ring/layout") return { body: layout };
      if (url.pathname === "/api/circuits/test-ring/performance") {
        return { body: { circuit_id: "test-ring", session_id: "2025-01-Q", corner_id: url.searchParams.get("corner_id"),
          metrics: [metric("a-driver", 3.0), metric("b-driver", 3.1)], teammate_relative_history: [],
          measured_vs_derived: { measured: ["speed"], derived: ["segment time"] }, notes: [] } };
      }
      return undefined;
    });
    renderPage(<TrackExplorerPage />, "/tracks?circuit=test-ring");
    expect(await screen.findByText("FastF1 corner markers")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    await userEvent.click(screen.getAllByText("T1")[1]);
    expect(await screen.findByText("T1: drivers in this session")).toBeInTheDocument();
    expect(screen.getByText("Measured: speed. Derived: segment time.")).toBeInTheDocument();
  });
});
