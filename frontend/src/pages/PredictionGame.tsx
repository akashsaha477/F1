import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { useGameEvent, useGameEvents, useGameLeaderboard, useGameRules, useSettleRace, useSubmitPrediction } from "../api/hooks";
import { Badge, Button, Card, EmptyState, ErrorState, Field, LoadingState, PageHeader, Select, StatTile, StatusPill, Warnings, inputClass } from "../components/ui";
import { titleFromId } from "../lib/format";
import type { GameEntry, GameEventDetail, GameEventSummary } from "../types/api";

const N = 10;
const NAME_KEY = "apexlens.game.player";
const ADMIN_KEY = "apexlens.game.admin";
const load = (k: string) => { try { return localStorage.getItem(k) ?? ""; } catch { return ""; } };
const save = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* private window */ } };
const loadName = () => load(NAME_KEY);
const saveName = (n: string) => save(NAME_KEY, n);

const raceName = (w: { name: string }) => w.name.replace(/^Formula 1\s+/, "").replace(/\s+\d{4}$/, "");
const raceLabel = (w: GameEventSummary) =>
  `R${w.round} · ${raceName(w)}${w.game_status === "open" ? " · open" : w.game_status === "locked" ? " · awaiting result" : w.game_status === "settled" ? " · scored" : ""}`;
const fmtWhen = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZoneName: "short" });
const lastName = (name: string) => name.split(" ").slice(-1)[0];
const KIND_LABEL: Record<GameEntry["kind"], string> = { player: "player", model: "model", ai: "AI" };

export default function PredictionGamePage() {
  const [params, setParams] = useSearchParams();
  const qc = useQueryClient();
  const events = useGameEvents();
  const all = events.data?.events ?? [];
  const seasons = useMemo(() => Array.from(new Set(all.map((w) => w.season))).sort((a, b) => b - a), [all]);
  const defaultEvent = useMemo(
    () => all.find((w) => w.game_status === "open") ?? [...all].reverse().find((w) => w.game_status !== "unavailable") ?? all.at(-1),
    [all],
  );
  const [season, setSeason] = useState<number | "">("");
  const [eventId, setEventId] = useState(params.get("event") ?? "");
  const [name, setName] = useState(loadName);

  useEffect(() => {
    if (!all.length) return;
    const ev = all.find((w) => w.event_id === eventId) ?? defaultEvent;
    if (ev) {
      if (!eventId) setEventId(ev.event_id);
      if (season === "") setSeason(ev.season);
    }
  }, [all, defaultEvent, eventId, season]);

  const week = all.find((w) => w.event_id === eventId);
  const playable = !!week && week.game_status !== "unavailable";
  const detail = useGameEvent(eventId, name.trim() || undefined, playable);
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["game-events"] });
    qc.invalidateQueries({ queryKey: ["game-event"] });
    qc.invalidateQueries({ queryKey: ["game-leaderboard"] });
  };
  const pick = (id: string) => { setEventId(id); setParams({ event: id }, { replace: true }); };
  const ai = useGameRules().data?.ai_enabled ?? false;

  return (
    <div className="space-y-5">
      <PageHeader title="Prediction game"
        description={ai
          ? "Call the top ten before the race. Once you have submitted, you see what the ApexLens model and the AI predicted; after the weekend the real result scores everyone and the season leaderboard keeps count — you, your friends, the model and the AI."
          : "Call the top ten before the race. Once you have submitted, you see what the ApexLens model predicted; after the weekend the real result scores everyone and the season leaderboard keeps count — you, your friends and the model."} />

      <Card title="Race">
        {events.isLoading ? <LoadingState /> : events.isError ? <ErrorState error={events.error} onRetry={() => events.refetch()} /> : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Field label="Season">
              <Select ariaLabel="Season" value={season} onChange={(v) => { setSeason(v); const first = all.find((w) => w.season === v && w.game_status === "open") ?? all.find((w) => w.season === v); if (first) pick(first.event_id); }}
                options={seasons.map((s) => ({ value: s, label: String(s) }))} />
            </Field>
            <div className="col-span-2">
              <Field label="Race">
                <Select ariaLabel="Race" value={eventId} onChange={pick}
                  options={all.filter((w) => w.season === season).map((w) => ({ value: w.event_id, label: raceLabel(w) }))} />
              </Field>
            </div>
            <Field label="Your name" hint="Use the same name to update your picks">
              <input aria-label="Your name" className={inputClass} maxLength={40} value={name} placeholder="e.g. Akash"
                onChange={(e) => { setName(e.target.value); saveName(e.target.value); }} />
            </Field>
          </div>
        )}
        {week && (
          <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
            <StatusBadge status={week.game_status} />
            <span className="text-ink-2">
              {week.game_status === "open" ? `Predictions close ${fmtWhen(week.deadline_utc)}` : week.game_status === "locked"
                ? `Closed ${fmtWhen(week.deadline_utc)} — waiting for the result` : week.game_status === "settled" ? "Scored"
                : "Not available: this race already has its results, or it started before anyone predicted it."}
            </span>
            {week.players > 0 && <Badge>{week.players} player{week.players > 1 ? "s" : ""}</Badge>}
          </div>
        )}
      </Card>

      {playable && detail.isLoading && <LoadingState label="Opening the race (the model's order is frozen now)…" />}
      {playable && detail.isError && <ErrorState error={detail.error} onRetry={() => detail.refetch()} />}
      {playable && detail.data && (
        <RaceView key={detail.data.event.event_id} d={detail.data} name={name} ai={ai} onChanged={refresh} />
      )}
      {!playable && !events.isLoading && week && <EmptyState>Pick a race that is open for predictions or already scored.</EmptyState>}

      <div className="grid gap-5 xl:grid-cols-3">
        <LeaderboardCard season={season === "" ? undefined : season} />
        <RulesCard />
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: GameEventSummary["game_status"] }) {
  if (status === "open") return <StatusPill status="good">open for predictions</StatusPill>;
  if (status === "locked") return <StatusPill status="warning">locked</StatusPill>;
  if (status === "settled") return <StatusPill status="info">settled</StatusPill>;
  return <StatusPill status="critical">unavailable</StatusPill>;
}

function RaceView({ d, name, ai, onChanged }: { d: GameEventDetail; name: string; ai: boolean; onChanged: () => void }) {
  const you = d.entries.find((e) => e.key === d.you);
  const settled = d.status === "settled";
  return (
    <div className="space-y-5">
      {settled && <ResultTiles d={d} you={you} />}
      {d.status === "open" && <PicksForm d={d} name={name} existing={you} onChanged={onChanged} />}
      {d.status === "locked" && <SettleCard d={d} onChanged={onChanged} />}
      {d.revealed ? <PredictionsTable d={d} ai={ai} /> : (
        <Card title="Predictions" subtitle={`${ai ? "The model's and the AI's calls are" : "The model's call is"} shown once you have submitted yours; everyone's picks become public when the race starts.`}>
          <HiddenEntrants entries={d.entries} />
        </Card>
      )}
      {d.model_warnings.length > 0 && <Warnings items={d.model_warnings} />}
    </div>
  );
}

function HiddenEntrants({ entries }: { entries: GameEntry[] }) {
  const names = entries.map((e) => `${e.name}${e.kind !== "player" ? ` (${KIND_LABEL[e.kind]})` : ""}`);
  return <p className="text-sm text-ink-2">Already in: {names.join(", ")}.</p>;
}

function PicksForm({ d, name, existing, onChanged }: { d: GameEventDetail; name: string; existing?: GameEntry; onChanged: () => void }) {
  const [picks, setPicks] = useState<string[]>(() => existing?.picks ?? Array(N).fill(""));
  useEffect(() => { if (existing?.picks) setPicks(existing.picks); }, [existing?.picks]);
  const submit = useSubmitPrediction(d.event.event_id);
  const complete = picks.every(Boolean) && new Set(picks).size === N;
  const ready = complete && name.trim().length > 0;
  const byId = new Map(d.field.map((f) => [f.driver_id, f]));
  const send = () => submit.mutate({ player: name.trim(), picks }, { onSuccess: onChanged });
  return (
    <Card title={existing ? "Your top ten (submitted — change it until the start)" : "Your top ten"}
      subtitle={`${d.field.length} drivers in the field. P1 is the winner.`}>
      <div className="grid grid-cols-2 gap-2 md:grid-cols-5">
        {picks.map((p, i) => (
          <Field key={i} label={`P${i + 1}`}>
            <Select ariaLabel={`P${i + 1}`} value={p} onChange={(v) => setPicks(picks.map((x, j) => (j === i ? v : x)))}
              options={[{ value: "", label: "—" }, ...d.field.filter((f) => f.driver_id === p || !picks.includes(f.driver_id))
                .map((f) => ({ value: f.driver_id, label: `${f.name} · ${titleFromId(f.constructor_id)}` }))]} />
          </Field>
        ))}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <Button disabled={!ready || submit.isPending} onClick={send}>{submit.isPending ? "Submitting…" : existing ? "Update prediction" : "Submit prediction"}</Button>
        <Button variant="ghost" onClick={() => setPicks(Array(N).fill(""))}>Clear</Button>
        {!name.trim() && <span className="text-xs text-ink-muted">Enter your name above.</span>}
        {name.trim() && !complete && <span className="text-xs text-ink-muted">Pick ten different drivers.</span>}
        {existing?.submitted_at && <span className="text-xs text-ink-muted">Submitted {fmtWhen(existing.submitted_at)}</span>}
      </div>
      {submit.isError && <div className="mt-3"><ErrorState error={submit.error} /></div>}
      {picks.some(Boolean) && (
        <p className="mt-2 text-xs text-ink-muted">{picks.map((p, i) => (p ? `P${i + 1} ${lastName(byId.get(p)?.name ?? p)}` : null)).filter(Boolean).join(" · ")}</p>
      )}
    </Card>
  );
}

const OUTCOME_CLASS: Record<string, string> = { exact: "text-good", "one off": "text-good", "two off": "text-warn", "in top ten": "text-ink-2" };

function PredictionsTable({ d, ai }: { d: GameEventDetail; ai: boolean }) {
  const byId = new Map(d.field.map((f) => [f.driver_id, f]));
  const shown = d.entries.filter((e) => e.picks && e.picks.length);
  const hidden = d.entries.filter((e) => !e.picks || !e.picks.length);
  const actual = new Map((d.result?.classified ?? []).map((c) => [c.position, c]));
  const scoreAt = (e: GameEntry, i: number) => e.score?.picks.find((p) => p.position === i + 1);
  return (
    <Card title="Predictions" subtitle={d.status === "settled" ? "Points per pick: 10 exact · 6 one off · 3 two off · 1 anywhere in the top ten."
      : ai && d.entries.some((e) => e.kind === "ai") ? "Everyone's calls side by side. The AI only saw the line-up, recent results and last year's race — not the model's order."
        : "Everyone's calls side by side."}>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-ink-muted">
            <tr>
              <th className="py-1 pr-2">Pos</th>
              {d.status === "settled" && <th className="pr-3">Result</th>}
              {shown.map((e) => (
                <th key={e.key} className="pr-3 font-medium">
                  <span className={e.key === d.you ? "text-ink" : ""}>{e.key === d.you ? "You" : e.name}</span>
                  {e.kind !== "player" && <span className="ml-1 text-[10px] uppercase tracking-wider text-ink-muted">{KIND_LABEL[e.kind]}</span>}
                  {e.score && <span className="tabular ml-1 text-ink">{e.score.points} pts</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: N }, (_, i) => (
              <tr key={i} className="border-t border-line">
                <td className="tabular py-1 pr-2 text-ink-muted">P{i + 1}</td>
                {d.status === "settled" && <td className="pr-3">{actual.get(i + 1) ? lastName(actual.get(i + 1)!.name) : "—"}</td>}
                {shown.map((e) => {
                  const id = e.picks![i];
                  const s = scoreAt(e, i);
                  return (
                    <td key={e.key} className="whitespace-nowrap pr-3">
                      {lastName(byId.get(id)?.name ?? titleFromId(id))}
                      {s && <span className={`tabular ml-1 text-xs ${OUTCOME_CLASS[s.outcome] ?? "text-ink-muted"}`} title={s.outcome}>{s.points > 0 ? `+${s.points}` : "0"}</span>}
                    </td>
                  );
                })}
              </tr>
            ))}
            {d.status === "settled" && (
              <tr className="border-t border-line text-xs text-ink-muted">
                <td className="py-1 pr-2">Bonus</td><td />
                {shown.map((e) => <td key={e.key} className="pr-3">{e.score?.bonuses.map((b) => `${b.name} +${b.points}`).join(", ") || "—"}</td>)}
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="mt-3 space-y-1 text-xs text-ink-muted">
        {shown.filter((e) => e.kind !== "player").map((e) => (
          <p key={e.key}><span className="text-ink-2">{e.name}:</span> {e.note}{e.rationale ? ` — “${e.rationale}”` : ""}</p>
        ))}
        {hidden.map((e) => (
          <p key={e.key}><span className="text-ink-2">{e.name}:</span>{" "}
            {e.status === "pending" ? "thinking…" : "picks hidden until the race starts"}
          </p>
        ))}
        {d.result && d.result.not_classified.length > 0 && (
          <p>Not classified: {d.result.not_classified.map((id) => lastName(byId.get(id)?.name ?? titleFromId(id))).join(", ")}.</p>
        )}
      </div>
    </Card>
  );
}

function SettleCard({ d, onChanged }: { d: GameEventDetail; onChanged: () => void }) {
  const settle = useSettleRace(d.event.event_id);
  const rules = useGameRules();
  const protectedSettle = rules.data?.settle_protected ?? false;
  const [token, setToken] = useState(() => load(ADMIN_KEY));
  const run = (fetch: boolean) => settle.mutate({ fetch, token: token.trim() || undefined }, { onSuccess: onChanged });
  const blocked = protectedSettle && !token.trim();
  return (
    <Card title="After the race" subtitle="Fetch the classified result from F1DB (usually published within a day or two of the race) and score every entrant.">
      <div className="flex flex-wrap items-end gap-3">
        {protectedSettle && (
          <Field label="Admin token" hint="This server only lets its admin fetch results">
            <input aria-label="Admin token" type="password" className={inputClass} value={token} autoComplete="off"
              onChange={(e) => { setToken(e.target.value); save(ADMIN_KEY, e.target.value); }} />
          </Field>
        )}
        <Button disabled={settle.isPending || blocked} onClick={() => run(true)}>{settle.isPending ? "Fetching…" : "Fetch results & score"}</Button>
        <Button variant="ghost" disabled={settle.isPending || blocked} onClick={() => run(false)}>Score from stored data</Button>
        {settle.isPending && <span className="text-xs text-ink-muted">Pulling F1DB and re-ingesting the season's results; this can take a minute.</span>}
      </div>
      {settle.isError && <div className="mt-3"><ErrorState error={settle.error} /></div>}
    </Card>
  );
}

function ResultTiles({ d, you }: { d: GameEventDetail; you?: GameEntry }) {
  const winner = d.result?.classified[0];
  const model = d.entries.find((e) => e.kind === "model");
  const ai = d.entries.find((e) => e.kind === "ai");
  const top = d.standings?.[0];
  return (
    <div className={`grid grid-cols-2 gap-3 ${ai ? "md:grid-cols-5" : "md:grid-cols-4"}`}>
      <StatTile label="Winner" value={winner ? lastName(winner.name) : "—"} hint={winner ? titleFromId(winner.constructor_id) : undefined} />
      <StatTile label="Top scorer" value={top ? `${top.points} pts` : "—"} hint={top?.name} />
      <StatTile label="You" value={you?.score ? `${you.score.points} pts` : "—"} hint={you?.score ? `${you.score.exact} exact` : "no entry"} />
      <StatTile label="ApexLens model" value={model?.score ? `${model.score.points} pts` : "—"} hint={model?.score ? `${model.score.exact} exact` : undefined} />
      {ai && <StatTile label="Claude (AI)" value={ai.score ? `${ai.score.points} pts` : "—"} hint={ai.score ? `${ai.score.exact} exact` : undefined} />}
    </div>
  );
}

function LeaderboardCard({ season }: { season?: number }) {
  const lb = useGameLeaderboard(season);
  return (
    <Card className="xl:col-span-2" title={`Leaderboard${season ? ` · ${season}` : ""}`}
      subtitle={lb.data ? `${lb.data.races.length} race${lb.data.races.length === 1 ? "" : "s"} scored` : undefined}>
      {lb.isLoading && <LoadingState />}
      {lb.isError && <ErrorState error={lb.error} />}
      {lb.data && lb.data.rows.length === 0 && <EmptyState>No race scored yet. Predict the next one, then settle it after the weekend.</EmptyState>}
      {lb.data && lb.data.rows.length > 0 && (
        <table className="w-full text-sm">
          <thead className="text-left text-xs text-ink-muted"><tr><th className="py-1">#</th><th>Entrant</th><th className="text-right">Points</th><th className="text-right">Races</th><th className="text-right">Avg</th><th className="text-right">Exact</th><th className="text-right">Podiums</th><th className="text-right">Race wins</th><th className="text-right">Best</th></tr></thead>
          <tbody>
            {lb.data.rows.map((r) => (
              <tr key={r.key} className="border-t border-line">
                <td className="tabular py-1">{r.rank}</td>
                <td>{r.name}{r.kind !== "player" && <span className="ml-1 text-[10px] uppercase tracking-wider text-ink-muted">{KIND_LABEL[r.kind]}</span>}</td>
                <td className="tabular text-right font-medium">{r.points}</td><td className="tabular text-right">{r.races}</td>
                <td className="tabular text-right">{r.average}</td><td className="tabular text-right">{r.exact}</td>
                <td className="tabular text-right">{r.podiums}</td><td className="tabular text-right">{r.race_wins}</td>
                <td className="tabular text-right">{r.best_race}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

function RulesCard() {
  const rules = useGameRules();
  if (!rules.data) return <Card title="How scoring works">{rules.isLoading ? <LoadingState /> : <ErrorState error={rules.error} />}</Card>;
  const r = rules.data;
  return (
    <Card title="How scoring works" subtitle={`Up to ${r.max_points} points per race`}>
      <ul className="space-y-1 text-sm text-ink-2">
        {r.per_pick.map((p) => <li key={p.outcome} className="flex justify-between gap-2"><span>{p.condition}</span><span className="tabular text-ink">{p.points}</span></li>)}
        {r.bonuses.map((b) => <li key={b.name} className="flex justify-between gap-2"><span>{b.condition}</span><span className="tabular text-ink">+{b.points}</span></li>)}
      </ul>
      <p className="mt-3 text-xs text-ink-muted">{r.deadline} {r.result}</p>
      <p className="mt-1 text-xs text-ink-muted">{r.bots}</p>
    </Card>
  );
}
