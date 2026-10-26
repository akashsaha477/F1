import { Link } from "react-router-dom";
import { useModels, useOverview } from "../api/hooks";
import { Card, ErrorState, LoadingState, PageHeader, StatTile, StatusPill } from "../components/ui";
import { compact, fmtNum, titleFromId } from "../lib/format";
import { DriverEffectsCard } from "../components/DriverEffectsCard";

export default function OverviewPage() {
  const ov = useOverview();
  const models = useModels();
  if (ov.isLoading) return <LoadingState />;
  if (ov.error) return <ErrorState error={ov.error} onRetry={() => ov.refetch()} />;
  const o = ov.data!;
  const s = o.summary as Record<string, number>;
  const prod = models.data?.models.filter((m) => m.is_production) ?? [];

  return (
    <div className="space-y-6">
      <PageHeader title="Overview"
        description="Where drivers gain or lose time, under which conditions, how much is attributable to the driver rather than the car, and how strong the evidence is. Every number below is computed from the stored data." />

      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatTile label="Lap-timing seasons" value={o.seasons_with_lap_data.length ? `${o.seasons_with_lap_data[0]}–${o.seasons_with_lap_data.at(-1)}` : "—"} hint="FastF1 export" />
        <StatTile label="Laps ingested" value={compact(s.laps)} hint={`${compact(s.clean_laps)} clean`} />
        <StatTile label="Sessions with timing" value={compact(s.sessions_with_timing)} />
        <StatTile label="Telemetry laps" value={compact(s.telemetry_laps)} hint="fastest qualifying laps" />
        <StatTile label="Results history" value={`${o.results_seasons[0]}–${o.results_seasons[1]}`} hint="F1DB" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card title="Model status" subtitle="Production lap-pace models, evaluated on an untouched final season" className="lg:col-span-2">
          {models.isLoading && <LoadingState />}
          {models.error && <ErrorState error={models.error} />}
          {prod.length === 0 && !models.isLoading && <p className="text-sm text-ink-muted">No trained models found.</p>}
          <div className="grid gap-3 md:grid-cols-2">
            {prod.map((m) => (
              <div key={m.model_version} className="rounded-md border border-line p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{m.horizon === "pre_race" ? "Pre-race horizon" : "Pre-event horizon"}</span>
                  <span className="text-xs text-ink-muted">{m.model}</span>
                </div>
                <div className="mt-2 grid grid-cols-3 gap-2 text-sm tabular">
                  <div><div className="text-xs text-ink-muted">Holdout MAE</div>{fmtNum(m.test_metrics.holdout.mae, 3)}%</div>
                  <div><div className="text-xs text-ink-muted">≈ seconds</div>{fmtNum(m.test_metrics.holdout.mae_seconds, 3)} s</div>
                  <div><div className="text-xs text-ink-muted">90% interval coverage</div>{fmtNum(m.test_metrics.holdout.coverage * 100, 1)}%</div>
                </div>
                <div className="mt-2 truncate text-[11px] text-ink-muted" title={m.model_version}>{m.model_version}</div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-ink-muted">
            Target: representative race-lap time relative to the session reference. See <Link className="text-accent" to="/methodology">Data &amp; methodology</Link> for baselines, folds and limitations.
          </p>
        </Card>

        <Card title="What the data supports">
          <ul className="space-y-2">
            {o.analyses.map((a) => (
              <li key={a.analysis} className="text-sm">
                <StatusPill status={a.supported ? (a.limitation ? "warning" : "good") : "critical"}>
                  {a.supported ? (a.limitation ? "limited" : "supported") : "not available"}
                </StatusPill>{" "}
                <span className="text-ink">{a.analysis}</span>
                <div className="text-xs text-ink-muted">{a.evidence}</div>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <DriverEffectsCard />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Recent races" subtitle="Podium and pole from F1DB">
          <ul className="divide-y divide-line">
            {o.recent_races.slice().reverse().map((r) => (
              <li key={r.event_id} className="flex items-center justify-between gap-3 py-2 text-sm">
                <div>
                  <Link to={`/races?event=${r.event_id}`} className="font-medium hover:text-accent">{r.official_name}</Link>
                  <div className="text-xs text-ink-muted">{r.date} · {titleFromId(r.circuit_id)} {r.wet_race && "· wet race"}</div>
                </div>
                <div className="text-right text-xs text-ink-2">
                  {r.podium.map((p) => <div key={p.position}>P{p.position} {titleFromId(p.driver_id)}</div>)}
                </div>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Coverage by season" subtitle="Lap-level sources">
          <table className="w-full text-left text-sm tabular">
            <thead className="text-xs text-ink-muted">
              <tr><th className="py-1">Season</th><th>Sessions</th><th>Clean laps</th><th>Wet clean laps</th><th>Telemetry laps</th></tr>
            </thead>
            <tbody>
              {o.per_season.map((r) => (
                <tr key={String(r.season)} className="border-t border-line">
                  <td className="py-1">{String(r.season)}</td>
                  <td>{String(r.sessions_with_timing)}</td>
                  <td>{compact(r.clean_laps as number)}</td>
                  <td>{compact(r.wet_clean_laps as number)}</td>
                  <td>{String(r.telemetry_laps)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  );
}
