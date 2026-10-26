import type { EChartsOption } from "echarts";
import { CHART, EChart, axisStyle } from "./EChart";
import { fmtPct } from "../lib/format";
import type { DegradationCurve } from "../types/api";

/** Expected change in lap time with tyre age (single series + 90% band). */
export function DegradationChart({ curve, color }: { curve: DegradationCurve; color: string }) {
  const x = curve.points.map((p) => p.tyre_age);
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 16, bottom: 32, containLabel: true },
    tooltip: { trigger: "axis", axisPointer: { type: "line", lineStyle: { color: CHART.axis } },
      formatter: (ps: unknown) => {
        const i = (ps as { dataIndex: number }[])[0].dataIndex;
        const p = curve.points[i];
        const sec = curve.reference_lap_s ? ` (${((p.delta_pct * curve.reference_lap_s) / 100).toFixed(2)} s)` : "";
        return `<b>${fmtPct(p.delta_pct)}</b>${sec}<br/>tyre age ${p.tyre_age}<br/><span style="color:${CHART.muted}">90%: ${fmtPct(p.lo_pct)} … ${fmtPct(p.hi_pct)}</span>`;
      } },
    xAxis: { type: "category", data: x, ...axisStyle, name: "tyre age (laps)", nameLocation: "middle", nameGap: 22, splitLine: { show: false } },
    yAxis: { type: "value", ...axisStyle, axisLabel: { color: CHART.muted, formatter: (v: number) => fmtPct(v, 1) } },
    series: [
      { type: "line", data: curve.points.map((p) => p.lo_pct), stack: "band", lineStyle: { opacity: 0 }, showSymbol: false, silent: true },
      { type: "line", data: curve.points.map((p) => p.hi_pct - p.lo_pct), stack: "band", lineStyle: { opacity: 0 }, showSymbol: false,
        areaStyle: { color, opacity: 0.12 }, silent: true },
      { type: "line", data: curve.points.map((p) => p.delta_pct), color, lineStyle: { width: 2 }, showSymbol: false },
    ],
  };
  return <EChart option={option} height={240} ariaLabel={`Degradation curve for ${curve.compound}`} />;
}
