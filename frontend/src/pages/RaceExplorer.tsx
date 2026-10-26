import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useEvents, useJson, useSessionLaps, useSessions } from "../api/hooks";
import { Badge, Card, EmptyState, ErrorState, Field, LoadingState, PageHeader, Select, StatusPill } from "../components/ui";
import { LapTimeChart } from "../charts/LapTimeChart";
import { StintChart, type StintRow } from "../charts/StintChart";
import { WeatherChart, type WeatherRow } from "../charts/WeatherChart";
import { fmtLapTime, fmtNum, titleFromId } from "../lib/format";

const SESSION_LABEL: Record<string, string> = { FP1: "Practice 1", FP2: "Practice 2", FP3: "Practice 3", Q: "Qualifying", SQ: "Sprint qualifying", S: "Sprint", R: "Race" };

export default function RaceExplorerPage() {
  const [params, setParams] = useSearchParams();
  const eventId = params.get("event") ?? "";
  const season = eventId ? Number(eventId.slice(0, 4)) : 2025;
  const events = useEvents(season);
  const sessions = useSessions(eventId || undefined);
  const [sessionId, setSessionId] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [lapDriver, setLapDriver] = useState(params.get("driver") ?? "");

  useEffect(() => {
    const withLaps = (sessions.data ?? []).filter((s) => s.n_laps);
    if (withLaps.length && !withLaps.some((s) => s.session_id === sessionId)) {
      const race = withLaps.find((s) => s.session_code === "R") ?? withLaps.at(-1)!;
      setSessionId(race.session_id);
    }
  }, [sessions.data, sessionId]);

  const laps = useSessionLaps(sessionId || undefined);
  const stints = useJson<StintRow[]>(["stints", sessionId], sessionId ? `/sessions/${sessionId}/stints` : null);
  const weather = useJson<WeatherRow[]>(["weather", sessionId], sessionId ? `/sessions/${sessionId}/weather` : null);
  const results = useJson<Record<string, unknown>[]>(["results", sessionId], sessionId ? `/sessions/${sessionId}/results` : null);
  const rcm = useJson<{ time_utc: string; lap: number | null; category: string; message: string; flag: string | null }[]>(
    ["rcm", sessionId], sessionId ? `/sessions/${sessionId}/race-control` : null);
  const session = sessions.data?.find((s) => s.session_id === sessionId);
  const circuitId = events.data?.find((e) => e.event_id === eventId)?.circuit_id;

  const order = useMemo(() => {
    const r = (results.data ?? []).map((x) => x.driver_id as string);
    const fromLaps = Array.from(new Set((laps.data?.laps ?? []).map((l) => l.driver_id)));
    return [...r.filter((d) => fromLaps.includes(d)), ...fromLaps.filter((d) => !r.includes(d))];
  }, [results.data, laps.data]);
  useEffect(() => {
    if (order.length && picked.length === 0) setPicked(order.slice(0, 2));
    if (order.length && (!lapDriver || !order.includes(lapDriver))) setLapDriver(order[0]);
  }, [order, picked.length, lapDriver]);

  const excl = useMemo(() => {
    const m = new Map<string, number>();
    (laps.data?.laps ?? []).forEach((l) => { if (!l.is_clean) m.set(l.exclusion_reason ?? "other", (m.get(l.exclusion_reason ?? "other") ?? 0) + 1); });
    return Array.from(m.entries()).sort((a, b) => b[1] - a[1]);
  }, [laps.data]);

  return (
    <div className="space-y-5">
      <PageHeader title="Race & lap explorer"
        description="Results, lap timing, sectors, stints, weather and race control for any ingested session. Excluded laps are kept and labelled, never deleted." />
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Season"><Select ariaLabel="Season" value={season} onChange={(v) => setParams({ event: `${v}-01` })}
          options={[2022, 2023, 2024, 2025].map((s) => ({ value: s, label: String(s) }))} /></Field>
        <Field label="Event"><Select ariaLabel="Event" value={eventId} onChange={(v) => { setParams({ event: v }); setSessionId(""); setPicked([]); }}
          options={[{ value: "", label: "Select event" }, ...(events.data ?? []).filter((e) => (e.lap_sessions ?? 0) > 0).map((e) => ({ value: e.event_id, label: `${e.round}. ${e.circuit_name ?? e.circuit_id}` }))]} /></Field>
        <Field label="Session"><Select ariaLabel="Session" value={sessionId} onChange={(v) => { setSessionId(v); setPicked([]); }}
          options={(sessions.data ?? []).filter((s) => s.n_laps).map((s) => ({ value: s.session_id, label: SESSION_LABEL[s.session_code] ?? s.session_code }))} /></Field>
      </div>
      {!eventId && <EmptyState>Select an event.</EmptyState>}
      {session && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <StatusPill status={session.quality_status === "ok" ? "good" : session.quality_status === "warning" ? "warning" : "critical"}>
            data quality: {session.quality_status ?? "unknown"}</StatusPill>
          {(session.warnings ?? []).map((w) => <Badge key={w}>{w.replace(/_/g, " ")}</Badge>)}
          <span className="text-ink-muted">{session.n_laps} laps · {session.n_clean_laps} clean · {session.telemetry_laps} telemetry laps</span>
          {session.telemetry_laps > 0 && circuitId && session.session_code === "Q" &&
            <Link className="text-accent" to={`/tracks?circuit=${circuitId}&session=${session.session_id}`}>Telemetry in the track explorer →</Link>}
        </div>
      )}
      {laps.isLoading && <LoadingState />}
      {laps.error && <ErrorState error={laps.error} />}
      {laps.data && (
        <>
          <Card title="Lap times" subtitle="Filled markers: clean laps. Hollow: excluded (pit, safety car, flags, deleted, inaccurate…), with the reason in the tooltip."
            actions={<div className="flex flex-wrap gap-1">{order.slice(0, 22).map((d) => (
              <button key={d} onClick={() => setPicked((p) => p.includes(d) ? p.filter((x) => x !== d) : p.length >= 4 ? [...p.slice(1), d] : [...p, d])}
                className={`rounded border px-1.5 py-0.5 text-[11px] ${picked.includes(d) ? "border-accent text-ink" : "border-line text-ink-muted"}`}>
                {laps.data!.laps.find((l) => l.driver_id === d)?.driver_abbr ?? d}</button>))}</div>}>
            <LapTimeChart laps={laps.data.laps} drivers={picked} />
            <div className="mt-2 flex flex-wrap gap-2 text-[11px] text-ink-muted">Exclusion reasons: {excl.map(([k, v]) => <Badge key={k}>{k.replace(/_/g, " ")}: {v}</Badge>)}</div>
          </Card>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Tyre stints">
              {stints.data && stints.data.length > 0 ? <StintChart stints={stints.data} order={order} /> : <EmptyState>No stint data.</EmptyState>}
            </Card>
            <Card title="Weather" subtitle="Trackside sensor; rain periods shaded">
              {weather.data && weather.data.length > 0 ? <WeatherChart rows={weather.data} /> : <EmptyState>No weather series for this session.</EmptyState>}
            </Card>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Classification" subtitle="F1DB">
              <div className="max-h-80 overflow-y-auto">
                <table className="w-full whitespace-nowrap text-left text-xs tabular">
                  <thead className="sticky top-0 bg-surface-1 text-ink-muted"><tr><th className="py-1">Pos</th><th>Driver</th><th>Team</th><th>Time / best</th><th>Notes</th></tr></thead>
                  <tbody>{(results.data ?? []).map((r, i) => (
                    <tr key={i} className="border-t border-line">
                      <td className="py-1">{String(r.position ?? r.position_text ?? "—")}</td>
                      <td><Link className="hover:text-accent" to={`/drivers?driver=${r.driver_id}`}>{titleFromId(r.driver_id as string)}</Link></td>
                      <td className="text-ink-2">{titleFromId(r.constructor_id as string)}</td>
                      <td>{r.best_s ? fmtLapTime(r.best_s as number) : r.time_s ? fmtLapTime(r.time_s as number) : r.gap_s ? `+${fmtNum(r.gap_s as number, 3)}` : "—"}</td>
                      <td className="text-ink-muted">{(r.reason_retired as string) ?? ""}</td>
                    </tr>))}</tbody>
                </table>
              </div>
            </Card>
            <Card title="Race control">
              <div className="max-h-80 overflow-y-auto">
                {(rcm.data ?? []).length === 0 && <EmptyState>No messages.</EmptyState>}
                <ul className="space-y-1 text-xs">{(rcm.data ?? []).map((m, i) => (
                  <li key={i} className="flex gap-2"><span className="w-10 shrink-0 text-ink-muted">{m.lap ? `L${m.lap}` : ""}</span>
                    <span className={m.category === "Flag" || m.category === "SafetyCar" ? "text-ink" : "text-ink-2"}>{m.message}</span></li>))}</ul>
              </div>
            </Card>
          </div>
          <Card title="Laps of one driver" actions={<Select ariaLabel="Lap table driver" value={lapDriver} onChange={setLapDriver}
            options={order.map((d) => ({ value: d, label: titleFromId(d) }))} />}>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full whitespace-nowrap text-left text-xs tabular">
                <thead className="sticky top-0 bg-surface-1 text-ink-muted">
                  <tr><th className="py-1">Lap</th><th>Time</th><th>S1</th><th>S2</th><th>S3</th><th>Tyre</th><th>Age</th><th>Pos</th><th>Status</th><th>Track °C</th><th>Speed trap</th></tr></thead>
                <tbody>{laps.data.laps.filter((l) => l.driver_id === lapDriver).map((l) => (
                  <tr key={l.lap_number} className={`border-t border-line ${l.is_clean ? "" : "text-ink-muted"}`}>
                    <td className="py-1">{l.lap_number}</td><td>{fmtLapTime(l.lap_time_s)}</td><td>{fmtNum(l.sector1_s, 3)}</td><td>{fmtNum(l.sector2_s, 3)}</td>
                    <td>{fmtNum(l.sector3_s, 3)}</td><td>{l.compound}</td><td>{l.tyre_life_laps ?? "—"}</td><td>{l.position ?? "—"}</td>
                    <td>{l.is_clean ? "clean" : (l.exclusion_reason ?? "").replace(/_/g, " ")}</td><td>{fmtNum(l.track_temp_c, 1)}</td><td>{l.speed_st_kph ?? "—"}</td>
                  </tr>))}</tbody>
              </table>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
