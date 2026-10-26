import { useEffect, useRef } from "react";
import * as echarts from "echarts";
import type { EChartsOption } from "echarts";

/** Chart chrome tokens (dark), matching src/styles/index.css. */
export const CHART = {
  surface: "#1a1a19",
  ink: "#f0efec",
  ink2: "#c3c2b7",
  muted: "#898781",
  grid: "#2c2c2a",
  axis: "#383835",
  series: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
  faster: "#3987e5",
  slower: "#e66767",
  neutral: "#383835",
};

export const baseOption: EChartsOption = {
  backgroundColor: "transparent",
  textStyle: { color: CHART.ink2, fontFamily: "Inter, system-ui, sans-serif", fontSize: 12 },
  color: CHART.series,
  tooltip: {
    backgroundColor: "#222220",
    borderColor: CHART.grid,
    textStyle: { color: CHART.ink },
    confine: true,
  },
  grid: { left: 8, right: 16, top: 24, bottom: 8, containLabel: true },
};

export const axisStyle = {
  axisLine: { lineStyle: { color: CHART.axis } },
  axisTick: { show: false },
  axisLabel: { color: CHART.muted },
  splitLine: { lineStyle: { color: CHART.grid, type: "solid" as const } },
  nameTextStyle: { color: CHART.muted },
};

export function EChart({ option, height = 280, ariaLabel }: { option: EChartsOption; height?: number; ariaLabel: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    if (typeof window === "undefined" || !("ResizeObserver" in window)) return; // jsdom: skip rendering
    chart.current = echarts.init(ref.current, undefined, { renderer: "canvas" });
    const ro = new ResizeObserver(() => chart.current?.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      chart.current?.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    chart.current?.setOption({ ...baseOption, ...option }, { notMerge: true });
  }, [option]);

  return <div ref={ref} role="img" aria-label={ariaLabel} style={{ height, width: "100%" }} />;
}
