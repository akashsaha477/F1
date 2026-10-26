import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useComparison, useConstructorName, useDriverCompare, useDrivers } from "../api/hooks";
import { Button, Card, EmptyState, ErrorState, Field, InsufficientEvidence, KV, LoadingState, PageHeader, Select, StatTile, Warnings } from "../components/ui";
import { ScenarioForm, defaultScenario, scenarioPayload, type ScenarioState } from "../components/ScenarioForm";
import { ConditionRow } from "../components/conditions";
import { HeadToHeadChart } from "../charts/HeadToHeadChart";
import { ContributionChart } from "../charts/ContributionChart";
import { IntervalChart } from "../charts/IntervalChart";
import { CHART } from "../charts/EChart";
import { fmtNum, fmtPct, fmtSec, titleFromId } from "../lib/format";
import type { ProfileSeason } from "../types/api";

const ROWS: { key: keyof ProfileSeason; label: string; fmt: (v: number) => string }[] = [
  { key: "race_pace_adj", label: "Team-adjusted race pace", fmt: (v) => fmtPct(v) },
  { key: "team_effect", label: "Team-season effect (car proxy)", fmt: (v) => fmtPct(v) },
  { key: "quali_adj", label: "Team-adjusted qualifying", fmt: (v) => fmtPct(v) },
  { key: "teammate_gap_race", label: "Race gap to team-mate", fmt: (v) => fmtPct(v) },
  { key: "quali_teammate_gap", label: "Qualifying gap to team-mate", fmt: (v) => fmtPct(v) },
  { key: "consistency_sd", label: "Lap-to-lap robust SD", fmt: (v) => `${fmtNum(v, 3)}%` },
  { key: "lap1_gain_mean", label: "Lap-1 positions gained", fmt: (v) => fmtNum(v, 2) },
  { key: "n_dry_races", label: "Dry races (evidence)", fmt: (v) => String(v) },
];

export default function DriverComparisonPage() {
  const [params, setParams] = useSearchParams();
  const a = params.get("a") ?? "";
  const b = params.get("b") ?? "";
  const [season, setSeason] = useState<number | 0>(0);
  const drivers = useDrivers({ scope: "lap" });
  const cmp = useDriverCompare(a || undefined, b || undefined, season || undefined);
  const [scenario, setScenario] = useState<ScenarioState>({ ...defaultScenario, mode: "next" });
  const [commonCar, setCommonCar] = useState(false);
  const model = useComparison();
  const teamName = useConstructorName();
  const name = (id: string) => drivers.data?.items.find((d) => d.driver_id === id)?.name ?? titleFromId(id);
  const set = (k: "a" | "b", v: string) => setParams((p) => { p.set(k, v); return p; });
  const opts = [{ value: "", label: "Select driver" }, ...(drivers.data?.items ?? []).map((d) => ({ value: d.driver_id, label: d.name }))];

  const seasonsBoth = useMemo(() => {
    if (!cmp.data) return [] as number[];
    const sa = new Set(cmp.data.profiles[a]?.map((p) => p.season));
    return (cmp.data.profiles[b] ?? []).map((p) => p.season).filter((s) => sa.has(s));
  }, [cmp.data, a, b]);

  const pa = cmp.data?.profiles[a] ?? [];
  const pb = cmp.data?.profiles[b] ?? [];
  const latest = seasonsBoth.at(-1);
  const ra = pa.find((p) => p.season === (season || latest));
  const rb = pb.find((p) => p.season === (season || latest));
  const h = cmp.data?.head_to_head;

  return (
    <div className="space-y-5">
      <PageHeader title="Driver comparison"
        description="Compare two drivers on team-adjusted pace, team-mate gaps, consistency and condition-specific evidence, then ask the model for an expected pace difference under a stated scenario." />
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Driver A"><Select ariaLabel="Driver A" value={a} onChange={(v) => set("a", v)} options={opts} /></Field>
        <Field label="Driver B"><Select ariaLabel="Driver B" value={b} onChange={(v) => set("b", v)} options={opts} /></Field>
        <Field label="Season"><Select ariaLabel="Comparison season" value={season} onChange={(v) => setSeason(v)}
          options={[{ value: 0, label: "All seasons" }, ...[2022, 2023, 2024, 2025].map((s) => ({ value: s, label: String(s) }))]} /></Field>
      </div>
      {(!a || !b) && <EmptyState>Select two drivers.</EmptyState>}
      {a && b && a === b && <EmptyState>Choose two different drivers.</EmptyState>}
      {cmp.isLoading && <LoadingState />}
      {cmp.error && <ErrorState error={cmp.error} />}

      {cmp.data && (
        <>
          {(h?.summary?.n_sessions ?? 0) < 5 && (
            <InsufficientEvidence>
              {name(a)} and {name(b)} share only {h?.summary?.n_sessions ?? 0} dry race session(s) in the selected period;
              direct comparisons are weak. Model-based comparisons below rely on form features instead.
            </InsufficientEvidence>
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title={`Fingerprint ${season || latest || ""}`} subtitle="Negative = faster. Team-mate gaps compare each driver with their own team-mate.">
              {ra || rb ? (
                <table className="w-full text-left text-sm tabular">
                  <thead className="text-xs text-ink-muted"><tr><th className="py-1">Metric</th><th>{name(a)}</th><th>{name(b)}</th></tr></thead>
                  <tbody>
                    <tr className="border-t border-line"><td className="py-1 text-ink-2">Team</td><td>{teamName(ra?.main_team)}</td><td>{teamName(rb?.main_team)}</td></tr>
                    {ROWS.map((r) => (
                      <tr key={String(r.key)} className="border-t border-line">
                        <td className="py-1 text-ink-2">{r.label}</td>
                        <td>{ra && ra[r.key] !== null && ra[r.key] !== undefined ? r.fmt(ra[r.key] as number) : "—"}</td>
                        <td>{rb && rb[r.key] !== null && rb[r.key] !== undefined ? r.fmt(rb[r.key] as number) : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : <EmptyState>No common season with profiles.</EmptyState>}
            </Card>
            <Card title="Team-adjusted race pace by season" subtitle="90% posterior intervals">
              <IntervalChart title="Team-adjusted race pace by season for both drivers" rows={[
                ...pa.map((p) => ({ label: `${p.season} ${name(a)}`, point: p.race_pace_adj, lo: p.race_pace_adj_lo, hi: p.race_pace_adj_hi, color: CHART.series[0] })),
                ...pb.map((p) => ({ label: `${p.season} ${name(b)}`, point: p.race_pace_adj, lo: p.race_pace_adj_lo, hi: p.race_pace_adj_hi, color: CHART.series[1] })),
              ].sort((x, y) => x.label.localeCompare(y.label))} />
              <div className="mt-1 flex gap-4 text-xs text-ink-muted">
                <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: CHART.series[0] }} />{name(a)}</span>
                <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: CHART.series[1] }} />{name(b)}</span>
              </div>
            </Card>
          </div>

          <Card title="Head-to-head in shared sessions" subtitle={h?.summary?.note}>
            {h?.summary ? (
              <>
                <div className="mb-3 grid grid-cols-2 gap-3 md:grid-cols-4">
                  <StatTile label={`Median difference (${name(a)} − ${name(b)})`} value={fmtPct(h.summary.median_diff)}
                    hint={h.summary.ci90 ? `90% CI ${fmtPct(h.summary.ci90[0])} … ${fmtPct(h.summary.ci90[1])}` : "too few sessions for a CI"} />
                  <StatTile label="Dry sessions shared" value={h.summary.n_sessions} hint={`${h.summary.n_same_team} as team-mates`} />
                  <StatTile label={`${name(a)} faster in`} value={`${fmtNum((h.summary.a_faster_share ?? 0) * 100, 0)}%`} hint="of shared dry sessions" />
                </div>
                <HeadToHeadChart sessions={h.sessions} aName={name(a)} bName={name(b)} />
                <p className="text-xs text-ink-muted">Faded bars are wet or mixed sessions (excluded from the summary).</p>
              </>
            ) : <EmptyState>No shared race sessions.</EmptyState>}
          </Card>

          <div className="grid gap-4 md:grid-cols-2">
            {[a, b].map((d) => (
              <Card key={d} title={`${name(d)}: condition-specific evidence`}>
                <div className="space-y-2">
                  {(cmp.data!.conditions[d] ?? []).map((c) => <ConditionRow key={c.dimension} c={c} />)}
                  {(cmp.data!.conditions[d] ?? []).length === 0 && <p className="text-sm text-ink-muted">No condition-specific evidence.</p>}
                </div>
              </Card>
            ))}
          </div>

          <Card title="Model-based comparison under a scenario" subtitle="Model D: difference in expected representative race-lap pace from the production lap-pace model">
            <ScenarioForm value={scenario} onChange={setScenario}>
              <Field label="Car assumption">
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={commonCar} onChange={(e) => setCommonCar(e.target.checked)} />
                  Give {name(b)} the team features of {name(a)}</label>
              </Field>
            </ScenarioForm>
            <div className="mt-3">
              <Button disabled={model.isPending || (scenario.mode === "event" && !scenario.event_id)}
                onClick={() => model.mutate({ driver_ids: [a, b], common_car: commonCar, ...scenarioPayload(scenario) })}>
                {model.isPending ? "Comparing…" : "Compare under scenario"}
              </Button>
            </div>
            {model.error && <div className="mt-3"><ErrorState error={model.error} /></div>}
            {model.data && (
              <div className="mt-4 space-y-4">
                <p className="text-sm leading-relaxed text-ink-2">{model.data.narrative}</p>
                <Warnings items={model.data.warnings} />
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <StatTile label={`Expected difference (${name(a)} − ${name(b)})`} value={fmtPct(model.data.difference.value_pct)}
                    hint={fmtSec(model.data.difference.value_s)} />
                  {model.data.difference.model_uncertainty && (
                    <StatTile label="Bootstrap 5–95%" value={`${fmtPct(model.data.difference.model_uncertainty.lo_pct, 2)} … ${fmtPct(model.data.difference.model_uncertainty.hi_pct, 2)}`}
                      hint={`${name(a)} faster in ${fmtNum((model.data.difference.model_uncertainty.prob_a_faster ?? 0) * 100, 0)}% of refits`} />
                  )}
                  {Object.entries(model.data.counterfactuals).map(([k, v]) => (
                    <StatTile key={k} label={k === "same_car" ? "With identical team features" : `With ${v.compound ?? ""} conditions`}
                      value={v.difference_pct !== undefined ? fmtPct(v.difference_pct) : "—"} hint={v.error ?? v.description} />
                  ))}
                </div>
                <div className="grid gap-4 lg:grid-cols-2">
                  <div>
                    <div className="mb-1 text-xs text-ink-muted">Contributions to the difference (TreeSHAP of A minus B)</div>
                    <ContributionChart items={model.data.difference.contributions} title="Contributions to predicted pace difference" />
                  </div>
                  <div>
                    <div className="mb-1 text-xs text-ink-muted">Evidence behind each prediction</div>
                    {model.data.drivers.map((d) => (
                      <div key={d.driver_id} className="mb-3">
                        <div className="text-sm font-medium">{d.name} <span className="text-xs text-ink-muted">({teamName(d.constructor_id)})</span></div>
                        <KV rows={[["Representative laps", String(d.evidence.driver_representative_laps)], ["Previous races", String(d.evidence.driver_events)],
                          ["Laps at circuit", String(d.evidence.driver_laps_at_circuit)], ["Laps on compound", String(d.evidence.driver_laps_on_compound)]]} />
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
