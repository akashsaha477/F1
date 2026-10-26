import type { EChartsOption } from "echarts";
import { CHART, EChart, axisStyle } from "./EChart";
import type { DriverPerformanceEvent } from "../types/api";
import { fmtPct } from "../lib/format";

/** Race pace per event (median representative lap vs session reference) and gap to team-mate. One axis, two series. */
export function PaceTimeline({ events, title }: { events: DriverPerformanceEvent[]; title: string }) {
  const ev = events.filter((e) => e.med_rel_pace !== null && e.med_rel_pace !== undefined);
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 32, bottom: 40, containLabel: true },
    legend: { top: 0, left: 0, textStyle: { color: CHART.ink2 }, itemWidth: 16, itemHeight: 8 },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "line", lineStyle: { color: CHART.axis } },
      valueFormatter: (v) => fmtPct(v as number),
    },
    xAxis: { type: "category", data: ev.map((e) => e.event_id), ...axisStyle, splitLine: { show: false },
      axisLabel: { color: CHART.muted, rotate: 45, fontSize: 10 } },
    yAxis: { type: "value", inverse: true, ...axisStyle,
      axisLabel: { color: CHART.muted, formatter: (v: number) => fmtPct(v, 1) } },
    series: [
      { name: "Race pace vs session reference", type: "line", color: CHART.series[0], data: ev.map((e) => e.med_rel_pace ?? null), symbolSize: 8,
        lineStyle: { width: 2 }, itemStyle: { color: CHART.series[0], borderColor: CHART.surface, borderWidth: 2 } },
      { name: "Gap to team-mate", type: "line", color: CHART.series[1], data: ev.map((e) => e.teammate_gap ?? null), symbolSize: 8, connectNulls: false,
        lineStyle: { width: 2 }, itemStyle: { color: CHART.series[1], borderColor: CHART.surface, borderWidth: 2 } },
    ],
  };
  return <EChart option={option} height={300} ariaLabel={title} />;
}
