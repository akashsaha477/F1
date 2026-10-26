import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { useCircuits, useDrivers, useJson } from "../api/hooks";
import { postJson, qs } from "../api/client";
import { Button, Card, EmptyState, ErrorState, Field, LoadingState, PageHeader, Select, StatTile, StatusPill } from "../components/ui";
import { ConditionStatus } from "../components/conditions";
import { CHART, EChart, axisStyle } from "../charts/EChart";
import { DegradationChart } from "../charts/DegradationChart";
import { COMPOUND_COLORS, fmtNum, fmtPct, fmtSigned, titleFromId } from "../lib/format";
import type { ConditionDimension, DegradationCurve, TyreDegradation } from "../types/api";

const DRY = ["SOFT", "MEDIUM", "HARD"] as const;

function CompoundSeasonChart({ rows }: { rows: TyreDegradation["by_compound"] }) {
  const seasons = Array.from(new Set(rows.map((r) => r.season))).sort();
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 40, bottom: 24, containLabel: true },
    legend: { top: 0, right: 0, textStyle: { color: CHART.ink2 }, itemWidth: 10, itemHeight: 10 },
    tooltip: { trigger: "item", formatter: (p: unknown) => {
      const d = (p as { data: { r: TyreDegradation["by_compound"][number] } }).data.r;
      return `<b>${fmtPct(d.slope_pct, 3)}</b> per lap (${d.slope_s_per_lap.toFixed(3)} s)<br/>${d.compound} · ${d.season}<br/>` +
        `<span style="color:${CHART.muted}">90%: ${fmtPct(d.ci_lo, 3)} … ${fmtPct(d.ci_hi, 3)} · ${d.n_stints} stints, ${d.n_sessions} races</span>`;
    } },
    xAxis: { type: "category", data: seasons.map(String), ...axisStyle, splitLine: { show: false } },
    yAxis: { type: "value", ...axisStyle, axisLabel: { color: CHART.muted, formatter: (v: number) => fmtPct(v, 2) } },
    series: DRY.map((c, i) => ({
      name: c[0] + c.slice(1).toLowerCase(), type: "custom" as const, color: COMPOUND_COLORS[c],
      encode: { x: 0, y: [1, 2, 3] },
      data: rows.filter((r) => r.compound === c).map((r) => ({ value: [seasons.indexOf(r.season), r.ci_lo, r.ci_hi, r.slope_pct], r })),
      renderItem: (_p: unknown, api: { value: (i: number) => number; coord: (v: number[]) => number[] }) => {
        const xi = api.value(0) + (i - 1) * 0.2;
        const lo = api.coord([xi, api.value(1)]);
        const hi = api.coord([xi, api.value(2)]);
        const pt = api.coord([xi, api.value(3)]);
        return { type: "group", children: [
          { type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: { stroke: COMPOUND_COLORS[c], lineWidth: 2 } },
          { type: "circle", shape: { cx: pt[0], cy: pt[1], r: 5 }, style: { fill: COMPOUND_COLORS[c], stroke: CHART.surface, lineWidth: 2 } },
        ] };
      },
    })) as EChartsOption["series"],
  };
  return <EChart option={option} height={260} ariaLabel="Degradation rate by compound and season" />;
}

function TemperatureChart({ data }: { data: TyreDegradation }) {
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 32, bottom: 32, containLabel: true },
    legend: { top: 0, left: 0, textStyle: { color: CHART.ink2 }, itemWidth: 10, itemHeight: 10 },
    tooltip: { trigger: "item", formatter: (p: unknown) => {
      const v = (p as { value: [number, number, string] }).value;
      return `${v[2]}<br/>track ${v[0].toFixed(1)} °C · ${fmtPct(v[1], 3)} per lap`;
    } },
    xAxis: { type: "value", ...axisStyle, name: "mean track temperature (°C)", nameLocation: "middle", nameGap: 22, scale: true },
    yAxis: { type: "value", ...axisStyle, axisLabel: { color: CHART.muted, formatter: (v: number) => fmtPct(v, 2) } },
    series: DRY.map((c) => ({
      name: c[0] + c.slice(1).toLowerCase(), type: "scatter" as const, color: COMPOUND_COLORS[c], symbolSize: 7,
      itemStyle: { borderColor: CHART.surface, borderWidth: 1, opacity: 0.8 },
      data: data.session_points.filter((p) => p.compound === c).map((p) => [p.temp, p.slope, p.session_id]),
    })),
  };
  return <EChart option={option} height={260} ariaLabel="Degradation versus track temperature per race" />;
}

export default function TyreWeatherLabPage() {
  const [season, setSeason] = useState<number | 0>(0);
  const [compound, setCompound] = useState<"SOFT" | "MEDIUM" | "HARD">("MEDIUM");
  const [circuit, setCircuit] = useState("");
  const [driver, setDriver] = useState("");
  const [dimension, setDimension] = useState("wet_race");
  const circuits = useCircuits();
  const drivers = useDrivers({ scope: "lap" });
  const deg = useJson<TyreDegradation>(["tyres", season, compound], `/tyres/degradation${qs({ season: season || undefined, compound })}`);
  const all = useJson<TyreDegradation>(["tyres-all"], "/tyres/degradation");
  const cond = useJson<ConditionDimension>(["conditions", dimension], `/conditions${qs({ dimension })}`);
  const curve = useMutation({ mutationFn: () => postJson<DegradationCurve>("/predict/tyre-degradation",
    { compound, circuit_id: circuit || null, driver_id: driver || null, max_tyre_age: 30 }) });
  const ev = all.data?.evaluation;
  const driverRows = useMemo(() => (deg.data?.driver_effects ?? []).slice().sort((a, b) => a.posterior_mean - b.posterior_mean), [deg.data]);

  return (
    <div className="space-y-5">
      <PageHeader title="Tyre & weather laboratory"
        description="Fuel-corrected tyre degradation by compound, circuit and driver, its association with track temperature, and condition-specific driver evidence (wet races, wet qualifying, circuit types) — with sample sizes and uncertainty." />

      {all.isLoading && <LoadingState />}
      {all.error && <ErrorState error={all.error} />}
      {all.data && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Degradation rate by compound and season" subtitle="Precision-weighted mean of stint slopes; 90% session-cluster bootstrap intervals">
            <CompoundSeasonChart rows={all.data.by_compound} />
            <p className="text-[11px] text-ink-muted">{all.data.definitions.slope_pct}. {all.data.limitations[1]}</p>
          </Card>
          <Card title="Degradation vs track temperature" subtitle="One point per race and compound (descriptive association)">
            <TemperatureChart data={all.data} />
            <ul className="mt-1 text-xs tabular text-ink-2">
              {all.data.temperature.map((t) => (
                <li key={t.compound}>{t.compound[0] + t.compound.slice(1).toLowerCase()}: {fmtSigned(t.slope_per_degC, 4)} pp per °C (95% CI {fmtSigned(t.ci_lo, 4)} … {fmtSigned(t.ci_hi, 4)}, {t.n_sessions} races)
                  {" "}{t.ci_lo < 0 && t.ci_hi > 0 ? <StatusPill status="info">no clear association</StatusPill> : <StatusPill status="good">association</StatusPill>}</li>
              ))}
            </ul>
            <p className="mt-1 text-[11px] text-ink-muted">{all.data.limitations[2]}</p>
          </Card>
        </div>
      )}

      <Card title="Degradation curve" subtitle="Expected change in lap time over a stint (linear, fuel-corrected)">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Compound"><Select ariaLabel="Compound" value={compound} onChange={setCompound}
            options={DRY.map((c) => ({ value: c, label: c[0] + c.slice(1).toLowerCase() }))} /></Field>
          <Field label="Circuit (optional)"><Select ariaLabel="Circuit" value={circuit} onChange={setCircuit}
            options={[{ value: "", label: "All circuits" }, ...(circuits.data ?? []).filter((c) => c.has_lap_data).map((c) => ({ value: c.circuit_id, label: c.name }))]} /></Field>
          <Field label="Driver (optional)"><Select ariaLabel="Driver" value={driver} onChange={setDriver}
            options={[{ value: "", label: "No driver adjustment" }, ...(drivers.data?.items ?? []).map((d) => ({ value: d.driver_id, label: d.name }))]} /></Field>
          <Button onClick={() => curve.mutate()} disabled={curve.isPending}>{curve.isPending ? "Computing…" : "Show curve"}</Button>
        </div>
        {curve.error && <div className="mt-3"><ErrorState error={curve.error} /></div>}
        {curve.data && (
          <div className="mt-3 grid gap-4 lg:grid-cols-[2fr_1fr]">
            <DegradationChart curve={curve.data} color={COMPOUND_COLORS[compound]} />
            <div className="space-y-2 text-sm">
              <StatTile label="Slope" value={`${fmtPct(curve.data.slope_pct_per_lap, 3)} / lap`}
                hint={`90%: ${fmtPct(curve.data.slope_ci[0], 3)} … ${fmtPct(curve.data.slope_ci[1], 3)}`} />
              <ul className="list-disc pl-4 text-xs text-ink-2">{curve.data.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
              <p className="text-[11px] text-ink-muted">{curve.data.note}</p>
            </div>
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Driver-specific degradation" subtitle="Stint slope minus other drivers' slopes on the same compound in the same race, shrunk towards zero"
          actions={<Select ariaLabel="Driver effects season" value={season} onChange={setSeason}
            options={[{ value: 0, label: "All seasons" }, ...[2022, 2023, 2024, 2025].map((s) => ({ value: s, label: String(s) }))]} />}>
          {deg.isLoading && <LoadingState />}
          {deg.error && <ErrorState error={deg.error} />}
          {driverRows.length === 0 && !deg.isLoading && <EmptyState>No driver estimates for this selection.</EmptyState>}
          <div className="max-h-80 overflow-y-auto">
            <table className="w-full whitespace-nowrap text-left text-xs tabular">
              <thead className="sticky top-0 bg-surface-1 text-ink-muted"><tr><th className="py-1">Driver</th><th>Season</th><th>Raw ± s.e.</th><th>Shrunk</th><th>Stints</th><th>Status</th></tr></thead>
              <tbody>{driverRows.map((r) => (
                <tr key={`${r.driver_id}-${r.season}`} className="border-t border-line">
                  <td className="py-1">{titleFromId(r.driver_id)}</td><td>{r.season}</td>
                  <td>{fmtSigned(r.raw, 3)} ± {fmtNum(r.raw_se, 3)}</td><td>{r.posterior_sd === 0 ? "0" : fmtSigned(r.posterior_mean, 3)}</td>
                  <td>{r.n_stints}</td>
                  <td><StatusPill status={r.status === "supported" ? "good" : r.status === "insufficient_evidence" ? "warning" : "info"}>{r.status.replace(/_/g, " ")}</StatusPill></td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        </Card>
        <Card title="Does driver-specific degradation help prediction?" subtitle={ev?.protocol}>
          {ev && (
            <>
              <table className="w-full text-left text-sm tabular">
                <thead className="text-xs text-ink-muted"><tr><th className="py-1">Model of the rest of a stint</th><th>MAE %</th><th>MAE s</th></tr></thead>
                <tbody>
                  {Object.entries(ev.mae_pct).map(([k, v]) => (
                    <tr key={k} className="border-t border-line"><td className="py-1 text-ink-2">{titleFromId(k.replace(/_/g, "-"))}</td><td>{fmtNum(v, 3)}</td><td>{fmtNum(ev.mae_s[k], 3)}</td></tr>
                  ))}
                </tbody>
              </table>
              <ul className="mt-3 space-y-1 text-xs">
                {Object.entries(ev.comparisons).map(([k, c]) => (
                  <li key={k} className="flex items-center gap-2">
                    <StatusPill status={c.significant ? "good" : "info"}>{c.significant ? "improves" : "no clear gain"}</StatusPill>
                    <span className="text-ink-2">{k.replace(/_/g, " ")}: ΔMAE {fmtSigned(c.estimate, 3)} pp (95% CI {fmtSigned(c.lo, 3)} … {fmtSigned(c.hi, 3)})</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] text-ink-muted">{ev.n_predicted_laps} laps in {ev.n_events} races predicted.</p>
            </>
          )}
        </Card>
      </div>

      <Card title="Condition-specific driver evidence" subtitle="Deviation from each driver's dry, car-adjusted expectation (2022–2025), empirical-Bayes shrinkage"
        actions={<Select ariaLabel="Condition" value={dimension} onChange={setDimension} options={[
          { value: "wet_race", label: "Wet races" }, { value: "wet_qualifying", label: "Wet qualifying" },
          { value: "street_circuit", label: "Street circuits" }, { value: "high_speed_circuit", label: "High-speed circuits" },
          { value: "slow_corner_circuit", label: "Slow-corner circuits" }]} />}>
        {cond.isLoading && <LoadingState />}
        {cond.error && <ErrorState error={cond.error} />}
        {cond.data && (
          <>
            <p className="mb-2 text-xs text-ink-2">{cond.data.definition} · estimated between-driver SD τ = {fmtNum(cond.data.tau, 3)} pp
              {cond.data.tau === 0 && " — the data show no driver-to-driver differences beyond noise, so every estimate is shrunk to zero."}</p>
            <div className="max-h-96 overflow-y-auto">
              <table className="w-full whitespace-nowrap text-left text-xs tabular">
                <thead className="sticky top-0 bg-surface-1 text-ink-muted"><tr><th className="py-1">Driver</th><th>Raw ± s.e.</th><th>Shrunk (90%)</th><th>Sessions</th><th>Status</th></tr></thead>
                <tbody>{cond.data.rows.map((c) => (
                  <tr key={c.driver_id} className="border-t border-line">
                    <td className="py-1">{titleFromId(c.driver_id)}</td>
                    <td>{c.status === "insufficient_evidence" ? "—" : `${fmtSigned(c.raw, 2)} ± ${fmtNum(c.raw_se, 2)}`}</td>
                    <td>{c.status === "insufficient_evidence" ? "—" : c.posterior_sd === 0 ? "0" : `${fmtSigned(c.posterior_mean, 2)} [${fmtSigned(c.posterior_mean - 1.645 * c.posterior_sd, 2)}, ${fmtSigned(c.posterior_mean + 1.645 * c.posterior_sd, 2)}]`}</td>
                    <td>{c.n_sessions}</td><td><ConditionStatus c={c} /></td>
                  </tr>
                ))}</tbody>
              </table>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
