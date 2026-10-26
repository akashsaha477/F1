import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useCircuits, useJson } from "../api/hooks";
import { qs } from "../api/client";
import { Badge, Card, EmptyState, ErrorState, Field, KV, LoadingState, PageHeader, Select, StatusPill } from "../components/ui";
import { TrackMap, type CornerDelta } from "../charts/TrackMap";
import { TraceChart } from "../charts/TraceChart";
import { CHART } from "../charts/EChart";
import { fmtNum, fmtSec, fmtSigned, titleFromId } from "../lib/format";
import type { TelemetryResponse, TrackLayout, TrackPerformance } from "../types/api";

const CAT_LABEL: Record<string, string> = { slow: "Slow", medium: "Medium", fast: "Fast", flat_out: "Flat-out kink" };

export default function TrackExplorerPage() {
  const [params, setParams] = useSearchParams();
  const circuits = useCircuits();
  const circuit = params.get("circuit") ?? "silverstone";
  const session = params.get("session") ?? undefined;
  const [corner, setCorner] = useState<string | undefined>();
  const [a, setA] = useState("");
  const [b, setB] = useState("");
  const layout = useJson<TrackLayout>(["layout", circuit, session], `/circuits/${circuit}/layout${qs({ session_id: session })}`);
  const sid = layout.data?.session_id;
  const perf = useJson<TrackPerformance>(["track-perf", circuit, sid], sid ? `/circuits/${circuit}/performance${qs({ session_id: sid })}` : null);
  const cornerPerf = useJson<TrackPerformance>(["track-perf", circuit, sid, corner],
    sid && corner ? `/circuits/${circuit}/performance${qs({ session_id: sid, corner_id: corner })}` : null);
  const telA = useJson<TelemetryResponse>(["tel", sid, a], sid && a ? `/sessions/${sid}/telemetry${qs({ driver_id: a })}` : null);
  const telB = useJson<TelemetryResponse>(["tel", sid, b], sid && b ? `/sessions/${sid}/telemetry${qs({ driver_id: b })}` : null);

  useEffect(() => setCorner(undefined), [circuit, sid]);
  const drivers = useMemo(() => Array.from(new Set((perf.data?.metrics ?? []).map((m) => m.driver_id))).sort(), [perf.data]);
  useEffect(() => {
    if (drivers.length && (!a || !drivers.includes(a))) setA(layout.data?.reference.driver_id ?? drivers[0]);
  }, [drivers, a, layout.data]);

  const deltas: CornerDelta[] | undefined = useMemo(() => {
    if (!perf.data || !a || !b) return undefined;
    const by = (d: string) => new Map(perf.data!.metrics.filter((m) => m.driver_id === d && m.quality === "ok").map((m) => [m.corner_id, m.segment_time_s]));
    const ma = by(a), mb = by(b);
    return Array.from(ma.entries()).filter(([k]) => mb.has(k)).map(([k, v]) => ({ corner_id: k, delta: v - (mb.get(k) as number) }));
  }, [perf.data, a, b]);

  const sel = layout.data?.corners.find((c) => c.corner_id === corner);
  const trace = (t: TelemetryResponse | undefined, key: "speed_kph" | "throttle_pct", name: string, color: string) =>
    t?.samples ? [{ name, color, points: t.samples.map((s) => ({ d: s.distance_m, v: s[key] })) }] : [];
  const val = layout.data?.marker_validation;

  return (
    <div className="space-y-5">
      <PageHeader title="Track explorer"
        description="Circuit geometry, corner segmentation and corner-by-corner driver comparisons from the fastest qualifying laps." />
      <div className="flex flex-wrap items-end gap-3">
        <Field label="Circuit">
          <Select ariaLabel="Circuit" value={circuit} onChange={(v) => setParams({ circuit: v })}
            options={(circuits.data ?? []).filter((c) => c.has_lap_data).map((c) => ({ value: c.circuit_id, label: c.name }))} />
        </Field>
        <Field label="Qualifying session">
          <Select ariaLabel="Qualifying session" value={sid ?? ""} onChange={(v) => setParams({ circuit, session: v })}
            options={(layout.data?.available_sessions ?? []).map((s) => ({ value: s.session_id, label: `${s.season} (${s.session_id})` }))} />
        </Field>
        <Field label="Driver A">
          <Select ariaLabel="Driver A" value={a} onChange={setA} options={[{ value: "", label: "—" }, ...drivers.map((d) => ({ value: d, label: titleFromId(d) }))]} />
        </Field>
        <Field label="Driver B (comparison)">
          <Select ariaLabel="Driver B" value={b} onChange={setB} options={[{ value: "", label: "None" }, ...drivers.map((d) => ({ value: d, label: titleFromId(d) }))]} />
        </Field>
      </div>
      {layout.isLoading && <LoadingState />}
      {layout.error && <ErrorState error={layout.error} />}
      {layout.data && (
        <>
          <div className="grid gap-4 lg:grid-cols-[3fr_2fr]">
            <Card title={`${titleFromId(layout.data.circuit_id)} · ${layout.data.season}`}
              subtitle={`Reference: ${titleFromId(layout.data.reference.driver_id)}'s ${fmtNum(layout.data.reference.lap_time_s, 3)} s lap. Click a corner for details.`}>
              <TrackMap layout={layout.data} selected={corner} onSelect={setCorner} deltas={b ? deltas : undefined}
                aName={titleFromId(a)} bName={titleFromId(b)} />
            </Card>
            <Card title="Segmentation and data quality">
              <div className="mb-2 flex flex-wrap gap-2">
                <StatusPill status={val?.status === "markers_used" ? "good" : "warning"}>
                  {val?.status === "markers_used" ? "FastF1 corner markers" : val?.status === "markers_rejected_off_path" ? "markers rejected (off path) — inferred segments" : "inferred segments"}
                </StatusPill>
              </div>
              <KV rows={[
                ["Corners / complexes", layout.data.corners.length],
                ["Curvature-inferred corners", layout.data.inferred_segments.length],
                ["Markers matched by curvature (recall)", val?.recall !== undefined && val?.recall !== null ? `${fmtNum(Number(val.recall) * 100, 0)}%` : "—"],
                ["Inferred corners at a marker (precision)", val?.precision !== undefined && val?.precision !== null ? `${fmtNum(Number(val.precision) * 100, 0)}%` : "—"],
                ["Median apex distance error", val?.median_apex_error_m !== undefined && val?.median_apex_error_m !== null ? `${fmtNum(Number(val.median_apex_error_m), 0)} m` : "—"],
                ["Median marker offset from path", val?.median_marker_offset_m !== null && val?.median_marker_offset_m !== undefined ? `${fmtNum(Number(val.median_marker_offset_m), 1)} m` : "—"],
                ["Reference path length", `${fmtNum(layout.data.length_m, 0)} m`],
              ]} />
              <ul className="mt-3 list-disc space-y-1 pl-4 text-xs text-ink-muted">{layout.data.notes.map((n) => <li key={n}>{n}</li>)}</ul>
              <div className="mt-3 text-xs text-ink-muted">Category rules (km/h, minimum speed on the reference lap): slow &lt; {layout.data.category_rules.slow_max_kph}, fast ≥ {layout.data.category_rules.fast_min_kph}; flat-out when throttle stays ≥ {layout.data.category_rules.flat_out_min_throttle}%.</div>
              {layout.data.sectors.length > 0 && (
                <table className="mt-3 w-full text-left text-xs tabular">
                  <thead className="text-ink-muted"><tr><th>Sector</th><th>Length</th><th>Slow</th><th>Medium</th><th>Fast</th><th>Full throttle</th></tr></thead>
                  <tbody>{layout.data.sectors.map((s) => (
                    <tr key={s.sector} className="border-t border-line"><td className="py-1">{s.sector}</td><td>{fmtNum(s.length_m, 0)} m</td>
                      <td>{fmtNum(s.frac_slow * 100, 0)}%</td><td>{fmtNum(s.frac_medium * 100, 0)}%</td><td>{fmtNum(s.frac_fast * 100, 0)}%</td><td>{fmtNum(s.full_throttle_frac * 100, 0)}%</td></tr>
                  ))}</tbody>
                </table>
              )}
            </Card>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Corners" subtitle="Windows run from the speed peak before to the speed peak after the minimum-speed point">
              <div className="max-h-96 overflow-y-auto">
                <table className="w-full text-left text-sm tabular">
                  <thead className="sticky top-0 bg-surface-1 text-xs text-ink-muted">
                    <tr><th className="py-1">Corner</th><th>Category</th><th>Min speed</th><th>Turn</th><th>Sector</th><th>Notes</th></tr>
                  </thead>
                  <tbody>
                    {layout.data.corners.map((c) => (
                      <tr key={c.corner_id} onClick={() => setCorner(c.corner_id)}
                        className={`cursor-pointer border-t border-line ${corner === c.corner_id ? "bg-surface-3" : "hover:bg-surface-2"}`}>
                        <td className="py-1">{c.corner_id}</td><td>{CAT_LABEL[c.category]}</td><td>{fmtNum(c.min_speed_ref, 0)} km/h</td>
                        <td>{fmtNum(Math.abs(c.heading_change_deg), 0)}° {c.direction}</td><td>{c.sector ?? "—"}</td>
                        <td className="space-x-1">{c.is_hairpin && <Badge>hairpin</Badge>}{c.is_chicane && <Badge>chicane</Badge>}{c.is_esses && <Badge>esses</Badge>}{c.is_sweeper && <Badge>sweeper</Badge>}{c.is_sequence && <Badge>sequence</Badge>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
            <Card title={sel ? `${sel.corner_id}: drivers in this session` : "Corner detail"}
              subtitle={sel ? `${CAT_LABEL[sel.category]} · entry ${fmtNum(sel.entry_speed_ref, 0)} → min ${fmtNum(sel.min_speed_ref, 0)} → exit ${fmtNum(sel.exit_speed_ref, 0)} km/h (reference lap)` : undefined}>
              {!corner && <EmptyState>Select a corner on the map or in the table.</EmptyState>}
              {corner && cornerPerf.isLoading && <LoadingState />}
              {cornerPerf.data && (
                <>
                  <div className="max-h-72 overflow-y-auto">
                    <table className="w-full whitespace-nowrap text-left text-xs tabular">
                      <thead className="sticky top-0 bg-surface-1 text-ink-muted">
                        <tr><th className="py-1">Driver</th><th>Time (s)</th><th>Δ best</th><th>Δ team-mate</th><th>Min km/h</th><th>Brake (m before apex)</th><th>To full throttle (s)</th></tr>
                      </thead>
                      <tbody>
                        {cornerPerf.data.metrics.slice().sort((x, y) => x.segment_time_s - y.segment_time_s).map((m) => (
                          <tr key={m.driver_id} className={`border-t border-line ${m.quality !== "ok" ? "text-ink-muted" : ""}`}>
                            <td className="py-1">{titleFromId(m.driver_id)} {m.quality !== "ok" && <span title="Low sample density or implausible segment">*</span>}</td>
                            <td>{fmtNum(m.segment_time_s, 3)}</td><td>{fmtSigned(m.delta_to_best_s, 3)}</td>
                            <td>{m.delta_to_teammate_s !== null ? fmtSigned(m.delta_to_teammate_s, 3) : <span className="text-ink-muted">n/a</span>}</td>
                            <td>{fmtNum(m.min_speed_kph, 0)}</td><td>{m.brake_onset_before_apex_m !== null ? fmtNum(m.brake_onset_before_apex_m, 0) : "no brake"}</td>
                            <td>{m.full_throttle_delay_s !== null ? fmtNum(m.full_throttle_delay_s, 2) : "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-1 text-[11px] text-ink-muted">* low sample density or implausible segment time (excluded from comparisons).</p>
                  <div className="mt-3 text-xs text-ink-muted">Across all analysed sessions at this circuit — mean segment-time gap to the team-mate in {corner} (comparable runs only):</div>
                  <ul className="mt-1 grid grid-cols-2 gap-x-4 text-xs tabular">
                    {cornerPerf.data.teammate_relative_history.slice(0, 10).map((h) => (
                      <li key={h.driver_id} className="flex justify-between"><span className="text-ink-2">{titleFromId(h.driver_id)}</span>
                        <span>{fmtSec(h.mean_delta_to_teammate_s, 3)} <span className="text-ink-muted">({h.n_sessions})</span></span></li>
                    ))}
                  </ul>
                  <p className="mt-2 text-[11px] text-ink-muted">Measured: {cornerPerf.data.measured_vs_derived.measured.join(", ")}. Derived: {cornerPerf.data.measured_vs_derived.derived.join("; ")}.</p>
                </>
              )}
            </Card>
          </div>

          <Card title="Speed and throttle traces" subtitle={`Fastest qualifying lap of each selected driver${sel ? `; shaded: ${sel.corner_id} window` : ""}. Distance is FastF1's integrated distance.`}>
            {!a && <EmptyState>Select driver A.</EmptyState>}
            {(telA.isLoading || telB.isLoading) && <LoadingState />}
            {telA.data && (
              <>
                <TraceChart title="Speed traces" unit="km/h" window={sel ? [sel.entry_s, sel.exit_s] : undefined}
                  traces={[...trace(telA.data, "speed_kph", titleFromId(a), CHART.series[0]), ...trace(telB.data, "speed_kph", titleFromId(b), CHART.series[1])]} />
                <TraceChart title="Throttle traces" unit="%" height={160} window={sel ? [sel.entry_s, sel.exit_s] : undefined}
                  traces={[...trace(telA.data, "throttle_pct", titleFromId(a), CHART.series[0]), ...trace(telB.data, "throttle_pct", titleFromId(b), CHART.series[1])]} />
                <p className="text-[11px] text-ink-muted">Unavailable channels: {telA.data.channels?.unavailable.join(", ")}. Brake is on/off only.
                  {" "}<Link className="text-accent" to={`/races?event=${sid?.slice(0, 7)}`}>Open the session in the race &amp; lap explorer →</Link></p>
              </>
            )}
          </Card>
        </>
      )}
    </div>
  );
}
