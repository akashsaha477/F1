import { useMemo } from "react";
import type { EChartsOption } from "echarts";
import type { Contribution } from "../types/api";
import { CHART, EChart, axisStyle } from "./EChart";
import { fmtPct, fmtSec } from "../lib/format";

/** Horizontal diverging bars: negative (faster) in blue, positive (slower) in red, neutral axis at 0. */
export function ContributionChart({ items, top = 10, unit = "pct", title }: {
  items: Contribution[]; top?: number; unit?: "pct" | "s"; title: string;
}) {
  const rows = useMemo(() => {
    const sorted = [...items].sort((a, b) => Math.abs(b.contribution_pct) - Math.abs(a.contribution_pct));
    const head = sorted.slice(0, top);
    const rest = sorted.slice(top);
    if (rest.length) {
      const v = rest.reduce((s, c) => s + c.contribution_pct, 0);
      const vs = rest.reduce((s, c) => s + (c.contribution_s ?? 0), 0);
      head.push({ feature: "_other", label: `${rest.length} other features`, group: "other", value: null,
        contribution_pct: v, contribution_s: vs, direction: v < 0 ? "faster" : "slower" });
    }
    return head.reverse();
  }, [items, top]);

  const val = (c: Contribution) => (unit === "s" && c.contribution_s !== null ? c.contribution_s : c.contribution_pct);
  const fmt = (v: number) => (unit === "s" ? fmtSec(v, 3) : fmtPct(v, 3));
  const labelled = new Set(
    [...rows].sort((a, b) => Math.abs(val(b)) - Math.abs(val(a))).slice(0, 3).map((r) => r.feature),
  );

  const option: EChartsOption = {
    grid: { left: 200, right: 24, top: 8, bottom: 24, containLabel: false },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const i = (p as { dataIndex: number }).dataIndex;
        const r = rows[i];
        const value = r.value === null || r.value === undefined ? "" : `<br/><span style="color:${CHART.muted}">input: ${String(r.value)}</span>`;
        return `<b>${fmt(val(r))}</b> (${r.direction})<br/><span style="color:${CHART.ink2}">${r.label}</span>${value}`;
      },
    },
    xAxis: {
      type: "value", ...axisStyle,
      // leave room inside the plot for the value labels at the bar tips
      min: (e: { min: number; max: number }) => Math.min(e.min * 1.45, -Math.abs(e.max) * 0.15),
      max: (e: { min: number; max: number }) => Math.max(e.max * 1.45, Math.abs(e.min) * 0.15),
      axisLabel: { color: CHART.muted, hideOverlap: true, showMinLabel: false, showMaxLabel: false, formatter: (v: number) => fmt(v) },
    },
    yAxis: { type: "category", data: rows.map((r) => r.label), ...axisStyle, splitLine: { show: false },
      axisLabel: { color: CHART.ink2, width: 190, overflow: "truncate" } },
    series: [{
      type: "bar",
      barMaxWidth: 14,
      data: rows.map((r) => {
        const v = val(r);
        return {
          value: v,
          itemStyle: { color: v < 0 ? CHART.faster : CHART.slower, borderRadius: v < 0 ? [4, 0, 0, 4] : [0, 4, 4, 0] },
          label: { show: labelled.has(r.feature), position: v < 0 ? "left" : "right", color: CHART.ink2,
            formatter: () => fmt(v) },
        };
      }),
      markLine: { silent: true, symbol: "none", lineStyle: { color: CHART.axis, type: "solid", width: 1 }, data: [{ xAxis: 0 }], label: { show: false } },
    }],
  };

  return (
    <div>
      <EChart option={option} height={Math.max(180, rows.length * 28 + 40)} ariaLabel={title} />
      <div className="mt-1 flex gap-4 text-xs text-ink-muted">
        <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: CHART.faster }} />towards faster</span>
        <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: CHART.slower }} />towards slower</span>
      </div>
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer text-ink-muted">Table view</summary>
        <table className="mt-2 w-full text-left tabular">
          <thead className="text-ink-muted"><tr><th className="py-1">Feature</th><th>Input</th><th className="text-right">Contribution</th></tr></thead>
          <tbody>
            {[...items].sort((a, b) => Math.abs(b.contribution_pct) - Math.abs(a.contribution_pct)).map((r) => (
              <tr key={r.feature} className="border-t border-line">
                <td className="py-1 text-ink-2">{r.label}</td>
                <td className="text-ink-muted">{r.value === null ? "—" : String(typeof r.value === "number" ? Number(r.value.toFixed(3)) : r.value)}</td>
                <td className="text-right">{fmt(val(r))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
