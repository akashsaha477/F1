"""Tables used by the race strategy planner, loaded once and shared by the planner and the backtest."""

from __future__ import annotations

from functools import cached_property

import numpy as np
import pandas as pd

from apexlens.storage.io import read_table
from apexlens.storage.paths import DataPaths

DRY = ("SOFT", "MEDIUM", "HARD")
WET = ("INTERMEDIATE", "WET")
LAP_COLS = ["session_id", "event_id", "season", "session_code", "circuit_id", "driver_id", "constructor_id", "lap_number",
            "lap_time_s", "exclusion_reason", "is_clean", "is_representative", "drv_session_median_s", "compound",
            "tyre_life_laps", "stint", "track_status", "session_ref_s", "rel_pace_pct", "condition"]


class StrategyData:
    def __init__(self, paths: DataPaths):
        self.paths = paths

    @cached_property
    def events(self) -> pd.DataFrame:
        e = read_table(self.paths.silver("events"))
        e["date"] = pd.to_datetime(e["date"])
        return e.set_index("event_id", drop=False)

    @cached_property
    def sessions(self) -> pd.DataFrame:
        s = read_table(self.paths.silver("sessions"))
        s["start"] = pd.to_datetime(s["start_utc"], utc=True, errors="coerce", format="ISO8601")
        return s

    @cached_property
    def circuits(self) -> pd.DataFrame:
        return read_table(self.paths.silver("circuits")).set_index("circuit_id")

    @cached_property
    def laps(self) -> pd.DataFrame:
        """Race and sprint laps (all of them, with exclusion reasons)."""
        lap = read_table(self.paths.gold("all_laps_relative"), columns=LAP_COLS)
        lap = lap[lap["session_code"].isin(["R", "S"])].copy()
        lap["date"] = lap["event_id"].map(self.events["date"])
        return lap.sort_values(["session_id", "driver_id", "lap_number"]).reset_index(drop=True)

    @cached_property
    def quali_refs(self) -> pd.Series:
        q = read_table(self.paths.gold("all_laps_relative"), columns=["event_id", "session_code", "session_ref_s"])
        return q[q["session_code"] == "Q"].groupby("event_id")["session_ref_s"].first()

    @cached_property
    def stint_slopes(self) -> pd.DataFrame:
        """Per-stint fuel-corrected degradation slopes and levels (Model C)."""
        st = read_table(self.paths.gold("tyre_stints"))
        st["date"] = pd.to_datetime(st["date"])
        return st[st["compound"].isin(DRY)].reset_index(drop=True)

    @cached_property
    def stints(self) -> pd.DataFrame:
        """Actual race stints (every lap, not only representative ones)."""
        s = read_table(self.paths.silver("stints"))
        s = s[s["session_code"] == "R"].copy()
        s["date"] = s["event_id"].map(self.events["date"])
        s["circuit_id"] = s["event_id"].map(self.events["circuit_id"])
        return s.sort_values(["session_id", "driver_id", "stint"]).reset_index(drop=True)

    @cached_property
    def results(self) -> pd.DataFrame:
        r = read_table(self.paths.silver("race_results"))
        return r[r["session_code"] == "R"].copy()

    @cached_property
    def weather(self) -> pd.DataFrame:
        return read_table(self.paths.silver("weather_observations"))

    @cached_property
    def fuel_slopes(self) -> pd.Series:
        adj = read_table(self.paths.gold("driver_session_adjusted"))
        return adj.groupby("session_id")["fuel_slope_pct_per_lap"].first()

    @cached_property
    def races(self) -> pd.DataFrame:
        """One row per race with lap timing: conditions and disruptions."""
        lap = self.laps[self.laps["session_code"] == "R"]
        ts = lap["track_status"].fillna("").astype(str).str.replace(".0", "", regex=False)
        flags = pd.DataFrame({"session_id": lap["session_id"], "sc": ts.str.contains("4"), "red": ts.str.contains("5"),
                              "vsc": ts.str.contains("6") | ts.str.contains("7"),
                              "wet_lap": lap["compound"].isin(WET)})
        agg = flags.groupby("session_id").agg(sc=("sc", "any"), vsc=("vsc", "any"), red=("red", "any"),
                                              wet_share=("wet_lap", "mean"))
        base = lap.groupby("session_id").agg(event_id=("event_id", "first"), season=("season", "first"),
                                             circuit_id=("circuit_id", "first"), ref_s=("session_ref_s", "first"),
                                             laps_run=("lap_number", "max"))
        out = base.join(agg).reset_index()
        out["date"] = out["event_id"].map(self.events["date"])
        out["scheduled_laps"] = out["event_id"].map(self.events["laps"]).fillna(out["laps_run"]).astype(int)
        out["q_ref_s"] = out["event_id"].map(self.quali_refs)
        out["fuel_slope"] = out["session_id"].map(self.fuel_slopes)
        out["wet"] = out["wet_share"] > 0.05
        return out.sort_values("date").reset_index(drop=True)

    @cached_property
    def pit_stops(self) -> pd.DataFrame:
        """Green-flag dry pit stops: time lost = in-lap + out-lap - 2 x the driver's median clean lap."""
        lap = self.laps[self.laps["session_code"] == "R"]
        nxt = lap.groupby(["session_id", "driver_id"]).shift(-1)
        m = ((lap["exclusion_reason"] == "pit_in_lap") & (nxt["exclusion_reason"] == "pit_out_lap")
             & (nxt["lap_number"] == lap["lap_number"] + 1) & lap["compound"].isin(DRY) & nxt["compound"].isin(DRY))
        loss = lap.loc[m, "lap_time_s"] + nxt.loc[m, "lap_time_s"] - 2 * lap.loc[m, "drv_session_median_s"]
        out = lap.loc[m, ["session_id", "event_id", "circuit_id", "date", "driver_id", "lap_number"]].assign(loss_s=loss)
        return out[out["loss_s"].between(5, 60)].reset_index(drop=True)

    @cached_property
    def start_tyre_age(self) -> float:
        """Median tyre age at the start of a dry race (cars usually start on sets used in qualifying)."""
        lap1 = self.laps[(self.laps["session_code"] == "R") & (self.laps["lap_number"] == 1)
                         & self.laps["compound"].isin(DRY)]
        return float(max(np.nanmedian(lap1["tyre_life_laps"]) - 1, 0)) if len(lap1) else 0.0
