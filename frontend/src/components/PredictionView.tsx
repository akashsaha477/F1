import { Link } from "react-router-dom";
import type { LapPrediction } from "../types/api";
import { Card, KV, StatTile, StatusPill, Warnings } from "./ui";
import { ContributionChart } from "../charts/ContributionChart";
import { IntervalChart } from "../charts/IntervalChart";
import { CHART } from "../charts/EChart";
import { fmtNum, fmtPct, fmtSec, groupLabel, titleFromId } from "../lib/format";

const EVIDENCE_LABELS: Record<string, string> = {
  driver_representative_laps: "Driver's representative race laps",
  driver_events: "Driver's previous races (in dataset)",
  driver_laps_at_circuit: "Driver's laps at this circuit",
  driver_events_at_circuit: "Driver's races at this circuit",
  driver_laps_on_compound: "Driver's laps on this compound",
  driver_wet_laps: "Driver's wet-tyre laps",
  team_events: "Team's previous races",
  training_laps_on_compound: "All drivers' laps on this compound",
  driver_events_at_circuit_prior_seasons: "Driver × circuit history (seasons)",
  cutoff: "Evidence cut-off (exclusive)",
};

export function PredictionView({ p }: { p: LapPrediction }) {
  const pred = p.prediction;
  const rows = [
    { label: `Single lap (${Math.round(pred.interval.level * 100)}% conformal)`, point: pred.value_pct, lo: pred.interval.lo_pct, hi: pred.interval.hi_pct, color: CHART.series[0] },
    ...(pred.model_uncertainty ? [{ label: "Expected pace (bootstrap 5–95%)", point: pred.value_pct, lo: pred.model_uncertainty.lo_pct, hi: pred.model_uncertainty.hi_pct, color: CHART.series[2] }] : []),
  ];
  const ev = p.evaluation.holdout;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <StatTile label="Predicted pace vs session reference" value={fmtPct(pred.value_pct)} hint={pred.value_pct < 0 ? "faster than reference" : "slower than reference"} />
        <StatTile label="In seconds per lap" value={fmtSec(pred.value_s)} hint={p.reference_lap_s ? `reference lap ≈ ${fmtNum(p.reference_lap_s, 1)} s` : "no reference lap"} />
        <StatTile label="Single-lap interval" value={`${fmtPct(pred.interval.lo_pct, 1)} … ${fmtPct(pred.interval.hi_pct, 1)}`} hint={`${pred.interval.condition_group} conditions`} />
        <StatTile label="Model baseline (average output)" value={fmtPct(p.baseline.value_pct)} hint="contributions add up from here" />
      </div>

      <Card title="Explanation" subtitle="Generated from the payload below by a fixed template; no free-text generation">
        <p className="text-sm leading-relaxed text-ink-2">{p.narrative}</p>
        {p.warnings.length > 0 && <div className="mt-3"><Warnings items={p.warnings} /></div>}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Feature contributions" subtitle="Exact TreeSHAP values (% of lap); how the model uses each input, not causal effects">
          <ContributionChart items={p.contributions} title="Feature contributions to the prediction" />
        </Card>
        <div className="space-y-4">
          <Card title="Uncertainty" subtitle="Lap-to-lap interval vs. uncertainty of the expected value">
            <IntervalChart rows={rows} title="Prediction intervals" />
          </Card>
          <Card title="By feature group">
            <ul className="space-y-1 text-sm tabular">
              {p.group_contributions.map((g) => (
                <li key={g.group} className="flex justify-between">
                  <span className="text-ink-2">{groupLabel(g.group)}</span>
                  <span>{fmtPct(g.contribution_pct, 3)} {g.contribution_s !== null && <span className="text-ink-muted">({fmtSec(g.contribution_s, 3)})</span>}</span>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Evidence" subtitle="Observations before the cut-off that inform this prediction">
          <KV rows={Object.entries(p.evidence).map(([k, v]) => [EVIDENCE_LABELS[k] ?? k, String(v)])} />
          <div className="mt-3 flex flex-wrap gap-2 text-xs">
            <Link className="text-accent" to={`/drivers?driver=${p.inputs.driver_id}`}>Driver's races →</Link>
            <Link className="text-accent" to={`/tracks?circuit=${p.inputs.circuit_id}`}>Circuit →</Link>
          </div>
        </Card>
        <Card title="Assumptions & extrapolation">
          <ul className="list-disc space-y-1 pl-4 text-sm text-ink-2">
            {p.assumptions.map((a) => <li key={a}>{a}</li>)}
          </ul>
          {p.extrapolation.length > 0 && (
            <div className="mt-3 space-y-1">
              {p.extrapolation.map((f) => (
                <div key={f.feature} className="text-xs">
                  <StatusPill status={f.outside_observed_range ? "serious" : "info"}>{f.outside_observed_range ? "outside training range" : "edge of training data"}</StatusPill>{" "}
                  <span className="text-ink-2">{f.label}: {fmtNum(f.value, 2)} (central 98%: {fmtNum(f.p01, 2)} … {fmtNum(f.p99, 2)})</span>
                </div>
              ))}
            </div>
          )}
        </Card>
        <Card title="Model" subtitle={p.target_definition}>
          <KV rows={[
            ["Model", p.model],
            ["Version", <span className="break-all text-xs">{p.model_version}</span>],
            ["Horizon", titleFromId(p.horizon.replace("_", "-"))],
            ["Trained on", p.evaluation.train_period],
            ["Holdout MAE", `${fmtNum(ev.mae, 3)}% (${fmtNum(ev.mae_seconds, 3)} s)`],
            ["Holdout 90% coverage", `${fmtNum(ev.coverage * 100, 1)}%`],
          ]} />
          <ul className="mt-3 list-disc space-y-1 pl-4 text-xs text-ink-muted">
            {p.limitations.map((l) => <li key={l}>{l}</li>)}
          </ul>
        </Card>
      </div>
    </div>
  );
}
