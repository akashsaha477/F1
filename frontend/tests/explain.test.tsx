import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import ExplainPredictionPage from "../src/pages/ExplainPrediction";
import { drivers, events2025, prediction, seasons } from "./fixtures";
import { mockApi, renderPage } from "./helpers";

function api(predictStatus = 200) {
  return mockApi((url, init) => {
    if (url.pathname === "/api/seasons") return { body: seasons };
    if (url.pathname === "/api/events") return { body: events2025 };
    if (url.pathname === "/api/circuits") return { body: [] };
    if (url.pathname === "/api/drivers") return { body: drivers };
    if (url.pathname === "/api/predict/lap-time" && init?.method === "POST") {
      return predictStatus === 200
        ? { body: prediction }
        : { status: 422, body: { error: { code: "unsupported_scenario", message: "no form for driver a-driver" } } };
    }
    return undefined;
  });
}

describe("Explain a prediction", () => {
  it("requires a driver and race before predicting", async () => {
    api();
    renderPage(<ExplainPredictionPage />);
    const button = screen.getByRole("button", { name: /predict and explain/i });
    expect(button).toBeDisabled();
    await waitFor(() => expect(screen.getByRole("option", { name: "Alpha Driver" })).toBeInTheDocument());
    await userEvent.selectOptions(screen.getByLabelText("Driver"), "a-driver");
    await userEvent.selectOptions(screen.getByLabelText("Race", { exact: true }), "2025-12");
    expect(button).toBeEnabled();
  });

  it("shows prediction, uncertainty, evidence, warnings and model version", async () => {
    const fetch = api();
    renderPage(<ExplainPredictionPage />, "/explain?driver=a-driver&event=2025-12");
    await waitFor(() => expect(screen.getByRole("option", { name: "Alpha Driver" })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /predict and explain/i }));
    expect(await screen.findByText(/0.71% faster than the session reference/)).toBeInTheDocument();
    expect(screen.getByText("−0.71%")).toBeInTheDocument();
    expect(screen.getByText("Single-lap interval")).toBeInTheDocument();
    expect(screen.getByText("3962")).toBeInTheDocument();
    expect(screen.getByText(/Insufficient wet-weather evidence/)).toBeInTheDocument();
    expect(screen.getByText("lap_pace_pre_event-lightgbm-test")).toBeInTheDocument();
    const post = fetch.mock.calls.find(([, init]) => (init as RequestInit | undefined)?.method === "POST");
    const body = JSON.parse(String((post![1] as RequestInit).body));
    expect(body).toMatchObject({ driver_id: "a-driver", as_of_event_id: "2025-12", horizon: "pre_event", compound: "MEDIUM" });
  });

  it("explains unsupported scenarios instead of failing silently", async () => {
    api(422);
    renderPage(<ExplainPredictionPage />, "/explain?driver=a-driver&event=2025-12");
    await waitFor(() => expect(screen.getByRole("option", { name: "Alpha Driver" })).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: /predict and explain/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("cannot be answered from the stored data");
    expect(screen.getByRole("alert")).toHaveTextContent("no form for driver a-driver");
  });
});
