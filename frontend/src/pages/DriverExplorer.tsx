import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useConstructors, useDriverPerformance, useDrivers, useSeasons } from "../api/hooks";
import { Badge, Card, EmptyState, ErrorState, KV, LoadingState, PageHeader, Select, StatTile, inputClass } from "../components/ui";
import { PaceTimeline } from "../charts/PaceTimeline";
import { fmtNum, fmtPct, titleFromId } from "../lib/format";

export default function DriverExplorerPage() {
  const [params, setParams] = useSearchParams();
  const seasons = useSeasons();
  const [season, setSeason] = useState<number | undefined>(params.get("season") ? Number(params.get("season")) : undefined);
  const [team, setTeam] = useState<string>("");
  const [q, setQ] = useState("");
  const [scope, setScope] = useState<"lap" | "all">("lap");
  const selected = params.get("driver") ?? undefined;
  const drivers = useDrivers({ season, constructor_id: team || undefined, q: q || undefined, scope });
  const teams = useConstructors(season);
  const perf = useDriverPerformance(selected);

  useEffect(() => {
    if (!season && seasons.data) {
      const lap = seasons.data.find((s) => s.has_lap_data);
      if (lap) setSeason(lap.season);
    }
  }, [season, seasons.data]);

  const seasonOptions = useMemo(() => [{ value: 0, label: "All seasons" },
    ...(seasons.data ?? []).filter((s) => scope === "all" || s.has_lap_data).map((s) => ({ value: s.season, label: String(s.season) }))],
  [seasons.data, scope]);

  const choose = (id: string) => setParams((p) => { p.set("driver", id); return p; });

  return (
    <div className="space-y-5">
      <PageHeader title="Driver explorer"
        description="Browse drivers, then inspect their context-adjusted performance fingerprint, results and race pace. Historical drivers outside the lap-timing seasons have results-only profiles." />
      <div className="flex flex-wrap items-end gap-3">
        <Select ariaLabel="Scope" value={scope} onChange={(v) => setScope(v)} options={[
          { value: "lap", label: "Lap-timing era (2022–2025)" }, { value: "all", label: "All history (results only before 2022)" }]} />
        <Select ariaLabel="Season" value={season ?? 0} onChange={(v) => setSeason(v === 0 ? undefined : v)} options={seasonOptions} />
        <Select ariaLabel="Team" value={team} onChange={(v) => setTeam(v)} options={[{ value: "", label: "All teams" },
          ...(teams.data ?? []).map((t) => ({ value: t.constructor_id, label: t.name }))]} />
        <input aria-label="Search drivers" placeholder="Search name or code" value={q} onChange={(e) => setQ(e.target.value)} className={inputClass} />
      </div>

      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <Card title={`Drivers${drivers.data ? ` (${drivers.data.total})` : ""}`} className="max-h-[75vh] overflow-y-auto">
          {drivers.isLoading && <LoadingState />}
          {drivers.error && <ErrorState error={drivers.error} />}
          {drivers.data && drivers.data.items.length === 0 && <EmptyState>No drivers match these filters.</EmptyState>}
          <ul className="space-y-0.5">
            {drivers.data?.items.map((d) => (
              <li key={d.driver_id}>
                <button onClick={() => choose(d.driver_id)}
                  className={`flex w-full items-center justify-between rounded px-2 py-1.5 text-left text-sm ${selected === d.driver_id ? "bg-surface-3" : "hover:bg-surface-2"}`}>
                  <span>{d.name}</span>
                  <span className="text-xs text-ink-muted">{d.abbreviation ?? ""} {d.has_lap_data ? "" : "· results"}</span>
                </button>
              </li>
            ))}
          </ul>
        </Card>

        <div className="space-y-4">
          {!selected && <EmptyState>Select a driver to see their profile.</EmptyState>}
          {selected && perf.isLoading && <LoadingState />}
          {selected && perf.error && <ErrorState error={perf.error} />}
          {perf.data && (
            <>
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-lg font-semibold">{perf.data.driver.name}</h2>
                {perf.data.driver.has_lap_data ? <Badge>lap-timing profile</Badge> : <Badge>results-only profile</Badge>}
                <span className="text-sm text-ink-muted">{perf.data.driver.first_season}–{perf.data.driver.last_season}</span>
                <Link className="ml-auto text-sm text-accent" to={`/compare?a=${selected}`}>Compare →</Link>
                <Link className="text-sm text-accent" to={`/explain?driver=${selected}`}>Explain a prediction →</Link>
              </div>
              <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
                <StatTile label="Starts" value={perf.data.results_summary.starts} />
                <StatTile label="Wins" value={perf.data.results_summary.wins} />
                <StatTile label="Podiums" value={perf.data.results_summary.podiums} />
                <StatTile label="Poles" value={perf.data.results_summary.poles} />
                <StatTile label="Avg positions gained" value={fmtNum(perf.data.results_summary.mean_positions_gained, 2)}
                  hint={`grid → finish, ${perf.data.results_summary.positions_gained_n} classified races`} />
              </div>
              {perf.data.driver.has_lap_data && (
                <Card title="Race pace by event" subtitle="Median representative lap vs the session reference, and gap to the team-mate in the same session. Negative = faster; the axis is inverted so up means faster.">
                  <PaceTimeline events={perf.data.events} title={`${perf.data.driver.name} race pace by event`} />
                </Card>
              )}
              <Card title="Race outcomes" subtitle={perf.data.results_summary.note}>
                <KV rows={Object.entries(perf.data.results_summary.outcomes).map(([k, v]) => [titleFromId(k.replace(/_/g, "-")), v])} />
              </Card>
              <Card title="Results" subtitle="Drill down into a race for laps, stints and telemetry">
                <div className="max-h-96 overflow-y-auto">
                  <table className="w-full text-left text-sm tabular">
                    <thead className="sticky top-0 bg-surface-1 text-xs text-ink-muted">
                      <tr><th className="py-1">Event</th><th>Team</th><th>Quali</th><th>Grid</th><th>Finish</th><th>Pace</th><th>vs TM</th><th>Outcome</th></tr>
                    </thead>
                    <tbody>
                      {perf.data.events.slice().reverse().map((e) => (
                        <tr key={e.event_id} className="border-t border-line">
                          <td className="py-1"><Link className="hover:text-accent" to={`/races?event=${e.event_id}&driver=${selected}`}>{e.event_id} {titleFromId(e.grand_prix_id)}</Link></td>
                          <td className="text-ink-2">{titleFromId(e.constructor_id)}</td>
                          <td>{e.quali_position ?? "—"}</td>
                          <td>{e.grid_position ?? "—"}</td>
                          <td>{e.position ?? e.position_text ?? "—"}</td>
                          <td>{e.med_rel_pace !== undefined ? fmtPct(e.med_rel_pace) : "—"}</td>
                          <td>{e.teammate_gap !== undefined ? fmtPct(e.teammate_gap) : "—"}</td>
                          <td className="text-xs text-ink-muted">{e.reason_retired ?? (e.outcome_category === "finished" ? "" : e.outcome_category)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
