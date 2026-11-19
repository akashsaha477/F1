import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import PredictionGamePage from "../src/pages/PredictionGame";
import { mockApi, renderPage } from "./helpers";

const ids = Array.from({ length: 12 }, (_, i) => `driver-${String(i + 1).padStart(2, "0")}`);
const field = ids.map((id, i) => ({ driver_id: id, name: `Pilot ${String.fromCharCode(65 + i)}`, constructor_id: "team-x" }));
const top = (from: string[]) => from.slice(0, 10);

const rules = {
  picks: 10, max_points: 135, deadline: "Predictions close at the race start.", result: "Classified positions from F1DB.", bots: "Bots are frozen.",
  per_pick: [{ outcome: "exact", condition: "exact position", points: 10 }], bonuses: [{ name: "podium", condition: "podium set", points: 10 }],
  entrants: [], settle_protected: false, ai_enabled: false,
};
const events = {
  events: [
    { event_id: "2026-20", season: 2026, round: 20, name: "Formula 1 Past Grand Prix 2026", circuit_id: "a", date: "2026-11-15", status: "past",
      race_start_utc: "2026-11-15T14:00:00Z", deadline_utc: "2026-11-15T14:00:00Z", game_status: "settled", players: 2 },
    { event_id: "2026-21", season: 2026, round: 21, name: "Formula 1 Next Grand Prix 2026", circuit_id: "b", date: "2026-11-29", status: "upcoming",
      race_start_utc: "2026-11-29T14:00:00Z", deadline_utc: "2026-11-29T14:00:00Z", game_status: "open", players: 1 },
  ],
};
const base = (event_id: string, status: string) => ({
  event: { event_id, name: event_id === "2026-21" ? "Formula 1 Next Grand Prix 2026" : "Formula 1 Past Grand Prix 2026", season: 2026, round: 21,
    circuit_id: "b", circuit_name: "Test Ring", date: "2026-11-29", laps: 57 },
  status, deadline_utc: "2026-11-29T14:00:00Z", opened_at: "2026-11-20T10:00:00Z", field, model_warnings: [], result: null, standings: null, ai_pending: false,
});
const hidden = {
  ...base("2026-21", "open"), revealed: false, you: null,
  entries: [{ key: "apexlens", kind: "model", name: "ApexLens model", status: "ok", submitted_at: "2026-11-20T10:00:00Z" },
    { key: "bob", kind: "player", name: "Bob", status: "ok", submitted_at: "2026-11-20T11:00:00Z" }],
};
const revealed = {
  ...base("2026-21", "open"), revealed: true, you: "ann",
  entries: [
    { key: "ann", kind: "player", name: "Ann", status: "ok", submitted_at: "2026-11-21T09:00:00Z", picks: top(ids) },
    { key: "apexlens", kind: "model", name: "ApexLens model", status: "ok", submitted_at: "2026-11-20T10:00:00Z", picks: top([...ids].reverse()),
      note: "production lap-pace model; data up to 2026-11-15" },
    { key: "claude", kind: "ai", name: "Claude (AI)", status: "ok", submitted_at: "2026-11-21T09:00:05Z", picks: top(ids), rationale: "Form favours A.",
      note: "claude-test: line-up only" },
    { key: "bob", kind: "player", name: "Bob", status: "ok", submitted_at: "2026-11-20T11:00:00Z" },
  ],
};
const score = (points: number, exact: number) => ({
  points, exact, in_top_ten: 10, podium: exact > 5, winner: exact > 5, bonuses: exact > 5 ? [{ name: "podium", points: 10 }] : [],
  picks: Array.from({ length: 10 }, (_, i) => ({ position: i + 1, driver_id: ids[i], actual_position: i + 1, points: exact > 5 ? 10 : 1, outcome: exact > 5 ? "exact" : "in top ten" })),
});
const settled = {
  ...base("2026-20", "settled"), revealed: true, you: "ann", ai_pending: false,
  entries: [
    { key: "ann", kind: "player", name: "Ann", status: "ok", submitted_at: "x", picks: top(ids), score: score(110, 10) },
    { key: "apexlens", kind: "model", name: "ApexLens model", status: "ok", submitted_at: "x", picks: top([...ids].reverse()), score: score(10, 0), note: "frozen" },
  ],
  result: { settled_at: "2026-11-16T09:00:00Z", classified: field.map((f, i) => ({ position: i + 1, driver_id: f.driver_id, name: f.name, constructor_id: "team-x" })),
    not_classified: [], not_in_field: [] },
  standings: [{ rank: 1, key: "ann", name: "Ann", kind: "player", points: 110, exact: 10 }, { rank: 2, key: "apexlens", name: "ApexLens model", kind: "model", points: 10, exact: 0 }],
};
const leaderboard = {
  season: 2026, races: [{ event_id: "2026-20", name: "Formula 1 Past Grand Prix 2026", round: 20, season: 2026, date: "2026-11-15", leader: null, points: {} }],
  rows: [{ rank: 1, key: "ann", name: "Ann", kind: "player", points: 110, races: 1, exact: 10, podiums: 1, winners: 1, race_wins: 1, best_race: 110, average: 110 },
    { rank: 2, key: "apexlens", name: "ApexLens model", kind: "model", points: 10, races: 1, exact: 0, podiums: 0, winners: 0, race_wins: 0, best_race: 10, average: 10 }],
};

beforeEach(() => localStorage.clear());

describe("Prediction game", () => {
  it("takes a top ten and then reveals the model's and the AI's picks", async () => {
    let submitted: unknown = null;
    const fetchMock = mockApi((url, init) => {
      if (url.pathname === "/api/game/events") return { body: events };
      if (url.pathname === "/api/game/rules") return { body: { ...rules, ai_enabled: true } };
      if (url.pathname === "/api/game/leaderboard") return { body: { season: 2026, races: [], rows: [] } };
      if (url.pathname === "/api/game/events/2026-21/predictions" && init?.method === "POST") { submitted = JSON.parse(String(init.body)); return { body: revealed }; }
      if (url.pathname === "/api/game/events/2026-21") return { body: submitted ? revealed : hidden };
      return undefined;
    });
    renderPage(<PredictionGamePage />, "/game");
    expect(await screen.findByText("open for predictions")).toBeInTheDocument();
    expect(await screen.findByText(/Already in: ApexLens model \(model\), Bob/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit prediction" })).toBeDisabled();

    // picks first, name last: the form must survive the name being typed (it re-keys the race query)
    for (let i = 1; i <= 10; i++) await userEvent.selectOptions(screen.getByLabelText(`P${i}`), ids[i - 1]);
    await userEvent.type(screen.getByLabelText("Your name"), "Ann");
    // a driver already picked is no longer offered elsewhere
    expect(within(screen.getByLabelText("P2")).queryByRole("option", { name: /Pilot A/ })).not.toBeInTheDocument();
    expect((screen.getByLabelText("P10") as HTMLSelectElement).value).toBe(ids[9]);
    const button = screen.getByRole("button", { name: "Submit prediction" });
    expect(button).toBeEnabled();
    await userEvent.click(button);

    expect(submitted).toEqual({ player: "Ann", picks: top(ids) });
    expect(await screen.findByText("You")).toBeInTheDocument();
    expect(screen.getByText("ApexLens model")).toBeInTheDocument();
    expect(screen.getByText("Claude (AI)")).toBeInTheDocument();
    expect(screen.getByText(/Form favours A\./)).toBeInTheDocument();
    expect(screen.getByText(/picks hidden until the race starts/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Update prediction" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some((c) => String(c[0]).includes("/game/events/2026-21?player=Ann"))).toBe(true);
    expect(localStorage.getItem("apexlens.game.player")).toBe("Ann");
  });

  it("shows points, the race standings and the leaderboard for a settled race", async () => {
    mockApi((url) => {
      if (url.pathname === "/api/game/events") return { body: events };
      if (url.pathname === "/api/game/rules") return { body: rules };
      if (url.pathname === "/api/game/leaderboard") return { body: leaderboard };
      if (url.pathname === "/api/game/events/2026-20") return { body: settled };
      return undefined;
    });
    renderPage(<PredictionGamePage />, "/game?event=2026-20");
    expect(await screen.findByText("settled")).toBeInTheDocument();
    expect((await screen.findAllByText("110 pts")).length).toBe(3); // the "Top scorer" and "You" tiles and the table header
    expect(screen.getAllByText("10 pts").length).toBeGreaterThan(0);
    // with the AI entrant off, nothing on the page mentions it
    expect(screen.queryByText(/Claude \(AI\)/)).not.toBeInTheDocument();
    expect(screen.queryByText(/the AI/)).not.toBeInTheDocument();
    expect(await screen.findByText("Leaderboard · 2026")).toBeInTheDocument();
    expect(await screen.findByText("1 race scored")).toBeInTheDocument();
    expect(await screen.findByText("Up to 135 points per race")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Submit prediction" })).not.toBeInTheDocument();
  });

  it("offers to fetch the result once a race is locked, with the admin token when the server wants one", async () => {
    let settleBody: unknown = null;
    let settleHeaders: Record<string, string> = {};
    mockApi((url, init) => {
      if (url.pathname === "/api/game/events") return { body: { events: [{ ...events.events[1], game_status: "locked" }] } };
      if (url.pathname === "/api/game/rules") return { body: { ...rules, settle_protected: true } };
      if (url.pathname === "/api/game/leaderboard") return { body: { season: 2026, races: [], rows: [] } };
      if (url.pathname === "/api/game/events/2026-21/settle" && init?.method === "POST") {
        settleBody = JSON.parse(String(init.body)); settleHeaders = init.headers as Record<string, string>; return { body: settled };
      }
      if (url.pathname === "/api/game/events/2026-21") return { body: { ...revealed, status: "locked", you: null } };
      return undefined;
    });
    renderPage(<PredictionGamePage />, "/game");
    const button = await screen.findByRole("button", { name: "Fetch results & score" });
    expect(button).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Admin token"), "s3cret");
    await userEvent.click(button);
    expect(settleBody).toEqual({ fetch: true });
    expect(settleHeaders["X-Admin-Token"]).toBe("s3cret");
    expect(await screen.findByText("No race scored yet. Predict the next one, then settle it after the weekend.")).toBeInTheDocument();
  });
});
