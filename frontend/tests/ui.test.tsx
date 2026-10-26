import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ApiError } from "../src/api/client";
import { ErrorState, InsufficientEvidence, StatusPill } from "../src/components/ui";
import { fmtLapTime, fmtPct } from "../src/lib/format";

describe("ui primitives", () => {
  it("status pills carry an icon and a label, not colour alone", () => {
    render(<StatusPill status="warning">limited</StatusPill>);
    expect(screen.getByText("limited")).toBeInTheDocument();
    expect(screen.getByText("!")).toBeInTheDocument();
  });

  it("insufficient evidence and error states are explicit", () => {
    render(<><InsufficientEvidence>Only 2 wet laps.</InsufficientEvidence><ErrorState error={new ApiError(404, "not_found", "unknown session")} /></>);
    expect(screen.getByText("Insufficient evidence.")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("unknown session");
  });

  it("formats signed percentages and lap times", () => {
    expect(fmtPct(-0.5)).toBe("−0.50%");
    expect(fmtPct(0.25, 1)).toBe("+0.3%");
    expect(fmtLapTime(93.123)).toBe("1:33.123");
    expect(fmtPct(null)).toBe("—");
  });
});
