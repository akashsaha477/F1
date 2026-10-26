import type { EChartsOption } from "echarts";
import { CHART, EChart, axisStyle } from "./EChart";

export interface Trace {
  name: string;
  color: string;
  points: { d: number; v: number }[];
}

/** One measure against lap distance for one or two drivers, with an optional highlighted window. */
export function TraceChart({ traces, unit, title, window: win, height = 220 }: {
  traces: Trace[]; unit: string; title: string; window?: [number, number]; height?: number;
}) {
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 28, bottom: 28, containLabel: true },
    legend: traces.length > 1 ? { top: 0, right: 0, textStyle: { color: CHART.ink2 }, itemWidth: 16, itemHeight: 8 } : undefined,
    tooltip: { trigger: "axis", axisPointer: { type: "line", lineStyle: { color: CHART.axis } },
      valueFormatter: (v) => `${Math.round(Number(v))} ${unit}` },
    xAxis: { type: "value", ...axisStyle, name: "distance (m)", nameLocation: "middle", nameGap: 22, splitLine: { show: false } },
    yAxis: { type: "value", ...axisStyle, axisLabel: { color: CHART.muted, formatter: (v: number) => `${v} ${unit}` } },
    series: traces.map((t, i) => ({
      name: t.name, type: "line", showSymbol: false, color: t.color, lineStyle: { width: 2 },
      data: t.points.map((p) => [p.d, p.v]),
      markArea: i === 0 && win ? { silent: true, itemStyle: { color: "rgba(255,255,255,0.05)" }, data: [[{ xAxis: win[0] }, { xAxis: win[1] }]] } : undefined,
    })),
  };
  return <EChart option={option} height={height} ariaLabel={title} />;
}
