import { useMemo } from "react";
import type { CornerDef, TrackLayout } from "../types/api";

// Sequential blue ramp (reference palette, light->dark = slow->fast is avoided: fast = darker would vanish on
// the dark surface, so the ramp runs dark->light with speed for legibility on #1a1a19).
const RAMP = ["#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#6da7ec", "#86b6ef", "#9ec5f4", "#b7d3f6"];
const FASTER = "#3987e5";
const SLOWER = "#e66767";

function rotate(x: number, y: number, deg: number) {
  const r = (deg * Math.PI) / 180;
  return [x * Math.cos(r) - y * Math.sin(r), x * Math.sin(r) + y * Math.cos(r)];
}

export interface CornerDelta {
  corner_id: string;
  delta: number; // A minus B, seconds
}

export function TrackMap({ layout, selected, onSelect, deltas, aName, bName }: {
  layout: TrackLayout; selected?: string; onSelect: (id: string) => void; deltas?: CornerDelta[]; aName?: string; bName?: string;
}) {
  const geo = useMemo(() => {
    const pts = layout.track.map((p) => rotate(p.x, p.y, layout.rotation_deg));
    const xs = pts.map((p) => p[0]);
    const ys = pts.map((p) => -p[1]); // SVG y axis points down
    const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
    const pad = Math.max(maxX - minX, maxY - minY) * 0.08;
    const speeds = layout.track.map((p) => p.speed_ref ?? 0);
    const lo = Math.min(...speeds), hi = Math.max(...speeds);
    const segs = pts.slice(0, -1).map((p, i) => {
      const t = hi > lo ? (speeds[i] - lo) / (hi - lo) : 0.5;
      return { x1: p[0], y1: -p[1], x2: pts[i + 1][0], y2: -pts[i + 1][1], color: RAMP[Math.min(RAMP.length - 1, Math.floor(t * RAMP.length))], v: speeds[i], s: layout.track[i].s };
    });
    const corners = layout.corners.map((c) => {
      const [x, y] = rotate(c.x, c.y, layout.rotation_deg);
      return { ...c, px: x, py: -y };
    });
    const sectorTicks = (layout.sector_bounds_m ?? []).map((b) => {
      const i = layout.track.findIndex((p) => p.s >= b);
      const p = pts[Math.max(0, i)];
      return { x: p[0], y: -p[1] };
    });
    return { segs, corners, sectorTicks, viewBox: `${minX - pad} ${minY - pad} ${maxX - minX + 2 * pad} ${maxY - minY + 2 * pad}`,
      size: Math.max(maxX - minX, maxY - minY), lo, hi, start: { x: pts[0][0], y: -pts[0][1] } };
  }, [layout]);

  const deltaMap = new Map((deltas ?? []).map((d) => [d.corner_id, d.delta]));
  const stroke = geo.size / 90;
  const r = geo.size / 70;

  const cornerFill = (c: CornerDef) => {
    if (deltas) {
      const d = deltaMap.get(c.corner_id);
      if (d === undefined || Number.isNaN(d)) return "#383835";
      return d < 0 ? FASTER : SLOWER;
    }
    return "#383835";
  };

  return (
    <div>
      <svg viewBox={geo.viewBox} role="group" aria-label={`Track map of ${layout.circuit_id}`} className="h-[440px] w-full">
        {geo.segs.map((s, i) => (
          <line key={i} x1={s.x1} y1={s.y1} x2={s.x2} y2={s.y2} stroke={s.color} strokeWidth={stroke} strokeLinecap="round">
            <title>{`${Math.round(s.s)} m · ${Math.round(s.v)} km/h (reference lap)`}</title>
          </line>
        ))}
        <circle cx={geo.start.x} cy={geo.start.y} r={r * 0.6} fill="#f0efec" stroke="#1a1a19" strokeWidth={stroke / 3}>
          <title>Start / finish (lap start of the reference lap)</title>
        </circle>
        {geo.sectorTicks.map((t, i) => (
          <g key={i}>
            <rect x={t.x - r * 0.4} y={t.y - r * 0.4} width={r * 0.8} height={r * 0.8} fill="#c98500" stroke="#1a1a19" strokeWidth={stroke / 4} />
            <title>{`End of sector ${i + 1}`}</title>
          </g>
        ))}
        {geo.corners.map((c) => {
          const d = deltaMap.get(c.corner_id);
          return (
            <g key={c.corner_id} role="button" tabIndex={0} aria-label={`Corner ${c.corner_id}`} style={{ cursor: "pointer" }}
              onClick={() => onSelect(c.corner_id)} onKeyDown={(e) => { if (e.key === "Enter") onSelect(c.corner_id); }}>
              <circle cx={c.px} cy={c.py} r={selected === c.corner_id ? r * 1.4 : r} fill={cornerFill(c)}
                stroke={selected === c.corner_id ? "#f0efec" : "#1a1a19"} strokeWidth={stroke / 2.5} />
              <text x={c.px + r * 1.3} y={c.py - r * 0.9} fontSize={r * 1.5} fill="#c3c2b7">{c.corner_id}</text>
              <title>{`${c.corner_id} · ${c.category.replace("_", "-")} · min ${Math.round(c.min_speed_ref)} km/h` +
                (d !== undefined ? ` · ${aName} ${d < 0 ? "faster" : "slower"} by ${Math.abs(d).toFixed(3)} s` : "")}</title>
            </g>
          );
        })}
      </svg>
      <div className="mt-2 flex flex-wrap items-center gap-4 text-xs text-ink-muted">
        <span className="flex items-center gap-1">
          Reference-lap speed {Math.round(geo.lo)}
          <span className="inline-flex h-2 w-24 overflow-hidden rounded">{RAMP.map((c) => <span key={c} className="flex-1" style={{ background: c }} />)}</span>
          {Math.round(geo.hi)} km/h
        </span>
        <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5" style={{ background: "#c98500" }} />sector boundary</span>
        {deltas && <>
          <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: FASTER }} />{aName} faster</span>
          <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: SLOWER }} />{bName} faster</span>
          <span className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "#383835" }} />no valid comparison</span>
        </>}
      </div>
    </div>
  );
}
