import type { EChartsOption } from "echarts";
import { CHART, EChart, axisStyle } from "./EChart";
import { fmtLapTime } from "../lib/format";
import type { TraceLap } from "../types/api";

export interface ActualLap { lap: number; lap_time_s: number | null; compound: string; clean: boolean; reason: string | null }

/**
 * Expected lap times of the recommended plan (and an alternative), with — for past races — the driver's
 * actual laps and the model's replay of the strategy the driver actually ran.
 */
export function RaceTraceChart({ best, bestLabel, alternative, alternativeLabel, actual, replay }: {
  best: TraceLap[]; bestLabel: string; alternative?: TraceLap[] | null; alternativeLabel?: string | null;
  actual?: ActualLap[] | null; replay?: TraceLap[] | null;
}) {
  const line = (rows: TraceLap[]) => rows.map((r) => ({ value: [r.lap, r.lap_time_s], r }));
  const series: EChartsOption["series"] = [
    { name: `Plan: ${bestLabel}`, type: "line", color: CHART.series[0], showSymbol: false, lineStyle: { width: 2 }, data: line(best) },
  ];
  if (alternative && alternativeLabel) {
    series.push({ name: `Alternative: ${alternativeLabel}`, type: "line", color: CHART.series[1], showSymbol: false,
      lineStyle: { width: 2, type: "dashed" }, data: line(alternative) });
  }
  if (replay) {
    series.push({ name: "Model replay of actual strategy", type: "line", color: CHART.series[3], showSymbol: false,
      lineStyle: { width: 2 }, data: line(replay) });
  }
  if (actual) {
    series.push({ name: "Actual laps", type: "scatter", color: CHART.series[2], symbolSize: 6,
      data: actual.filter((a) => a.lap_time_s !== null).map((a) => ({ value: [a.lap, a.lap_time_s], a })),
      itemStyle: { opacity: 0.9 } });
  }
  const vals = [...best, ...(alternative ?? [])].filter((r) => r.pit === null && r.lap > 1).map((r) => r.lap_time_s).sort((a, b) => a - b);
  const lo = vals[0] ?? 60;
  const hi = vals[vals.length - 1] ?? 100;
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 52, bottom: 32, containLabel: true },
    legend: { top: 0, left: 0, textStyle: { color: CHART.ink2 }, itemWidth: 14, itemHeight: 8 },
    tooltip: { trigger: "item", formatter: (p: unknown) => {
      const d = (p as { seriesName: string; data: { r?: TraceLap; a?: ActualLap } });
      if (d.data.a) {
        const a = d.data.a;
        return `Actual · lap ${a.lap}<br/><b>${fmtLapTime(a.lap_time_s)}</b> on ${a.compound}` +
          `<br/><span style="color:${CHART.muted}">${a.clean ? "clean lap" : `excluded: ${a.reason}`}</span>`;
      }
      const r = d.data.r as TraceLap;
      return `${d.seriesName} · lap ${r.lap}<br/><b>${fmtLapTime(r.lap_time_s)}</b> · ${r.compound}, ${r.tyre_age} laps old` +
        (r.pit ? `<br/><span style="color:${CHART.muted}">pit ${r.pit}-lap (includes half the pit loss)</span>` : "");
    } },
    xAxis: { type: "value", ...axisStyle, name: "lap", nameLocation: "middle", nameGap: 22, minInterval: 1, splitLine: { show: false } },
    yAxis: { type: "value", ...axisStyle, min: Math.floor(lo - 1.5), max: Math.ceil(hi + 3),
      axisLabel: { color: CHART.muted, formatter: (v: number) => fmtLapTime(v) } },
    series,
  };
  return <EChart option={option} height={340} ariaLabel="Expected and actual lap times" />;
}
