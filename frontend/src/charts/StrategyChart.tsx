import type { EChartsOption } from "echarts";
import { CHART, EChart, axisStyle } from "./EChart";
import { COMPOUND_COLORS } from "../lib/format";

export interface StrategyRowInput {
  label: string;
  sequence: string[];
  stint_laps: number[];
  windows?: { from_lap: number; to_lap: number }[];
  note?: string;
}

interface Seg { row: number; from: number; to: number; compound: string; stint: number; label: string; note?: string }

/** One row per strategy: stints coloured by compound (2px gaps), pit windows as a faint band behind the bar. */
export function StrategyChart({ rows, laps, height }: { rows: StrategyRowInput[]; laps: number; height?: number }) {
  const labels = rows.map((r) => r.label);
  const segs: Seg[] = [];
  const wins: { row: number; from: number; to: number }[] = [];
  rows.forEach((r, i) => {
    let start = 0;
    r.sequence.forEach((c, k) => {
      const L = r.stint_laps[k];
      segs.push({ row: i, from: start, to: start + L, compound: c, stint: k + 1, label: r.label, note: r.note });
      start += L;
    });
    (r.windows ?? []).forEach((w) => wins.push({ row: i, from: w.from_lap - 0.5, to: w.to_lap + 0.5 }));
  });
  const compounds = Array.from(new Set(segs.map((s) => s.compound)));
  type Api = { value: (i: number) => number; coord: (v: number[]) => number[]; size: (v: number[]) => number[] };
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 32, bottom: 32, containLabel: true },
    legend: { top: 0, left: 0, textStyle: { color: CHART.ink2 }, itemWidth: 10, itemHeight: 10,
      data: [...compounds, ...(wins.length ? ["pit window"] : [])] },
    tooltip: { trigger: "item", formatter: (p: unknown) => {
      const d = (p as { data: { s?: Seg; w?: { from: number; to: number } } }).data;
      if (d.w) return `Pit window: laps ${Math.ceil(d.w.from)}–${Math.floor(d.w.to)}`;
      const s = d.s as Seg;
      return `${s.label}<br/>stint ${s.stint}: <b>${s.compound}</b>, laps ${s.from + 1}–${s.to} (${s.to - s.from} laps)` +
        (s.note ? `<br/><span style="color:${CHART.muted}">${s.note}</span>` : "");
    } },
    xAxis: { type: "value", min: 0, max: laps, ...axisStyle, name: "lap", nameLocation: "middle", nameGap: 22, splitLine: { show: false },
      axisLabel: { color: CHART.muted, showMaxLabel: false } },
    yAxis: { type: "category", data: labels, inverse: true, ...axisStyle, splitLine: { show: false },
      axisLabel: { color: CHART.ink2, fontSize: 11 } },
    series: [
      ...(wins.length ? [{
        name: "pit window", type: "custom" as const, color: "rgba(195,194,183,0.28)", encode: { x: [1, 2], y: 0 },
        data: wins.map((w) => ({ value: [w.row, w.from, w.to], w })),
        renderItem: (_p: unknown, api: Api) => {
          const a = api.coord([api.value(1), api.value(0)]);
          const b = api.coord([api.value(2), api.value(0)]);
          const h = Math.min(api.size([0, 1])[1] * 0.85, 26);
          return { type: "rect", shape: { x: a[0], y: a[1] - h / 2, width: Math.max(b[0] - a[0], 2), height: h, r: 3 },
            style: { fill: "rgba(195,194,183,0.18)" } };
        },
      }] : []),
      ...compounds.map((c) => ({
        name: c, type: "custom" as const, color: COMPOUND_COLORS[c] ?? CHART.muted, encode: { x: [1, 2], y: 0 },
        data: segs.filter((s) => s.compound === c).map((s) => ({ value: [s.row, s.from, s.to], s })),
        renderItem: (_p: unknown, api: Api) => {
          const a = api.coord([api.value(1), api.value(0)]);
          const b = api.coord([api.value(2), api.value(0)]);
          const h = Math.min(api.size([0, 1])[1] * 0.5, 14);
          return { type: "rect", shape: { x: a[0] + 1, y: a[1] - h / 2, width: Math.max(b[0] - a[0] - 2, 1), height: h, r: 3 },
            style: { fill: COMPOUND_COLORS[c] ?? CHART.muted } };
        },
      })),
    ] as EChartsOption["series"],
  };
  return <EChart option={option} height={height ?? Math.max(160, rows.length * 34 + 70)} ariaLabel="Tyre strategies and pit windows" />;
}
