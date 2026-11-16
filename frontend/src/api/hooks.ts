import { useMutation, useQuery } from "@tanstack/react-query";
import { getJson, postJson, qs } from "./client";
import type {
  Circuit,
  DriverCompare,
  DriverProfile,
  SeasonEffects,
  ComparisonPrediction,
  Constructor,
  DriverIndexItem,
  DriverPerformance,
  EventItem,
  LapPrediction,
  LapScenario,
  ModelListItem,
  Overview,
  Page,
  ScenarioResult,
  Season,
  SessionItem,
  SessionLaps,
  RaceWeek,
  StrategyRequest,
  StrategyResponse,
  GameEventDetail,
  GameEventSummary,
  GameLeaderboard,
  GameRules,
} from "../types/api";

const STALE = 5 * 60 * 1000;

export const useOverview = () => useQuery({ queryKey: ["overview"], queryFn: () => getJson<Overview>("/overview"), staleTime: STALE });
export const useSeasons = () => useQuery({ queryKey: ["seasons"], queryFn: () => getJson<Season[]>("/seasons"), staleTime: STALE });
export const useEvents = (season?: number) =>
  useQuery({ queryKey: ["events", season], queryFn: () => getJson<EventItem[]>(`/events${qs({ season })}`), staleTime: STALE });
export const useCircuits = () => useQuery({ queryKey: ["circuits"], queryFn: () => getJson<Circuit[]>("/circuits"), staleTime: STALE });
export const useConstructors = (season?: number) =>
  useQuery({ queryKey: ["constructors", season], queryFn: () => getJson<Constructor[]>(`/constructors${qs({ season })}`), staleTime: STALE });

export const useDrivers = (p: { season?: number; constructor_id?: string; q?: string; scope?: "lap" | "all"; limit?: number; offset?: number }) =>
  useQuery({
    queryKey: ["drivers", p],
    queryFn: () => getJson<Page<DriverIndexItem>>(`/drivers${qs({ limit: 200, ...p })}`),
    staleTime: STALE,
    placeholderData: (prev) => prev,
  });

export const useSessions = (event_id?: string) =>
  useQuery({
    queryKey: ["sessions", event_id],
    queryFn: () => getJson<SessionItem[]>(`/sessions${qs({ event_id })}`),
    enabled: !!event_id,
    staleTime: STALE,
  });

export const useSessionLaps = (session_id?: string) =>
  useQuery({
    queryKey: ["laps", session_id],
    queryFn: () => getJson<SessionLaps>(`/sessions/${session_id}/laps`),
    enabled: !!session_id,
    staleTime: STALE,
  });

export const useDriverPerformance = (driver_id?: string, season?: number) =>
  useQuery({
    queryKey: ["driver-performance", driver_id, season],
    queryFn: () => getJson<DriverPerformance>(`/drivers/${driver_id}/performance${qs({ season })}`),
    enabled: !!driver_id,
    staleTime: STALE,
  });

export const useModels = () =>
  useQuery({
    queryKey: ["models"],
    queryFn: () => getJson<{ production: Record<string, string>; models: ModelListItem[] }>("/models"),
    staleTime: STALE,
  });

export const useLapPrediction = () => useMutation({ mutationFn: (s: LapScenario) => postJson<LapPrediction>("/predict/lap-time", s) });
export const useComparison = () =>
  useMutation({
    mutationFn: (s: Omit<LapScenario, "driver_id"> & { driver_ids: string[]; common_car: boolean }) =>
      postJson<ComparisonPrediction>("/predict/driver-comparison", s),
  });
export const useScenario = () => useMutation({ mutationFn: (s: LapScenario) => postJson<ScenarioResult>("/scenarios", s) });

export function useJson<T>(key: unknown[], path: string | null) {
  return useQuery({ queryKey: key, queryFn: () => getJson<T>(path as string), enabled: !!path, staleTime: STALE });
}

export const useDriverProfile = (driver_id?: string) =>
  useQuery({
    queryKey: ["driver-profile", driver_id],
    queryFn: () => getJson<DriverProfile>(`/drivers/${driver_id}/profile`),
    enabled: !!driver_id,
    staleTime: STALE,
    retry: false,
  });

export const useSeasonEffects = (season?: number) =>
  useQuery({
    queryKey: ["driver-effects", season],
    queryFn: () => getJson<SeasonEffects>(`/driver-effects${qs({ season })}`),
    enabled: !!season,
    staleTime: STALE,
  });

export const useDriverCompare = (a?: string, b?: string, season?: number) =>
  useQuery({
    queryKey: ["driver-compare", a, b, season],
    queryFn: () => getJson<DriverCompare>(`/drivers/compare${qs({ ids: `${a},${b}`, season })}`),
    enabled: !!a && !!b && a !== b,
    staleTime: STALE,
  });

/** Display name lookup for constructors (falls back to a title-cased id). */
export function useConstructorName() {
  const q = useQuery({ queryKey: ["constructors", "all"], queryFn: () => getJson<Constructor[]>("/constructors"), staleTime: Infinity });
  const map = new Map((q.data ?? []).map((c) => [c.constructor_id, c.name]));
  return (id?: string | null) => (id ? map.get(id) ?? id.split("-").map((w) => w[0].toUpperCase() + w.slice(1)).join(" ") : "—");
}

export const useRaceWeeks = () =>
  useQuery({ queryKey: ["race-weeks"], queryFn: () => getJson<{ race_weeks: RaceWeek[] }>("/strategy/race-weeks"), staleTime: STALE });
export const useStrategyPlan = () =>
  useMutation({ mutationFn: (r: StrategyRequest) => postJson<StrategyResponse>("/strategy/plan", r) });

// -- prediction game ---------------------------------------------------------------------------
export const useGameRules = () => useQuery({ queryKey: ["game-rules"], queryFn: () => getJson<GameRules>("/game/rules"), staleTime: Infinity });
export const useGameEvents = () =>
  useQuery({ queryKey: ["game-events"], queryFn: () => getJson<{ events: GameEventSummary[] }>("/game/events"), staleTime: 60 * 1000 });
/** The race's game state; refetches while the AI entrant is still thinking. */
export const useGameEvent = (event_id?: string, player?: string, enabled = true) =>
  useQuery({
    queryKey: ["game-event", event_id, player],
    queryFn: () => getJson<GameEventDetail>(`/game/events/${event_id}${qs({ player })}`),
    enabled: enabled && !!event_id,
    staleTime: 10 * 1000,
    retry: false,
    refetchInterval: (q) => (q.state.data?.ai_pending ? 3000 : false),
    // typing your name re-keys the query; keep the same race on screen meanwhile so the picks form is not reset
    placeholderData: (prev) => (prev && prev.event.event_id === event_id ? prev : undefined),
  });
export const useSubmitPrediction = (event_id: string) =>
  useMutation({ mutationFn: (r: { player: string; picks: string[] }) => postJson<GameEventDetail>(`/game/events/${event_id}/predictions`, r) });
export const useSettleRace = (event_id: string) =>
  useMutation({
    mutationFn: ({ token, ...r }: { fetch: boolean; laps?: boolean; token?: string }) =>
      postJson<GameEventDetail>(`/game/events/${event_id}/settle`, r, token ? { "X-Admin-Token": token } : {}),
  });
export const useGameLeaderboard = (season?: number) =>
  useQuery({ queryKey: ["game-leaderboard", season], queryFn: () => getJson<GameLeaderboard>(`/game/leaderboard${qs({ season })}`), staleTime: 60 * 1000 });
