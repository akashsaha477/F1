export const fmtNum = (v: number | null | undefined, d = 2) =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : v.toFixed(d);

export const fmtSigned = (v: number | null | undefined, d = 2, unit = "") =>
  v === null || v === undefined || Number.isNaN(v) ? "—" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${Math.abs(v).toFixed(d)}${unit}`;

export const fmtPct = (v: number | null | undefined, d = 2) => fmtSigned(v, d, "%");
export const fmtSec = (v: number | null | undefined, d = 2) => fmtSigned(v, d, " s");

export const fmtLapTime = (s: number | null | undefined) => {
  if (s === null || s === undefined || Number.isNaN(s)) return "—";
  const m = Math.floor(s / 60);
  const rest = s - m * 60;
  return m > 0 ? `${m}:${rest.toFixed(3).padStart(6, "0")}` : rest.toFixed(3);
};

export const compact = (v: number | null | undefined) => {
  if (v === null || v === undefined) return "—";
  if (Math.abs(v) >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  if (Math.abs(v) >= 1e3) return `${(v / 1e3).toFixed(1)}K`;
  return String(Math.round(v));
};

export const titleFromId = (id: string | null | undefined) =>
  (id ?? "").split("-").filter(Boolean).map((w) => w[0].toUpperCase() + w.slice(1)).join(" ");

export const GROUP_LABELS: Record<string, string> = {
  driver: "Driver form",
  team: "Team / car",
  weekend: "Weekend (qualifying)",
  track: "Track",
  corner: "Corner profile",
  tyre: "Tyre",
  weather: "Weather",
  race_context: "Race phase",
  interaction: "Driver × circuit",
  other: "Other",
};

export const groupLabel = (g: string) => GROUP_LABELS[g] ?? g;

// Validated with the dataviz palette checker against the dark surface (orange / blue / aqua pass all-pairs);
// tyre-wall colours (red / yellow / white) were rejected because red and yellow are too close.
export const COMPOUND_COLORS: Record<string, string> = {
  SOFT: "#d95926",
  MEDIUM: "#3987e5",
  HARD: "#199e70",
  INTERMEDIATE: "#c98500",
  WET: "#9085e9",
  UNKNOWN: "#898781",
};
