import type { ConditionEffect } from "../types/api";
import { StatusPill } from "./ui";
import { fmtNum, fmtSigned } from "../lib/format";

export const DIMENSION_LABELS: Record<string, string> = {
  wet_race: "Wet-race pace vs dry expectation",
  wet_qualifying: "Wet qualifying vs dry expectation",
  street_circuit: "Street circuits vs permanent circuits",
  high_speed_circuit: "High-speed circuits vs others",
  slow_corner_circuit: "Slow-corner circuits vs others",
};

const STATUS_TEXT: Record<ConditionEffect["status"], string> = {
  supported: "effect supported by data",
  not_distinguishable_from_zero: "not distinguishable from zero",
  insufficient_evidence: "insufficient evidence",
};

export function ConditionStatus({ c }: { c: ConditionEffect }) {
  const status = c.status === "supported" ? "good" : c.status === "insufficient_evidence" ? "warning" : "info";
  return <StatusPill status={status}>{STATUS_TEXT[c.status]}</StatusPill>;
}

export function ConditionRow({ c }: { c: ConditionEffect }) {
  const lo = c.posterior_mean - 1.645 * c.posterior_sd;
  const hi = c.posterior_mean + 1.645 * c.posterior_sd;
  return (
    <div className="rounded-md border border-line p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium">{DIMENSION_LABELS[c.dimension] ?? c.dimension}</span>
        <ConditionStatus c={c} />
      </div>
      {c.status === "insufficient_evidence" ? (
        <p className="mt-1 text-xs text-ink-muted">
          Only {c.n_sessions} session(s) and {c.n_laps} lap(s) of evidence — no estimate is shown.
        </p>
      ) : (
        <div className="mt-1 grid grid-cols-3 gap-2 text-xs tabular text-ink-2">
          <div><div className="text-ink-muted">Shrunk estimate</div>
            {c.posterior_sd === 0
              ? <span title="Estimated between-driver variance is zero: deviations are consistent with noise">0 (no between-driver variation detected)</span>
              : <>{fmtSigned(c.posterior_mean, 2, "%")} <span className="text-ink-muted">[{fmtSigned(lo, 2)}, {fmtSigned(hi, 2)}]</span></>}
          </div>
          <div><div className="text-ink-muted">Raw (± s.e.)</div>{fmtSigned(c.raw, 2, "%")} ± {fmtNum(c.raw_se, 2)}</div>
          <div><div className="text-ink-muted">Evidence</div>{c.n_sessions} sessions{c.dimension === "wet_qualifying" ? "" : ` · ${c.n_laps} laps`}</div>
        </div>
      )}
    </div>
  );
}
