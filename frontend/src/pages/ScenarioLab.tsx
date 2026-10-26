import { useState } from "react";
import type { EChartsOption } from "echarts";
import { Link } from "react-router-dom";
import { useScenario } from "../api/hooks";
import { Button, Card, EmptyState, ErrorState, LoadingState, PageHeader, StatusPill } from "../components/ui";
import { DriverSelect, ScenarioForm, defaultScenario, scenarioPayload, type ScenarioState } from "../components/ScenarioForm";
import { CHART, EChart, axisStyle } from "../charts/EChart";
import { fmtPct } from "../lib/format";
import type { ScenarioChange } from "../types/api";

function ChangesChart({ changes }: { changes: ScenarioChange[] }) {
  const rows = [...changes].reverse();
  const option: EChartsOption = {
    grid: { left: 210, right: 24, top: 8, bottom: 24, containLabel: false },
    tooltip: { trigger: "item", formatter: (p: unknown) => {
      const r = rows[(p as { dataIndex: number }).dataIndex];
      return `<b>${fmtPct(r.delta_pct, 3)}</b><br/>${r.change}${r.supported ? "" : "<br/>(little training data for this value)"}`;
    } },
    xAxis: { type: "value", ...axisStyle, axisLabel: { color: CHART.muted, formatter: (v: number) => fmtPct(v, 1) } },
    yAxis: { type: "category", data: rows.map((r) => r.change), ...axisStyle, splitLine: { show: false }, axisLabel: { color: CHART.ink2, width: 200, overflow: "truncate" } },
    series: [{ type: "bar", barMaxWidth: 14, data: rows.map((r) => ({ value: r.delta_pct,
      itemStyle: { color: r.delta_pct < 0 ? CHART.faster : CHART.slower, opacity: r.supported ? 1 : 0.45, borderRadius: r.delta_pct < 0 ? [4, 0, 0, 4] : [0, 4, 4, 0] } })),
      markLine: { silent: true, symbol: "none", data: [{ xAxis: 0 }], label: { show: false }, lineStyle: { color: CHART.axis, type: "solid" } } }],
  };
  return <EChart option={option} height={rows.length * 30 + 40} ariaLabel="Model response to single changes" />;
}

function CurveChart({ change, base }: { change: ScenarioChange; base: number }) {
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 16, bottom: 32, containLabel: true },
    tooltip: { trigger: "axis", valueFormatter: (v) => fmtPct(Number(v), 2) },
    xAxis: { type: "value", ...axisStyle, scale: true, name: change.feature.replace(/_/g, " "), nameLocation: "middle", nameGap: 22, splitLine: { show: false } },
    yAxis: { type: "value", ...axisStyle, scale: true, axisLabel: { color: CHART.muted, formatter: (v: number) => fmtPct(v, 1) } },
    series: [{ type: "line", color: CHART.series[0], lineStyle: { width: 2 }, symbolSize: 6,
      data: (change.curve ?? []).map((p) => [p.value, p.prediction_pct]),
      markLine: { silent: true, symbol: "none", data: [{ yAxis: base }], label: { show: true, formatter: "current", color: CHART.muted }, lineStyle: { color: CHART.axis, type: "solid" } } }],
  };
  return <EChart option={option} height={200} ariaLabel={`Prediction across ${change.feature}`} />;
}

export default function ScenarioLabPage() {
  const [driver, setDriver] = useState("");
  const [scenario, setScenario] = useState<ScenarioState>({ ...defaultScenario, mode: "next" });
  const m = useScenario();
  const ready = driver && (scenario.mode === "next" || scenario.event_id);
  return (
    <div className="space-y-5">
      <PageHeader title="Scenario laboratory"
        description="Change one condition at a time and see how the lap-pace model responds, within the range of the training data. This is the model's response, not the causal effect of an intervention; full race simulation (strategy, pit stops, safety cars) is not implemented." />
      <Card title="Scenario">
        <ScenarioForm value={scenario} onChange={setScenario}>
          <DriverSelect season={scenario.mode === "event" ? scenario.season : undefined} value={driver} onChange={setDriver} label="Driver" />
        </ScenarioForm>
        <div className="mt-3 flex items-center gap-3">
          <Button disabled={!ready || m.isPending} onClick={() => m.mutate({ driver_id: driver, ...scenarioPayload(scenario) })}>
            {m.isPending ? "Running…" : "Explore changes"}</Button>
          <Link className="text-sm text-accent" to="/compare">Two-driver comparisons with a common car →</Link>
        </div>
      </Card>
      {m.isPending && <LoadingState />}
      {m.error && <ErrorState error={m.error} />}
      {!m.data && !m.isPending && !m.error && <EmptyState>Choose a driver and run the scenario.</EmptyState>}
      {m.data && (
        <>
          <Card title={`Single changes from the base prediction (${fmtPct(m.data.base_prediction_pct)} vs session reference)`} subtitle={m.data.note}>
            <ChangesChart changes={m.data.changes} />
            <div className="mt-2 flex gap-3 text-xs text-ink-muted">
              <StatusPill status="info">faded bars: values with little training data (e.g. full-wet tyres)</StatusPill>
            </div>
          </Card>
          <div className="grid gap-4 lg:grid-cols-3">
            {m.data.changes.filter((c) => c.curve).map((c) => (
              <Card key={c.feature} title={`Sweep: ${c.feature.replace(/_/g, " ")}`} subtitle="central 98% of training values">
                <CurveChart change={c} base={m.data!.base_prediction_pct} />
              </Card>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
