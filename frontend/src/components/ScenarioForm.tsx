import { useMemo } from "react";
import { useCircuits, useDrivers, useEvents, useSeasons } from "../api/hooks";
import { Field, Select, inputClass } from "./ui";

export interface ScenarioState {
  season: number;
  mode: "event" | "next";
  event_id: string;
  circuit_id: string;
  horizon: "pre_event" | "pre_race";
  compound: string;
  tyre_life_laps: number;
  race_progress: number;
  rainfall: boolean;
  track_temp_c: string;
  stint: number;
}

export const defaultScenario: ScenarioState = {
  season: 2025, mode: "event", event_id: "", circuit_id: "silverstone", horizon: "pre_event", compound: "MEDIUM",
  tyre_life_laps: 10, race_progress: 0.5, rainfall: false, track_temp_c: "", stint: 2,
};

const COMPOUNDS = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"];

export function scenarioPayload(s: ScenarioState) {
  return {
    horizon: s.horizon,
    compound: s.compound,
    tyre_life_laps: s.tyre_life_laps,
    race_progress: s.race_progress,
    rainfall: s.rainfall,
    stint: s.stint,
    is_sprint: false,
    track_temp_c: s.track_temp_c === "" ? null : Number(s.track_temp_c),
    ...(s.mode === "event" ? { as_of_event_id: s.event_id || null } : { circuit_id: s.circuit_id }),
  };
}

export function DriverSelect({ season, value, onChange, label }: { season?: number; value: string; onChange: (v: string) => void; label: string }) {
  const drivers = useDrivers({ season, scope: "lap" });
  return (
    <Field label={label}>
      <Select ariaLabel={label} value={value} onChange={onChange}
        options={[{ value: "", label: drivers.isLoading ? "Loading…" : "Select driver" },
          ...(drivers.data?.items ?? []).map((d) => ({ value: d.driver_id, label: d.name }))]} />
    </Field>
  );
}

export function ScenarioForm({ value, onChange, children }: {
  value: ScenarioState; onChange: (s: ScenarioState) => void; children?: React.ReactNode;
}) {
  const seasons = useSeasons();
  const events = useEvents(value.season);
  const circuits = useCircuits();
  const set = <K extends keyof ScenarioState>(k: K, v: ScenarioState[K]) => onChange({ ...value, [k]: v });
  const lapSeasons = useMemo(() => (seasons.data ?? []).filter((s) => s.has_lap_data), [seasons.data]);
  const wet = value.compound === "INTERMEDIATE" || value.compound === "WET";

  return (
    <div className="grid gap-3 md:grid-cols-4">
      <Field label="Form as of">
        <Select ariaLabel="Form as of" value={value.mode} onChange={(v) => set("mode", v)}
          options={[{ value: "event", label: "Before a historical race" }, { value: "next", label: "Next race (latest form)" }]} />
      </Field>
      {value.mode === "event" ? (
        <>
          <Field label="Season">
            <Select ariaLabel="Season" value={value.season} onChange={(v) => onChange({ ...value, season: v, event_id: "" })}
              options={lapSeasons.map((s) => ({ value: s.season, label: String(s.season) }))} />
          </Field>
          <Field label="Race">
            <Select ariaLabel="Race" value={value.event_id} onChange={(v) => set("event_id", v)}
              options={[{ value: "", label: "Select race" }, ...(events.data ?? []).filter((e) => (e.lap_sessions ?? 0) > 0)
                .map((e) => ({ value: e.event_id, label: `${e.round}. ${e.circuit_name ?? e.circuit_id}` }))]} />
          </Field>
        </>
      ) : (
        <Field label="Circuit">
          <Select ariaLabel="Circuit" value={value.circuit_id} onChange={(v) => set("circuit_id", v)}
            options={(circuits.data ?? []).filter((c) => c.has_lap_data).map((c) => ({ value: c.circuit_id, label: c.name }))} />
        </Field>
      )}
      {children}
      <Field label="Horizon" hint={value.horizon === "pre_race" ? "uses this event's qualifying result" : "only information before the weekend"}>
        <Select ariaLabel="Horizon" value={value.horizon} onChange={(v) => set("horizon", v)}
          options={[{ value: "pre_event", label: "Pre-event" }, { value: "pre_race", label: "Pre-race (after qualifying)" }]} />
      </Field>
      <Field label="Tyre compound">
        <Select ariaLabel="Tyre compound" value={value.compound}
          onChange={(v) => onChange({ ...value, compound: v, rainfall: v === "INTERMEDIATE" || v === "WET" ? true : value.rainfall && false })}
          options={COMPOUNDS.map((c) => ({ value: c, label: c[0] + c.slice(1).toLowerCase() }))} />
      </Field>
      <Field label={`Tyre age: ${value.tyre_life_laps} laps`}>
        <input aria-label="Tyre age" type="range" min={1} max={45} value={value.tyre_life_laps}
          onChange={(e) => set("tyre_life_laps", Number(e.target.value))} />
      </Field>
      <Field label={`Race phase: ${(value.race_progress * 100).toFixed(0)}% of distance`} hint="fuel-load proxy">
        <input aria-label="Race phase" type="range" min={0.05} max={1} step={0.05} value={value.race_progress}
          onChange={(e) => set("race_progress", Number(e.target.value))} />
      </Field>
      <Field label="Track temperature °C" hint="blank = circuit's historical median">
        <input aria-label="Track temperature" className={inputClass} inputMode="decimal" value={value.track_temp_c}
          onChange={(e) => set("track_temp_c", e.target.value.replace(/[^0-9.-]/g, ""))} placeholder="auto" />
      </Field>
      <Field label="Rain">
        <label className="flex items-center gap-2 text-sm text-ink">
          <input type="checkbox" checked={value.rainfall || wet} disabled={wet} onChange={(e) => set("rainfall", e.target.checked)} />
          Rain falling {wet && <span className="text-xs text-ink-muted">(implied by wet tyres)</span>}
        </label>
      </Field>
    </div>
  );
}
