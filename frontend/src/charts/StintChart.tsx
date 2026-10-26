import type { EChartsOption } from "echarts";
import { CHART, EChart, axisStyle } from "./EChart";
import { COMPOUND_COLORS } from "../lib/format";

export interface StintRow {
  driver_id: string;
  stint: number;
  compound: string;
  start_lap: number;
  end_lap: number;
  n_laps: number;
  tyre_life_start: number | null;
}

/** One row per driver, one bar per stint coloured by compound (with a 2px surface gap between stints). */
export function StintChart({ stints, order }: { stints: StintRow[]; order: string[] }) {
  const compounds = Array.from(new Set(stints.map((s) => s.compound)));
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 32, bottom: 32, containLabel: true },
    legend: { top: 0, left: 0, textStyle: { color: CHART.ink2 }, itemWidth: 10, itemHeight: 10, data: compounds },
    tooltip: { trigger: "item", formatter: (p: unknown) => {
      const s = (p as { data: { s: StintRow } }).data.s;
      return `${s.driver_id} · stint ${s.stint}<br/><b>${s.compound}</b> laps ${s.start_lap}–${s.end_lap}` +
        (s.tyre_life_start !== null ? `<br/><span style="color:${CHART.muted}">tyre age at start ${s.tyre_life_start}</span>` : "");
    } },
    xAxis: { type: "value", ...axisStyle, name: "lap", nameLocation: "middle", nameGap: 22, splitLine: { show: false } },
    yAxis: { type: "category", data: order, inverse: true, ...axisStyle, splitLine: { show: false }, axisLabel: { color: CHART.ink2, fontSize: 10 } },
    series: compounds.map((c) => ({
      name: c, type: "custom" as const, color: COMPOUND_COLORS[c] ?? CHART.muted,
      encode: { x: [1, 2], y: 0 },
      data: stints.filter((s) => s.compound === c).map((s) => ({ value: [order.indexOf(s.driver_id), s.start_lap - 0.5, s.end_lap + 0.5], s })),
      renderItem: (_p: unknown, api: { value: (i: number) => number; coord: (v: number[]) => number[]; size: (v: number[]) => number[] }) => {
        const y = api.value(0);
        const a = api.coord([api.value(1), y]);
        const b = api.coord([api.value(2), y]);
        const h = Math.min(api.size([0, 1])[1] * 0.6, 14);
        return { type: "rect", shape: { x: a[0] + 1, y: a[1] - h / 2, width: Math.max(b[0] - a[0] - 2, 1), height: h, r: 3 },
          style: { fill: COMPOUND_COLORS[c] ?? CHART.muted } };
      },
    })) as EChartsOption["series"],
  };
  return <EChart option={option} height={Math.max(220, order.length * 18 + 70)} ariaLabel="Tyre stints by driver" />;
}
