import { useEffect, useState } from "react";
import type { EChartsOption } from "echarts";
import { useSeasonEffects, useSeasons } from "../api/hooks";
import { Card, ErrorState, LoadingState, Select } from "./ui";
import { CHART, EChart, axisStyle } from "../charts/EChart";
import { fmtPct, titleFromId } from "../lib/format";

/** Team-adjusted race pace of every driver in a season with 90% intervals (one series). */
export function DriverEffectsCard() {
  const seasons = useSeasons();
  const [season, setSeason] = useState<number | undefined>();
  useEffect(() => {
    if (!season && seasons.data) setSeason(seasons.data.find((s) => s.has_lap_data)?.season);
  }, [season, seasons.data]);
  const q = useSeasonEffects(season);
  const rows = (q.data?.drivers ?? []).filter((d) => d.n_dry_races >= 5);
  const option: EChartsOption = {
    grid: { left: 150, right: 24, top: 8, bottom: 40, containLabel: false },
    tooltip: {
      trigger: "item",
      formatter: (p: unknown) => {
        const r = rows[(p as { dataIndex: number }).dataIndex];
        return `<b>${fmtPct(r.race_pace_adj)}</b> team-adjusted<br/>${titleFromId(r.driver_id)} · ${titleFromId(r.main_team)}<br/>` +
          `<span style="color:${CHART.muted}">90%: ${fmtPct(r.race_pace_adj_lo)} … ${fmtPct(r.race_pace_adj_hi)} · ${r.n_dry_races} races<br/>team effect ${fmtPct(r.team_effect)}</span>`;
      },
    },
    xAxis: { type: "value", ...axisStyle, name: "% of lap vs. an average driver in the same car (negative = faster)", nameLocation: "middle", nameGap: 24,
      axisLabel: { color: CHART.muted, formatter: (v: number) => fmtPct(v, 1) } },
    yAxis: { type: "category", inverse: true, data: rows.map((r) => titleFromId(r.driver_id)), ...axisStyle, splitLine: { show: false },
      axisLabel: { color: CHART.ink2 } },
    series: [{
      type: "custom",
      data: rows.map((r, i) => [i, r.race_pace_adj_lo, r.race_pace_adj_hi, r.race_pace_adj]),
      encode: { x: [1, 2, 3], y: 0 },
      renderItem: (_params, api) => {
        const i = api.value(0) as number;
        const lo = api.coord([api.value(1), i]);
        const hi = api.coord([api.value(2), i]);
        const pt = api.coord([api.value(3), i]);
        return { type: "group", children: [
          { type: "line", shape: { x1: lo[0], y1: lo[1], x2: hi[0], y2: hi[1] }, style: { stroke: CHART.series[0], lineWidth: 2, opacity: 0.6 } },
          { type: "circle", shape: { cx: pt[0], cy: pt[1], r: 5 }, style: { fill: CHART.series[0], stroke: CHART.surface, lineWidth: 2 } },
        ] };
      },
      markLine: { silent: true, symbol: "none", data: [{ xAxis: 0 }], label: { show: false }, lineStyle: { color: CHART.axis, type: "solid" } },
    }],
  };
  return (
    <Card title="Team-adjusted driver race pace"
      subtitle="Driver + driver-season effects from a crossed random-effects model of condition-adjusted race pace (dry races, ≥5 races). Intervals are 90% posterior intervals."
      actions={<Select ariaLabel="Effects season" value={season ?? ""} onChange={(v) => setSeason(v)}
        options={(seasons.data ?? []).filter((s) => s.has_lap_data).map((s) => ({ value: s.season, label: String(s.season) }))} />}>
      {q.isLoading && <LoadingState />}
      {q.error && <ErrorState error={q.error} />}
      {rows.length > 0 && <EChart option={option} height={rows.length * 22 + 60} ariaLabel={`Team-adjusted race pace ${season}`} />}
      {q.data && <p className="mt-2 text-[11px] text-ink-muted">{q.data.meta.identification_note}</p>}
    </Card>
  );
}
