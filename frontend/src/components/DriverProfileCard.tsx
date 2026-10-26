import { useEffect, useState } from "react";
import { useConstructorName, useDriverProfile } from "../api/hooks";
import { ApiError } from "../api/client";
import { Card, ErrorState, LoadingState, Select, StatusPill } from "./ui";
import { ConditionRow } from "./conditions";
import { IntervalChart } from "../charts/IntervalChart";
import { CHART } from "../charts/EChart";
import { fmtNum, fmtPct, fmtSigned, titleFromId } from "../lib/format";
import type { ProfileSeason } from "../types/api";

function Metric({ label, value, interval, n, pctile, hint }: {
  label: string; value: string; interval?: string; n?: string; pctile?: number | null; hint?: string;
}) {
  return (
    <div className="rounded-md border border-line p-3">
      <div className="text-xs text-ink-muted">{label}</div>
      <div className="mt-1 text-lg font-semibold tabular">{value}</div>
      {interval && <div className="text-xs text-ink-2 tabular">{interval}</div>}
      <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-ink-muted">
        {n && <span>{n}</span>}
        {pctile !== undefined && pctile !== null && (
          <span className="flex items-center gap-1" title="Share of the season's reference group with a worse value">
            <span className="inline-block h-1.5 w-16 overflow-hidden rounded bg-surface-3">
              <span className="block h-full rounded bg-accent" style={{ width: `${Math.max(2, pctile)}%` }} />
            </span>
            {fmtNum(pctile, 0)}th pct
          </span>
        )}
      </div>
      {hint && <div className="mt-1 text-[11px] text-ink-muted">{hint}</div>}
    </div>
  );
}

const ci = (lo?: number | null, hi?: number | null) =>
  lo === null || lo === undefined || hi === null || hi === undefined || Number.isNaN(lo) ? undefined : `90% CI ${fmtSigned(lo, 2)} … ${fmtSigned(hi, 2)}`;

export function DriverProfileCard({ driverId }: { driverId: string }) {
  const q = useDriverProfile(driverId);
  const teamName = useConstructorName();
  const [season, setSeason] = useState<number | undefined>();
  useEffect(() => {
    if (q.data && (!season || !q.data.seasons.some((s) => s.season === season))) setSeason(q.data.seasons.at(-1)?.season);
  }, [q.data, season]);

  if (q.isLoading) return <LoadingState label="Loading performance fingerprint…" />;
  if (q.error) {
    if (q.error instanceof ApiError && q.error.status === 404)
      return <Card title="Performance fingerprint"><p className="text-sm text-ink-muted">{q.error.message}</p></Card>;
    return <ErrorState error={q.error} />;
  }
  const p = q.data!;
  const s: ProfileSeason | undefined = p.seasons.find((x) => x.season === season);
  if (!s) return null;
  const outcomes = Object.entries(s).filter(([k, v]) => k.startsWith("outcome_") && typeof v === "number" && v > 0 && k !== "outcome_finished");

  return (
    <Card title="Performance fingerprint"
      subtitle={`Context-adjusted estimates for ${s.season} (${teamName(s.main_team)}). Negative = faster. Percentiles: ${s.rank_reference}.`}
      actions={<Select ariaLabel="Profile season" value={season ?? ""} onChange={(v) => setSeason(v)}
        options={p.seasons.map((x) => ({ value: x.season, label: String(x.season) }))} />}>
      <div className="grid gap-3 md:grid-cols-3">
        <Metric label="Team-adjusted race pace" value={fmtPct(s.race_pace_adj)} interval={ci(s.race_pace_adj_lo, s.race_pace_adj_hi)}
          n={`${s.n_dry_races} dry races · ${s.n_laps} laps`} pctile={s.race_pace_adj_pctile}
          hint={`Team-season effect ${fmtPct(s.team_effect)} (car proxy)`} />
        <Metric label="Team-adjusted qualifying" value={fmtPct(s.quali_adj)}
          interval={s.quali_adj_sd ? `± ${fmtNum(1.645 * s.quali_adj_sd, 2)} (90%)` : undefined}
          n={`${s.n_quali} dry qualifying sessions`} pctile={s.quali_adj_pctile}
          hint={`Median gap to pole ${fmtNum(s.quali_gap_median, 2)}%`} />
        <Metric label="Consistency (lap-to-lap robust SD)" value={`${fmtNum(s.consistency_sd, 3)}%`}
          interval={s.consistency_lo ? `90% CI ${fmtNum(s.consistency_lo, 3)} … ${fmtNum(s.consistency_hi, 3)}` : undefined}
          pctile={s.consistency_pctile} n="lower = more consistent" hint="Influenced by car, traffic and strategy as well." />
        <Metric label="Race gap to team-mate (median)" value={fmtPct(s.teammate_gap_race)}
          interval={ci(s.teammate_gap_race_lo, s.teammate_gap_race_hi)} n={`${s.n_teammate_races} shared races`} hint="Same car: the most direct comparison." />
        <Metric label="Qualifying gap to team-mate" value={fmtPct(s.quali_teammate_gap)}
          interval={ci(s.quali_teammate_gap_lo, s.quali_teammate_gap_hi)} n={`${s.n_quali_teammate} sessions`} />
        <Metric label="Racecraft" value={`${fmtSigned(s.lap1_gain_mean, 2)} on lap 1`}
          n={`${s.n_lap1 ?? 0} starts · ${fmtSigned(s.positions_gained_mean, 2)} grid→finish (${s.n_classified ?? 0} classified)`}
          hint="Position changes reflect car, strategy and incidents too." />
      </div>

      {p.seasons.length > 1 && (
        <div className="mt-4">
          <div className="mb-1 text-xs text-ink-muted">Team-adjusted race pace by season (90% intervals)</div>
          <IntervalChart title="Team-adjusted race pace by season"
            rows={p.seasons.map((x) => ({ label: `${x.season} · ${teamName(x.main_team)}`, point: x.race_pace_adj, lo: x.race_pace_adj_lo, hi: x.race_pace_adj_hi, color: CHART.series[0] }))} />
        </div>
      )}

      <div className="mt-4">
        <div className="mb-2 text-xs text-ink-muted">Condition-specific deviations ({p.meta.seasons?.[0]}–{p.meta.seasons?.at(-1)}, shrunk towards zero)</div>
        <div className="grid gap-2 md:grid-cols-3">
          {p.conditions.map((c) => <ConditionRow key={c.dimension} c={c} />)}
          {p.conditions.length === 0 && <p className="text-sm text-ink-muted">No condition-specific evidence.</p>}
        </div>
      </div>

      {outcomes.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-ink-muted">Non-finishes {s.season} (reported separately from pace):</span>
          {outcomes.map(([k, v]) => <StatusPill key={k} status="info">{titleFromId(k.replace("outcome_", "").replace(/_/g, "-"))}: {String(v)}</StatusPill>)}
        </div>
      )}
      <p className="mt-4 text-[11px] leading-relaxed text-ink-muted">{p.meta.identification_note} Model: {p.meta.race_model?.formula}.</p>
    </Card>
  );
}
