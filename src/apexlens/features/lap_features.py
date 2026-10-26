"""Gold layer: session references, driver-session summaries, leakage-safe form features and the
lap-level modelling table.

Leakage rule: a form feature for event *e* only uses events whose race date is strictly earlier
than the first session of *e*. This is enforced by computing every form feature on the entity's
event sequence shifted by one and is verified in ``tests/modeling/test_leakage.py``.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from apexlens.storage.io import read_json, read_table, write_table
from apexlens.storage.paths import DataPaths

log = logging.getLogger(__name__)

HALF_LIFE_EVENTS = 4.0
REPRESENTATIVE_MAX_SLOWDOWN = 0.05  # laps > 5% slower than the driver's session median are not representative
MIN_LAPS_DRIVER_SESSION = 5
FORM_N_CAP = 10
RACE_CODES = ("R", "S")

LAP_COLUMNS = [
    "session_id", "event_id", "season", "round", "session_code", "session_type", "circuit_id", "driver_id",
    "constructor_id", "driver_abbr", "lap_number", "lap_time_s", "sector1_s", "sector2_s", "sector3_s", "compound",
    "tyre_life_laps", "fresh_tyre", "stint", "position", "track_status", "air_temp_c", "track_temp_c", "humidity_pct",
    "rainfall", "wind_speed_ms", "is_clean", "exclusion_reason", "condition", "is_wet_compound", "is_pit_in_lap",
    "is_pit_out_lap", "deleted", "quali_segment", "speed_st_kph", "lap_start_utc",
]


def usable_sessions(paths: DataPaths) -> set[str]:
    rows = read_json(paths.manifests / "sessions_ingested.json", default=[])
    return {r["session_id"] for r in rows if r.get("quality_status") in ("ok", "warning") and r.get("n_laps")}


def load_laps(paths: DataPaths, seasons: list[int] | None = None, codes: tuple[str, ...] | None = None) -> pd.DataFrame:
    laps = read_table(paths.silver("laps"), columns=LAP_COLUMNS)
    ok = usable_sessions(paths)
    laps = laps[laps["session_id"].isin(ok)]
    if seasons:
        laps = laps[laps["season"].isin(seasons)]
    if codes:
        laps = laps[laps["session_code"].isin(codes)]
    return laps.reset_index(drop=True)


def add_relative_pace(laps: pd.DataFrame) -> pd.DataFrame:
    """Session reference, relative pace and the representative-lap flag."""
    laps = laps.copy()
    clean = laps[laps["is_clean"]]
    ref = clean.groupby("session_id")["lap_time_s"].median().rename("session_ref_s")
    nref = clean.groupby("session_id").size().rename("session_ref_n")
    laps = laps.join(ref, on="session_id").join(nref, on="session_id")
    laps["rel_pace_pct"] = 100.0 * (laps["lap_time_s"] / laps["session_ref_s"] - 1.0)
    drv_med = laps[laps["is_clean"]].groupby(["session_id", "driver_id"])["lap_time_s"].median().rename("drv_session_median_s")
    laps = laps.join(drv_med, on=["session_id", "driver_id"])
    laps["is_representative"] = laps["is_clean"] & (
        laps["lap_time_s"] <= laps["drv_session_median_s"] * (1 + REPRESENTATIVE_MAX_SLOWDOWN))
    return laps


def driver_session_summary(laps: pd.DataFrame) -> pd.DataFrame:
    rep = laps[laps["is_representative"]]
    g = rep.groupby(["session_id", "event_id", "season", "round", "session_code", "circuit_id", "driver_id"])
    s = g.agg(constructor_id=("constructor_id", "first"), med_rel_pace=("rel_pace_pct", "median"),
              mean_rel_pace=("rel_pace_pct", "mean"), n_laps=("rel_pace_pct", "size"),
              mad_rel_pace=("rel_pace_pct", lambda x: float(np.median(np.abs(x - np.median(x))))),
              wet_share=("is_wet_compound", "mean"), session_ref_s=("session_ref_s", "first")).reset_index()
    s["robust_sd"] = 1.4826 * s["mad_rel_pace"]
    s["se_rel_pace"] = 1.2533 * s["robust_sd"] / np.sqrt(s["n_laps"].clip(lower=1))
    s["is_wet_session"] = s.groupby("session_id")["wet_share"].transform("mean") > 0.5
    # team-mate gap
    tm = s.groupby(["session_id", "constructor_id"])["med_rel_pace"].transform("sum")
    cnt = s.groupby(["session_id", "constructor_id"])["med_rel_pace"].transform("count")
    s["teammate_med_rel_pace"] = np.where(cnt == 2, tm - s["med_rel_pace"], np.nan)
    s["teammate_gap"] = s["med_rel_pace"] - s["teammate_med_rel_pace"]
    return s


def qualifying_summary(paths: DataPaths, seasons: list[int]) -> pd.DataFrame:
    q = read_table(paths.silver("qualifying_results"))
    q = q[q["season"].isin(seasons) & (q["session_code"] == "Q")].copy()
    pole = q.groupby("event_id")["best_s"].transform("min")
    q["quali_gap_pct"] = 100.0 * (q["best_s"] / pole - 1.0)
    return q[["event_id", "season", "round", "driver_id", "constructor_id", "position", "best_s", "quali_gap_pct"]]


def _ewm_prior(df: pd.DataFrame, key: str, value: str, order: list[str], halflife: float = HALF_LIFE_EVENTS) -> pd.Series:
    """EWMA of ``value`` over each entity's *previous* rows (shifted by one, so never includes the current row)."""
    df = df.sort_values(order)
    shifted = df.groupby(key)[value].shift(1)
    out = shifted.groupby(df[key]).transform(lambda s: s.ewm(halflife=halflife, ignore_na=True).mean())
    return out.reindex(df.index)


def event_order(paths: DataPaths) -> pd.DataFrame:
    ev = read_table(paths.silver("events"))
    ev["date"] = pd.to_datetime(ev["date"])
    return ev.sort_values("date")[["event_id", "season", "round", "date", "circuit_id", "circuit_type", "course_length_km",
                                   "turns", "laps", "sprint_laps", "is_sprint_weekend"]]


def driver_event_form(summary: pd.DataFrame, quali: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """One row per (event, driver) with features computed from previous events only."""
    race = summary[summary["session_code"].isin(RACE_CODES) & (summary["n_laps"] >= MIN_LAPS_DRIVER_SESSION)]
    # one value per driver-event: weight race and sprint by laps
    agg = race.groupby(["event_id", "driver_id"]).apply(
        lambda g: pd.Series({"constructor_id": g["constructor_id"].iloc[0],
                             "pace": np.average(g["med_rel_pace"], weights=g["n_laps"]),
                             "tm_gap": np.nanmean(g["teammate_gap"]) if g["teammate_gap"].notna().any() else np.nan,
                             "circuit_id": g["circuit_id"].iloc[0], "is_wet": bool(g["is_wet_session"].any())}),
        include_groups=False).reset_index()
    # the driver-event grid is every driver who appears in a race/sprint *or* qualifying
    base = pd.concat([agg[["event_id", "driver_id", "constructor_id"]],
                      quali[["event_id", "driver_id", "constructor_id"]]]).drop_duplicates(["event_id", "driver_id"])
    base = base.merge(events[["event_id", "season", "round", "date", "circuit_id"]], on="event_id", how="inner")
    base = base.merge(agg[["event_id", "driver_id", "pace", "tm_gap", "is_wet"]], on=["event_id", "driver_id"], how="left")
    base = base.merge(quali[["event_id", "driver_id", "quali_gap_pct"]], on=["event_id", "driver_id"], how="left")
    # wet races are excluded from dry form (they are modelled separately)
    base["pace_dry"] = base["pace"].where(~base["is_wet"].fillna(False).astype(bool))
    order = ["date", "event_id"]
    base = base.sort_values(order).reset_index(drop=True)
    base["drv_form_pace"] = _ewm_prior(base, "driver_id", "pace_dry", order)
    # evidence count behind drv_form_pace; capped because the EWMA (half-life 4) is saturated by ~10 events
    # and an uncapped count would only encode "time since the dataset starts".
    base["drv_form_n"] = base.groupby("driver_id")["pace_dry"].transform(
        lambda s: s.shift(1).notna().cumsum()).clip(upper=FORM_N_CAP)
    base["drv_teammate_gap_form"] = _ewm_prior(base, "driver_id", "tm_gap", order)
    base["drv_quali_form"] = _ewm_prior(base, "driver_id", "quali_gap_pct", order)

    # constructor form: mean of its drivers per event, then prior EWMA
    team_ev = base.groupby(["event_id", "constructor_id", "season", "date"]).agg(
        tpace=("pace_dry", "mean"), tquali=("quali_gap_pct", "mean")).reset_index().sort_values(order)
    team_ev["team_form_pace"] = _ewm_prior(team_ev, "constructor_id", "tpace", order)
    team_ev["team_quali_form"] = _ewm_prior(team_ev, "constructor_id", "tquali", order)
    team_ev["team_season_form"] = team_ev.groupby(["constructor_id", "season"])["tpace"].transform(
        lambda s: s.shift(1).expanding().mean())
    team_ev["team_season_events"] = team_ev.groupby(["constructor_id", "season"]).cumcount()
    base = base.merge(team_ev[["event_id", "constructor_id", "team_form_pace", "team_quali_form", "team_season_form",
                               "team_season_events", "tquali"]], on=["event_id", "constructor_id"], how="left")
    base = base.rename(columns={"quali_gap_pct": "evt_quali_gap", "tquali": "evt_team_quali_gap"})

    # driver x circuit history: previous *seasons* at this circuit, relative to form at the time
    base["pace_vs_form"] = base["pace_dry"] - base["drv_form_pace"]
    hist = []
    for _, g in base.groupby(["driver_id", "circuit_id"]):
        g = g.sort_values("date")
        vals = []
        for i in range(len(g)):
            prev = g.iloc[:i]
            prev = prev[prev["season"] < g["season"].iloc[i]]
            vals.append(prev["pace_vs_form"].mean() if len(prev) and prev["pace_vs_form"].notna().any() else np.nan)
        hist.append(pd.Series(vals, index=g.index))
    base["drv_circuit_hist"] = pd.concat(hist) if hist else np.nan
    return base


def circuit_reference(summary: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Median clean race lap at each circuit in *previous* seasons (per event)."""
    race_ref = summary[summary["session_code"] == "R"].groupby("event_id")["session_ref_s"].first().reset_index()
    race_ref = race_ref.merge(events[["event_id", "season", "circuit_id"]], on="event_id")
    out = []
    for r in events.itertuples():
        prev = race_ref[(race_ref.circuit_id == r.circuit_id) & (race_ref.season < r.season)]
        out.append({"event_id": r.event_id, "circuit_ref_lap_s": prev["session_ref_s"].median() if len(prev) else np.nan})
    return pd.DataFrame(out)


def build_lap_features(paths: DataPaths, seasons: list[int] | None = None) -> dict[str, pd.DataFrame]:
    laps = load_laps(paths, seasons)
    seasons = sorted(laps["season"].unique().tolist())
    laps = add_relative_pace(laps)
    summary = driver_session_summary(laps)
    events = event_order(paths)
    events = events[events["season"].isin(seasons)]
    quali = qualifying_summary(paths, seasons)
    form = driver_event_form(summary, quali, events)
    cref = circuit_reference(summary, events)

    race = laps[laps["session_code"].isin(RACE_CODES)].copy()
    race = race.merge(form[["event_id", "driver_id", "drv_form_pace", "drv_form_n", "drv_teammate_gap_form",
                            "drv_quali_form", "drv_circuit_hist", "team_form_pace", "team_quali_form",
                            "team_season_form", "team_season_events", "evt_quali_gap", "evt_team_quali_gap"]],
                      on=["event_id", "driver_id"], how="left")
    race = race.merge(events[["event_id", "date", "circuit_type", "course_length_km", "turns", "laps", "sprint_laps"]],
                      on="event_id", how="left")
    race = race.merge(cref, on="event_id", how="left")
    scheduled = pd.to_numeric(race["sprint_laps"].where(race["session_code"] == "S", race["laps"]), errors="coerce")
    race["race_progress"] = race["lap_number"].astype(float) / scheduled
    race["is_sprint"] = race["session_code"] == "S"
    race["circuit_is_street"] = race["circuit_type"] == "STREET"
    race = race.rename(columns={"course_length_km": "circuit_length_km", "turns": "circuit_turns"})
    profiles = read_table(paths.gold("circuit_profiles"))
    if len(profiles):
        race = race.merge(profiles[["circuit_id", "circuit_frac_slow", "circuit_frac_fast", "circuit_full_throttle_frac"]],
                          on="circuit_id", how="left")
    race["rainfall"] = race["rainfall"].astype("float")
    race["fresh_tyre"] = race["fresh_tyre"].astype("float")
    race["is_wet_compound"] = race["is_wet_compound"].astype(float)
    race["lap_start_utc"] = race["lap_start_utc"].astype(str)

    write_table(paths.gold("lap_features"), race)
    write_table(paths.gold("driver_session_summary"), summary)
    write_table(paths.gold("driver_event_form"), form)
    write_table(paths.gold("all_laps_relative"), laps.assign(lap_start_utc=laps["lap_start_utc"].astype(str)))
    log.info("lap_features: %d race/sprint laps (%d representative)", len(race), int(race["is_representative"].sum()))
    return {"lap_features": race, "summary": summary, "form": form}
