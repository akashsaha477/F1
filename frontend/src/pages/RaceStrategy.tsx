import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useConstructors, useRaceWeeks, useStrategyPlan } from "../api/hooks";
import { DriverSelect } from "../components/ScenarioForm";
import {
  Badge, Button, Card, EmptyState, ErrorState, Field, KV, LoadingState, PageHeader, Select, StatTile, StatusPill, Warnings, inputClass,
} from "../components/ui";
import { StrategyChart } from "../charts/StrategyChart";
import { RaceTraceChart } from "../charts/RaceTraceChart";
import { fmtNum, fmtPct, fmtSigned, titleFromId } from "../lib/format";
import type { MeanCI, RaceWeek, StrategyPlan, StrategyResponse } from "../types/api";

const fmtRaceTime = (s: number) => {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s - h * 3600) / 60);
  const sec = s - h * 3600 - m * 60;
  return `${h}:${String(m).padStart(2, "0")}:${sec.toFixed(1).padStart(4, "0")}`;
};
const pctCI = (c?: MeanCI | null) =>
  c && c.estimate !== null ? `${Math.round(c.estimate * 100)}% (${Math.round((c.lo ?? 0) * 100)}–${Math.round((c.hi ?? 0) * 100)}%)` : "—";
const numCI = (c?: MeanCI | null, d = 2) =>
  c && c.estimate !== null ? `${fmtNum(c.estimate, d)} (${fmtNum(c.lo, d)}–${fmtNum(c.hi, d)})` : "—";
const pitText = (p: StrategyPlan) =>
  p.pit_windows.map((w) => `lap ${w.best_lap} (${w.from_lap}–${w.to_lap})`).join(", ");
const weekLabel = (w: RaceWeek) =>
  `R${w.round} · ${w.name.replace(/^Formula 1\s+/, "").replace(/\s+\d{4}$/, "")}${w.status === "upcoming" ? " · upcoming" : w.status === "no_timing_data" ? " · no timing data" : ""}`;

export default function RaceStrategyPage() {
  const [params, setParams] = useSearchParams();
  const weeks = useRaceWeeks();
  const all = weeks.data?.race_weeks ?? [];
  const seasons = useMemo(() => Array.from(new Set(all.map((w) => w.season))).sort((a, b) => b - a), [all]);
  const lastDataSeason = useMemo(() => Math.max(0, ...all.filter((w) => w.status === "past").map((w) => w.season)), [all]);
  const defaultWeek = useMemo(() => all.find((w) => w.status === "upcoming") ?? [...all].reverse().find((w) => w.status === "past"), [all]);

  const [season, setSeason] = useState<number | "">("");
  const [eventId, setEventId] = useState(params.get("event") ?? "");
  const [driver, setDriver] = useState(params.get("driver") ?? "");
  const [car, setCar] = useState("");
  const [grid, setGrid] = useState("");
  const [maxStops, setMaxStops] = useState(3);
  const [windowS, setWindowS] = useState(2);
  const [trackTemp, setTrackTemp] = useState("");
  const [rain, setRain] = useState<"auto" | "dry" | "wet">("auto");
  const plan = useStrategyPlan();

  useEffect(() => {
    if (!all.length) return;
    const ev = all.find((w) => w.event_id === eventId) ?? defaultWeek;
    if (ev) {
      if (!eventId) setEventId(ev.event_id);
      if (season === "") setSeason(ev.season);
    }
  }, [all, defaultWeek, eventId, season]);

  const week = all.find((w) => w.event_id === eventId);
  const driverSeason = week ? (week.status === "past" ? week.season : Math.min(week.season, lastDataSeason)) : undefined;
  const constructors = useConstructors(driverSeason);
  const ready = !!eventId && !!driver && week?.status !== "no_timing_data";

  const run = () => {
    setParams({ event: eventId, driver }, { replace: true });
    plan.mutate({
      event_id: eventId, driver_id: driver, constructor_override: car || null, grid_position: grid ? Number(grid) : null,
      max_stops: maxStops, window_s: windowS, track_temp_c: trackTemp ? Number(trackTemp) : null,
      rain: rain === "auto" ? null : rain === "wet",
    });
  };

  return (
    <div className="space-y-5">
      <PageHeader title="Race week planner"
        description="Pick a race weekend, a driver and — if you like — a different car. ApexLens estimates the weather, the best tyre strategy and pit windows, the lap times and the finishing order. For past races it shows what actually happened next to the plan." />

      <Card title="Race week">
        {weeks.isLoading ? <LoadingState /> : weeks.isError ? <ErrorState error={weeks.error} /> : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-5">
            <Field label="Season">
              <Select ariaLabel="Season" value={season} onChange={(v) => { setSeason(v); setEventId(all.find((w) => w.season === v && w.status !== "no_timing_data")?.event_id ?? ""); }}
                options={seasons.map((s) => ({ value: s, label: String(s) }))} />
            </Field>
            <div className="col-span-2">
              <Field label="Race">
                <Select ariaLabel="Race" value={eventId} onChange={setEventId}
                  options={all.filter((w) => w.season === season).map((w) => ({ value: w.event_id, label: weekLabel(w) }))} />
              </Field>
            </div>
            <DriverSelect season={driverSeason} value={driver} onChange={setDriver} label="Driver" />
            <Field label="Car" hint="Put the driver in another team's car">
              <Select ariaLabel="Car" value={car} onChange={setCar}
                options={[{ value: "", label: "Their own car" },
                  ...(constructors.data ?? []).map((c) => ({ value: c.constructor_id, label: c.name }))]} />
            </Field>
            <Field label="Starting position" hint="Empty = actual / predicted grid">
              <input aria-label="Starting position" className={inputClass} type="number" min={1} max={26} value={grid}
                onChange={(e) => setGrid(e.target.value)} />
            </Field>
            <Field label="Max stops">
              <Select ariaLabel="Max stops" value={maxStops} onChange={setMaxStops}
                options={[1, 2, 3].map((n) => ({ value: n, label: String(n) }))} />
            </Field>
            <Field label="Pit window (s)" hint="Stops within this of the best plan">
              <Select ariaLabel="Pit window" value={windowS} onChange={setWindowS}
                options={[1, 2, 3, 5].map((n) => ({ value: n, label: `${n} s` }))} />
            </Field>
            <Field label="Track temperature °C" hint="Empty = forecast / weekend / history">
              <input aria-label="Track temperature" className={inputClass} type="number" min={-10} max={75} value={trackTemp}
                onChange={(e) => setTrackTemp(e.target.value)} />
            </Field>
            <Field label="Weather">
              <Select ariaLabel="Weather" value={rain} onChange={setRain}
                options={[{ value: "auto", label: "From the data" }, { value: "dry", label: "Assume dry" }, { value: "wet", label: "Assume rain" }]} />
            </Field>
          </div>
        )}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button disabled={!ready || plan.isPending} onClick={run}>{plan.isPending ? "Planning…" : "Plan the race"}</Button>
          {week?.status === "no_timing_data" && <span className="text-xs text-ink-muted">This race has no timing data yet — ingest it first.</span>}
          {week?.status === "upcoming" && <Badge>upcoming: forecast + latest form</Badge>}
          {week?.status === "past" && <Badge>past race: compared with what happened</Badge>}
        </div>
      </Card>

      {plan.isPending && <LoadingState label="Estimating weather, tyre wear, pit loss and pace…" />}
      {plan.isError && <ErrorState error={plan.error} />}
      {plan.data && <PlanView p={plan.data} />}
      {!plan.data && !plan.isPending && !plan.isError && (
        <EmptyState>Choose a race and a driver, then “Plan the race”.</EmptyState>
      )}
    </div>
  );
}

function PlanView({ p }: { p: StrategyResponse }) {
  const best = p.best;
  const w = p.weather.assumed.values;
  const top = p.plans.slice(0, 5);
  return (
    <div className="space-y-5">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatTile label="Best strategy" value={best.label.split(" (")[0]} hint={`${best.stops} stop${best.stops > 1 ? "s" : ""}`} />
        <StatTile label="Pit stop" value={best.pit_laps.map((l) => `L${l}`).join(" · ")}
          hint={`window ${best.pit_windows.map((x) => `${x.from_lap}–${x.to_lap}`).join(", ")}`} />
        <StatTile label="Predicted finish" value={`P${p.prediction.predicted_position}`} hint={`from P${p.prediction.grid} on the grid`} />
        <StatTile label="Expected race time" value={fmtRaceTime(p.expected_race_time_s)} hint="green-flag, no safety car" />
        <StatTile label="Weather" value={`${fmtNum(w.track_temp_c, 0)}°C track`}
          hint={w.wet_race_likely ? `rain likely (${Math.round(w.rain_risk * 100)}%)` : `rain risk ${Math.round(w.rain_risk * 100)}%`} />
      </div>
      <Warnings items={p.warnings} />

      <div className="grid gap-5 xl:grid-cols-3">
        <Card className="xl:col-span-2" title={`Strategy options · ${p.event.circuit_name}, ${p.event.laps} laps`}
          subtitle="Best plan per tyre combination; the faint band is the pit window (stops within your tolerance of that plan's best lap).">
          <StrategyChart laps={p.event.laps} rows={top.map((q) => ({ label: `${q.label}  ${q.delta_s > 0 ? `+${q.delta_s.toFixed(1)} s` : "best"}`,
            sequence: q.sequence, stint_laps: q.stint_laps, windows: q.pit_windows }))} />
          <table className="mt-3 w-full text-sm">
            <thead className="text-left text-xs text-ink-muted"><tr><th>Plan</th><th>Pit laps (window)</th><th className="text-right">vs best</th><th className="text-right">Same tyres, other order</th></tr></thead>
            <tbody>
              {p.plans.map((q) => (
                <tr key={q.label} className="border-t border-line">
                  <td className="py-1">{q.label}</td><td className="tabular">{pitText(q)}</td>
                  <td className="tabular whitespace-nowrap text-right">{q.delta_s === 0 ? "best" : `+${q.delta_s.toFixed(1)} s`}</td>
                  <td className="text-right text-xs text-ink-muted">{q.equivalent_orders.slice(0, 2).join(", ") || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
        <Card title="How sure is the call?" subtitle={`Tyre wear, compound pace and pit loss re-estimated on ${p.robustness.n} resamples of past races`}>
          <ul className="space-y-2">
            {(p.robustness.best_share ?? []).slice(0, 5).map((b) => (
              <li key={b.label}>
                <div className="flex justify-between text-sm"><span>{b.label}</span><span className="tabular">{Math.round(b.share * 100)}%</span></div>
                <div className="mt-1 h-1.5 rounded bg-surface-3"><div className="h-1.5 rounded bg-accent" style={{ width: `${b.share * 100}%` }} /></div>
              </li>
            ))}
          </ul>
          {p.robustness.first_stop_lap && (
            <p className="mt-3 text-xs text-ink-2">First stop across resamples: lap {Math.round(p.robustness.first_stop_lap.p10)}–{Math.round(p.robustness.first_stop_lap.p90)} (median {Math.round(p.robustness.first_stop_lap.median)}).</p>
          )}
          <p className="mt-3 text-xs text-ink-muted">
            Safety car in {Math.round(p.parameters.sc_prob * 100)}% and VSC in {Math.round(p.parameters.vsc_prob * 100)}% of races here (shrunk towards the season-wide rate). A neutralisation inside the window usually makes stopping then the better call.
          </p>
        </Card>
      </div>

      <Card title={`${p.driver.name} · expected lap times`}
        subtitle={p.event.mode === "past" ? "Plan vs the laps actually driven, and the model replaying the strategy the driver actually ran" : "Plan and the best alternative with a different number of stops"}>
        <RaceTraceChart best={p.trace.best} bestLabel={best.label} alternative={p.trace.alternative} alternativeLabel={p.trace.alternative_label}
          actual={p.actual?.laps} replay={p.actual?.replay_trace} />
        <p className="mt-2 text-xs text-ink-muted">
          Pace {fmtPct(p.prediction.base_pct)} vs the session reference ({p.prediction.pace_model}){p.driver.car_override ? ` in the ${titleFromId(p.driver.car_override)} car` : ""}. Reference lap ≈ {fmtNum(p.parameters.ref_lap_s, 1)} s ({p.parameters.ref_source}).
        </p>
      </Card>

      {p.actual && <ActualView p={p} />}

      <div className="grid gap-5 xl:grid-cols-2">
        <Card title="Predicted finishing order" subtitle={`${Math.round(p.prediction.blend_weight * 100)}% grid position, ${Math.round((1 - p.prediction.blend_weight) * 100)}% predicted pace (weight fitted on ${p.prediction.blend_weight_races} earlier races). Grid: ${p.prediction.grid_source}.`}>
          <div className="max-h-96 overflow-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-surface-1 text-left text-xs text-ink-muted"><tr><th>Pred.</th><th>Driver</th><th>Team</th><th className="text-right">Grid</th><th className="text-right">Pace</th>{p.event.mode === "past" && <th className="text-right">Actual</th>}</tr></thead>
              <tbody>
                {p.prediction.field.map((f) => (
                  <tr key={f.driver_id} className={`border-t border-line ${f.driver_id === p.driver.driver_id ? "bg-surface-3" : ""}`}>
                    <td className="tabular py-1">P{f.predicted_position}</td><td>{f.name}</td><td className="text-ink-2">{titleFromId(f.constructor_id)}</td>
                    <td className="tabular text-right">{f.grid}</td><td className="tabular text-right">{fmtPct(f.base_pct)}</td>
                    {p.event.mode === "past" && <td className="tabular text-right">{f.actual_position ? `P${f.actual_position}` : "DNF"}</td>}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-ink-muted">Retirements, penalties and first-lap incidents are not predicted.</p>
        </Card>
        <WeatherView p={p} />
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <BacktestView p={p} />
        <Card title="What the plan is built from" subtitle={`Measured from races before ${p.event.date}`}>
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-ink-muted"><tr><th>Compound</th><th className="text-right">Wear / lap</th><th className="text-right">Pace at 8 laps old</th><th className="text-right">Max stint</th><th className="text-right">Stints here</th></tr></thead>
            <tbody>
              {(["SOFT", "MEDIUM", "HARD"] as const).map((c) => (
                <tr key={c} className="border-t border-line">
                  <td className="py-1">{c}</td><td className="tabular text-right">{fmtSigned(p.parameters.slope_s_per_lap[c], 3, " s")}</td>
                  <td className="tabular text-right">{c === "MEDIUM" ? "reference" : fmtSigned(p.parameters.offset_s[c], 2, " s")}</td>
                  <td className="tabular text-right">{p.parameters.max_stint[c]} laps</td>
                  <td className="tabular text-right">{p.parameters.evidence.degradation[c]?.stints_at_circuit ?? 0}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mt-3">
            <KV rows={[
              ["Pit stop time loss", `${fmtNum(p.parameters.pit_loss_s, 1)} s (${p.parameters.evidence.pit_stops_at_circuit} stops measured here)`],
              ["Earlier races here", `${p.parameters.evidence.races_at_circuit} (of ${p.parameters.evidence.races_total})`],
              ["Hidden cost per stop", p.calibration ? `${fmtNum(p.calibration.stop_s, 1)} s (track position, fitted on ${p.calibration.races} races)` : "not calibrated"],
              ["Hidden cost per SOFT stint", p.calibration ? `${fmtNum(p.calibration.soft_stint_s, 1)} s (set availability, graining)` : "not calibrated"],
            ]} />
          </div>
        </Card>
      </div>

      <Card title="Limitations">
        <ul className="list-disc space-y-1 pl-5 text-sm text-ink-2">{p.limitations.map((l) => <li key={l}>{l}</li>)}</ul>
      </Card>
    </div>
  );
}

function Check({ ok, children }: { ok: boolean | null | undefined; children: React.ReactNode }) {
  if (ok === null || ok === undefined) return <StatusPill status="info">{children}</StatusPill>;
  return <StatusPill status={ok ? "good" : "critical"}>{children}</StatusPill>;
}

function ActualView({ p }: { p: StrategyResponse }) {
  const a = p.actual!;
  const mine = a.driver_strategy;
  const win = a.race.winner;
  const rows = [{ label: "ApexLens plan", sequence: p.best.sequence, stint_laps: p.best.stint_laps, windows: p.best.pit_windows }];
  if (mine) rows.push({ label: `${p.driver.name} (actual)`, sequence: mine.sequence, stint_laps: mine.stint_laps, windows: [] });
  if (win && win.driver_id !== p.driver.driver_id) rows.push({ label: `${titleFromId(win.driver_id)} — winner`, sequence: win.sequence, stint_laps: win.stint_laps, windows: [] });
  const c = a.comparison;
  const flags = [a.race.safety_car && "safety car", a.race.virtual_safety_car && "VSC", a.race.red_flag && "red flag", a.race.wet && "wet"].filter(Boolean);
  return (
    <Card title="What actually happened" subtitle={`Result: ${a.result?.position ? `P${a.result.position}` : a.result?.position_text ?? "—"}${a.result?.grid ? ` from P${a.result.grid}` : ""}${flags.length ? ` · race had: ${flags.join(", ")}` : " · green race"}`}>
      <StrategyChart laps={p.event.laps} rows={rows} />
      <div className="mt-3 flex flex-wrap gap-2">
        <Check ok={c.same_stop_count as boolean}>same number of stops as {p.driver.name.split(" ").slice(-1)[0]}</Check>
        <Check ok={c.same_compounds as boolean}>same tyres</Check>
        <Check ok={c.first_stop_in_window as boolean}>first stop inside the window</Check>
        <Check ok={c.winner_same_stop_count as boolean}>winner's stop count</Check>
        <Check ok={c.matches_most_common_top10_plan as boolean | undefined}>top-10's most common plan</Check>
      </div>
      {(a.race.safety_car || a.race.virtual_safety_car || a.race.red_flag) && (
        <p className="mt-2 text-xs text-ink-muted">Neutralisations change the best call during a race; the plan is made before the start.</p>
      )}
      <div className="mt-3 max-h-64 overflow-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-ink-muted"><tr><th>Pos</th><th>Driver</th><th>Strategy</th><th>Pit laps</th></tr></thead>
          <tbody>
            {a.race.top.map((t) => (
              <tr key={t.driver_id} className="border-t border-line"><td className="tabular py-1">P{t.position}</td><td>{titleFromId(t.driver_id)}</td>
                <td>{t.label}</td><td className="tabular">{t.pit_laps.join(", ")}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function WeatherView({ p }: { p: StrategyResponse }) {
  const wx = p.weather;
  const v = wx.assumed.values;
  return (
    <Card title="Weather" subtitle="What the plan assumes, and where each value comes from">
      <KV rows={[
        ["Track temperature", `${fmtNum(v.track_temp_c, 1)} °C — ${wx.assumed.source.track_temp_c ?? ""}`],
        ["Air temperature", `${fmtNum(v.air_temp_c, 1)} °C — ${wx.assumed.source.air_temp_c ?? ""}`],
        ["Humidity", `${fmtNum(v.humidity_pct, 0)} % — ${wx.assumed.source.humidity_pct ?? ""}`],
        ["Rain risk", `${Math.round(v.rain_risk * 100)} % — ${wx.assumed.source.rain_risk ?? ""}`],
        ...(wx.forecast && !wx.forecast.error ? [["Forecast", `${fmtNum(wx.forecast.air_temp_c, 1)} °C air, ${fmtNum(wx.forecast.rain_probability_pct, 0)} % rain (${wx.forecast.source})`] as [string, string]] : []),
        ...(wx.race_actual?.track_temp_c !== undefined ? [["Actual race", `${fmtNum(wx.race_actual.track_temp_c, 1)} °C track, ${fmtNum(wx.race_actual.air_temp_c, 1)} °C air${(wx.race_actual.rain_share ?? 0) > 0.05 ? ", rain" : ""}`] as [string, string]] : []),
        ["At this circuit before", wx.circuit_history.races ? `${wx.circuit_history.races} races, track ${fmtNum(wx.circuit_history.track_temp_range_c?.[0], 0)}–${fmtNum(wx.circuit_history.track_temp_range_c?.[1], 0)} °C, rain in ${Math.round((wx.circuit_history.rain_race_share ?? 0) * 100)}%` : "no earlier races"],
      ]} />
      {wx.weekend_sessions.length > 0 && (
        <table className="mt-3 w-full text-sm">
          <thead className="text-left text-xs text-ink-muted"><tr><th>Session</th><th className="text-right">Track</th><th className="text-right">Air</th><th className="text-right">Humidity</th><th className="text-right">Rain</th></tr></thead>
          <tbody>
            {wx.weekend_sessions.map((s) => (
              <tr key={s.session_id} className="border-t border-line"><td className="py-1">{s.session_code}</td>
                <td className="tabular text-right">{s.track_temp_c !== undefined ? `${fmtNum(s.track_temp_c, 1)} °C` : "—"}</td>
                <td className="tabular text-right">{s.air_temp_c !== undefined ? `${fmtNum(s.air_temp_c, 1)} °C` : "—"}</td>
                <td className="tabular text-right">{s.humidity_pct !== undefined ? `${fmtNum(s.humidity_pct, 0)} %` : "—"}</td>
                <td className="tabular text-right">{s.rain_share !== undefined ? `${Math.round(s.rain_share * 100)} %` : "—"}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="mt-2 text-xs text-ink-muted">Temperature is shown but does not change tyre wear in the plan: adjusting for it made held-out predictions worse.</p>
    </Card>
  );
}

function BacktestView({ p }: { p: StrategyResponse }) {
  const b = p.backtest;
  if (!b) return <Card title="Track record"><EmptyState>Backtest not run yet (scripts/evaluate_models.py --only strategy).</EmptyState></Card>;
  const fo = b.finishing_order;
  return (
    <Card title="Track record on past races" subtitle={`Every race since the second season planned with only earlier data, then compared with what the top-10 did (${b.strategy_races} dry races; 95% intervals)`}>
      <table className="w-full text-sm">
        <thead className="text-left text-xs text-ink-muted"><tr><th>Matches reality</th><th className="text-right">Planner</th><th className="text-right">Copy last year</th></tr></thead>
        <tbody>
          <tr className="border-t border-line"><td className="py-1">Number of stops</td><td className="tabular text-right">{pctCI(b.stops_match)}</td><td className="tabular text-right">{pctCI(b.previous_edition.stops_match)}</td></tr>
          <tr className="border-t border-line"><td className="py-1">Stops + tyre set</td><td className="tabular text-right">{pctCI(b.plan_match)}</td><td className="tabular text-right">{pctCI(b.previous_edition.plan_match)}</td></tr>
          <tr className="border-t border-line"><td className="py-1">Starting tyre</td><td className="tabular text-right">{pctCI(b.start_match)}</td><td className="tabular text-right">{pctCI(b.previous_edition.start_match)}</td></tr>
          <tr className="border-t border-line"><td className="py-1">First stops inside the window</td><td className="tabular text-right">{pctCI(b.window_hit)}</td><td className="tabular text-right">—</td></tr>
        </tbody>
      </table>
      <table className="mt-3 w-full text-sm">
        <thead className="text-left text-xs text-ink-muted"><tr><th>Finishing order ({b.races} races)</th><th className="text-right">Planner</th><th className="text-right">Grid order</th></tr></thead>
        <tbody>
          <tr className="border-t border-line"><td className="py-1">Rank correlation</td><td className="tabular text-right">{numCI(fo.blend?.spearman)}</td><td className="tabular text-right">{numCI(fo.grid_order?.spearman)}</td></tr>
          <tr className="border-t border-line"><td className="py-1">Winner correct</td><td className="tabular text-right">{pctCI(fo.blend?.winner_correct)}</td><td className="tabular text-right">{pctCI(fo.grid_order?.winner_correct)}</td></tr>
          <tr className="border-t border-line"><td className="py-1">Podium overlap</td><td className="tabular text-right">{pctCI(fo.blend?.podium_overlap)}</td><td className="tabular text-right">{pctCI(fo.grid_order?.podium_overlap)}</td></tr>
        </tbody>
      </table>
      {b.lap_replay.model_mae_s && (
        <p className="mt-3 text-xs text-ink-2">Lap times when replaying the top-10's actual strategies: {numCI(b.lap_replay.model_mae_s)} s mean error per lap vs {numCI(b.lap_replay.constant_pace_mae_s)} s for a constant-pace guess.</p>
      )}
      <p className="mt-2 text-xs text-ink-muted">Copying last year's race at the same circuit is a strong baseline; the planner also works for new circuits and gives timing windows.</p>
    </Card>
  );
}
