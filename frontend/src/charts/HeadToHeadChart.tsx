import type { EChartsOption } from "echarts";
import { CHART, EChart, axisStyle } from "./EChart";
import { fmtPct } from "../lib/format";

/** Per-session pace difference (A minus B); blue when A was faster, red when slower. */
export function HeadToHeadChart({ sessions, aName, bName }: {
  sessions: { session_id: string; diff: number; same_team: boolean; condition: string }[]; aName: string; bName: string;
}) {
  const option: EChartsOption = {
    grid: { left: 8, right: 16, top: 16, bottom: 56, containLabel: true },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const s = sessions[(p as { dataIndex: number }).dataIndex];
        return `<b>${fmtPct(s.diff)}</b> ${s.diff < 0 ? `${aName} faster` : `${bName} faster`}<br/>${s.session_id} · ${s.condition}${s.same_team ? " · team-mates" : ""}`;
      },
    },
    xAxis: { type: "category", data: sessions.map((s) => s.session_id), ...axisStyle, splitLine: { show: false },
      axisLabel: { color: CHART.muted, rotate: 60, fontSize: 10 } },
    yAxis: { type: "value", ...axisStyle, axisLabel: { color: CHART.muted, formatter: (v: number) => fmtPct(v, 1) } },
    series: [{
      type: "bar", barMaxWidth: 12,
      data: sessions.map((s) => ({ value: s.diff, itemStyle: { color: s.diff < 0 ? CHART.faster : CHART.slower,
        borderRadius: s.diff < 0 ? [0, 0, 4, 4] : [4, 4, 0, 0], opacity: s.condition === "dry" ? 1 : 0.5 } })),
    }],
  };
  return <EChart option={option} height={260} ariaLabel={`Session by session pace difference ${aName} minus ${bName}`} />;
}
