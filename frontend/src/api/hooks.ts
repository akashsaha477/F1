import { useMutation, useQuery } from "@tanstack/react-query";
import { getJson, postJson, qs } from "./client";
import type {
  Circuit,
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
