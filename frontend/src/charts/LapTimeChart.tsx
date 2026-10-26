import type { EChartsOption } from "echarts";
import { CHART, EChart, axisStyle } from "./EChart";
import type { Lap } from "../types/api";
import { fmtLapTime } from "../lib/format";

/** Lap times by lap number; clean laps are filled markers, excluded laps are hollow and keep their label. */
export function LapTimeChart({ laps, drivers }: { laps: Lap[]; drivers: string[] }) {
  const series = drivers.flatMap((d, i) => {
    const color = CHART.series[i];
    const own = laps.filter((l) => l.driver_id === d && l.lap_time_s !== null);
    const other = own.filter((l) => !l.is_clean);
    // the line only joins consecutive clean laps; an excluded lap breaks it
    const line = laps.filter((l) => l.driver_id === d).sort((a, b) => a.lap_number - b.lap_number)
      .map((l) => (l.is_clean && l.lap_time_s !== null ? { value: [l.lap_number, l.lap_time_s], lap: l } : { value: [l.lap_number, null], lap: l }));
    return [
      { name: d, type: "line" as const, color, showSymbol: true, symbolSize: 6, lineStyle: { width: 2 }, data: line, connectNulls: false },
      { name: `${d} (excluded)`, type: "scatter" as const, color, symbol: "emptyCircle", symbolSize: 7,
        data: other.map((l) => ({ value: [l.lap_number, l.lap_time_s], lap: l })) },
    ];
  });
  const clean = laps.filter((l) => l.is_clean && l.lap_time_s);
  const sorted = clean.map((l) => l.lap_time_s as number).sort((a, b) => a - b);
  const p95 = sorted[Math.floor(sorted.length * 0.98)] ?? undefined;
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 32, bottom: 32, containLabel: true },
    legend: { top: 0, left: 0, textStyle: { color: CHART.ink2 }, itemWidth: 12, itemHeight: 8, data: drivers },
    tooltip: { trigger: "item", formatter: (p: unknown) => {
      const l = (p as { data: { lap: Lap } }).data.lap;
      return `<b>${fmtLapTime(l.lap_time_s)}</b> · lap ${l.lap_number}<br/>${l.driver_id} · ${l.compound} (${l.tyre_life_laps ?? "?"} laps old)` +
        `<br/><span style="color:${CHART.muted}">${l.is_clean ? "clean lap" : `excluded: ${l.exclusion_reason}`}</span>`;
    } },
    xAxis: { type: "value", ...axisStyle, name: "lap", nameLocation: "middle", nameGap: 22, minInterval: 1, splitLine: { show: false } },
    yAxis: { type: "value", ...axisStyle, scale: true, max: p95 ? Math.ceil(p95 * 1.04) : undefined,
      axisLabel: { color: CHART.muted, formatter: (v: number) => fmtLapTime(v) } },
    series,
  };
  return <EChart option={option} height={320} ariaLabel="Lap times by lap" />;
}
