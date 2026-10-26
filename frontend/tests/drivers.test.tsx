import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import DriverExplorerPage from "../src/pages/DriverExplorer";
import { drivers, seasons } from "./fixtures";
import { mockApi, renderPage } from "./helpers";

const perf = {
  driver: drivers.items[1],
  results_summary: { starts: 20, wins: 2, podiums: 5, points: 30, poles: 1, outcomes: { finished: 15, mechanical_or_reliability: 5 },
    mean_positions_gained: 1.5, positions_gained_n: 15, seasons: [1950], note: "Retirement categories describe the recorded reason only." },
  events: [],
};

describe("Driver explorer", () => {
  it("filters by search and shows a results-only profile for historical drivers", async () => {
    const fetch = mockApi((url) => {
      if (url.pathname === "/api/seasons") return { body: seasons };
      if (url.pathname === "/api/constructors") return { body: [] };
      if (url.pathname === "/api/drivers") {
        const q = url.searchParams.get("q");
        return { body: q ? { ...drivers, items: drivers.items.filter((d) => d.name.toLowerCase().includes(q)), total: 1 } : drivers };
      }
      if (url.pathname === "/api/drivers/old-driver/performance") return { body: perf };
      return undefined;
    });
    renderPage(<DriverExplorerPage />, "/drivers");
    expect(await screen.findByText("Alpha Driver")).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Search drivers"), "old");
    await waitFor(() => expect(screen.queryByText("Alpha Driver")).not.toBeInTheDocument());
    expect(fetch.mock.calls.some(([u]) => String(u).includes("q=old"))).toBe(true);
    await userEvent.click(screen.getByText("Old Driver"));
    expect(await screen.findByText("results-only profile")).toBeInTheDocument();
    expect(screen.getByText("Mechanical Or Reliability")).toBeInTheDocument();
    expect(screen.queryByText("Race pace by event")).not.toBeInTheDocument();
  });

  it("shows an empty state when nothing matches", async () => {
    mockApi((url) => {
      if (url.pathname === "/api/seasons") return { body: seasons };
      if (url.pathname === "/api/constructors") return { body: [] };
      if (url.pathname === "/api/drivers") return { body: { items: [], total: 0, limit: 200, offset: 0 } };
      return undefined;
    });
    renderPage(<DriverExplorerPage />, "/drivers");
    expect(await screen.findByText("No drivers match these filters.")).toBeInTheDocument();
  });
});
