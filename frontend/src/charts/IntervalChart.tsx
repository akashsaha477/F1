import type { EChartsOption } from "echarts";
import { CHART, EChart, axisStyle } from "./EChart";
import { fmtPct } from "../lib/format";

export interface IntervalRow {
  label: string;
  point: number;
  lo: number;
  hi: number;
  color?: string;
}

/** Point estimates with interval whiskers on one shared axis (% vs session reference). */
export function IntervalChart({ rows, title }: { rows: IntervalRow[]; title: string }) {
  const data = rows.map((r, i) => [i, r.lo, r.hi, r.point]);
  const option: EChartsOption = {
    grid: { left: 210, right: 24, top: 8, bottom: 40, containLabel: false },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const r = rows[(p as { dataIndex: number }).dataIndex];
        return `<b>${fmtPct(r.point)}</b><br/>${r.label}<br/><span style="color:${CHART.muted}">${fmtPct(r.lo)} to ${fmtPct(r.hi)}</span>`;
      },
    },
    xAxis: { type: "value", ...axisStyle, name: "% vs session reference (negative = faster)", nameLocation: "middle", nameGap: 22,
      axisLabel: { color: CHART.muted, formatter: (v: number) => fmtPct(v, 1) } },
    yAxis: { type: "category", data: rows.map((r) => r.label), inverse: true, ...axisStyle, splitLine: { show: false },
      axisLabel: { color: CHART.ink2, width: 200, overflow: "truncate" } },
    series: [{
      type: "custom",
      encode: { x: [1, 2, 3], y: 0 },
      markLine: { silent: true, symbol: "none", data: [{ xAxis: 0 }], label: { show: false },
        lineStyle: { color: CHART.axis, type: "solid", width: 1 } },
      data,
      renderItem: (params, api) => {
        const i = api.value(0) as number;
        const lo = api.coord([api.value(1), i]);
        const hi = api.coord([api.value(2), i]);
        const pt = api.coord([api.value(3), i]);
        const color = rows[params.dataIndex].color ?? CHART.series[0];
        return {
          type: "group",
          children: [
            { type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: { stroke: color, lineWidth: 2, opacity: 0.7 } },
            { type: "line", shape: { x1: lo[0], y1: lo[1] - 6, x2: lo[0], y2: lo[1] + 6 }, style: { stroke: color, lineWidth: 2 } },
            { type: "line", shape: { x1: hi[0], y1: hi[1] - 6, x2: hi[0], y2: hi[1] + 6 }, style: { stroke: color, lineWidth: 2 } },
            { type: "circle", shape: { cx: pt[0], cy: pt[1], r: 5 }, style: { fill: color, stroke: CHART.surface, lineWidth: 2 } },
          ],
        };
      },
    }],
  };
  return <EChart option={option} height={Math.max(120, rows.length * 44 + 50)} ariaLabel={title} />;
}
