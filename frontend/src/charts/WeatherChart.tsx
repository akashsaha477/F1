import type { EChartsOption } from "echarts";
import { CHART, EChart, axisStyle } from "./EChart";

export interface WeatherRow {
  session_time_s: number;
  air_temp_c: number | null;
  track_temp_c: number | null;
  rainfall: boolean | null;
}

/** Track and air temperature over the session (one axis, °C); rain periods shaded. */
export function WeatherChart({ rows }: { rows: WeatherRow[] }) {
  const mins = (t: number) => Math.round(t / 6) / 10;
  const rain: [number, number][] = [];
  let start: number | null = null;
  rows.forEach((r, i) => {
    if (r.rainfall && start === null) start = mins(r.session_time_s);
    if ((!r.rainfall || i === rows.length - 1) && start !== null) { rain.push([start, mins(r.session_time_s)]); start = null; }
  });
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 32, bottom: 32, containLabel: true },
    legend: { top: 0, left: 0, textStyle: { color: CHART.ink2 }, itemWidth: 16, itemHeight: 8 },
    tooltip: { trigger: "axis", axisPointer: { type: "line", lineStyle: { color: CHART.axis } }, valueFormatter: (v) => `${Number(v).toFixed(1)} °C` },
    xAxis: { type: "value", ...axisStyle, name: "session time (min)", nameLocation: "middle", nameGap: 22, splitLine: { show: false } },
    yAxis: { type: "value", ...axisStyle, scale: true, axisLabel: { color: CHART.muted, formatter: (v: number) => `${v} °C` } },
    series: [
      { name: "Track", type: "line", color: CHART.series[1], showSymbol: false, lineStyle: { width: 2 },
        data: rows.map((r) => [mins(r.session_time_s), r.track_temp_c]),
        markArea: rain.length ? { silent: true, itemStyle: { color: "rgba(57,135,229,0.12)" }, label: { show: false },
          data: rain.map(([a, b]) => [{ xAxis: a }, { xAxis: b }]) } : undefined },
      { name: "Air", type: "line", color: CHART.series[0], showSymbol: false, lineStyle: { width: 2 },
        data: rows.map((r) => [mins(r.session_time_s), r.air_temp_c]) },
    ],
  };
  return <EChart option={option} height={220} ariaLabel="Weather during the session" />;
}
