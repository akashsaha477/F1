"""Feature registry: meaning, unit, derivation, sources, availability and limitations.

``availability`` states the latest point in time at which the feature is known:

* ``static``      known before the season (circuit descriptors)
* ``pre_event``   computed only from events that finished before the event's first session
* ``pre_race``    additionally uses the same event's practice/qualifying sessions
* ``scenario``    a condition the user (or the observed lap) specifies: tyre, weather, race phase
* ``target``      outcome; never used as an input
"""

from __future__ import annotations

FEATURES: dict[str, dict] = {
    # --- target --------------------------------------------------------------------------
    "rel_pace_pct": dict(group="target", unit="% of session reference", availability="target",
                         description="Lap time relative to the session reference: 100 * (lap / reference - 1). "
                                     "Negative is faster.",
                         derivation="reference = median of all clean laps of all drivers in the same session",
                         sources=["tracinginsights"], limitations="Field composition shifts the reference slightly."),
    # --- driver form ----------------------------------------------------------------------
    "drv_form_pace": dict(group="driver", unit="%", availability="pre_event",
                          description="Driver's exponentially weighted race pace over previous events",
                          derivation="EWMA (half-life 4 events) of the driver's median representative-lap rel_pace_pct "
                                     "in previous races/sprints, strictly before the event",
                          sources=["tracinginsights"], limitations="Mixes driver and car performance."),
    "drv_form_n": dict(group="driver", unit="events", availability="pre_event",
                       description="Number of previous events contributing to drv_form_pace",
                       derivation="count", sources=["tracinginsights"], limitations=""),
    "drv_teammate_gap_form": dict(group="driver", unit="%", availability="pre_event",
                                  description="Driver's EWMA race-pace gap to the team-mate in previous events",
                                  derivation="median rel pace minus team-mate's, previous events only",
                                  sources=["tracinginsights"],
                                  limitations="Team-mates may run different strategies or setups."),
    "drv_quali_form": dict(group="driver", unit="% gap to pole", availability="pre_event",
                           description="Driver's EWMA qualifying gap to pole in previous events",
                           derivation="F1DB best qualifying time / pole time - 1", sources=["f1db"],
                           limitations="Q1 eliminees have fewer runs and less track evolution."),
    "drv_circuit_hist": dict(group="interaction", unit="%", availability="pre_event",
                             description="Driver's mean race pace at this circuit in previous seasons minus their "
                                         "season form at the time (driver x circuit interaction history)",
                             derivation="previous seasons only; NaN when the driver has no history at the circuit",
                             sources=["tracinginsights"], limitations="At most a few observations per pair."),
    # --- team / car -----------------------------------------------------------------------
    "team_form_pace": dict(group="team", unit="%", availability="pre_event",
                           description="Constructor's EWMA race pace (mean of its drivers) over previous events",
                           derivation="EWMA half-life 4 events across seasons", sources=["tracinginsights"],
                           limitations="Car changes between seasons are only captured by team_season_events."),
    "team_season_form": dict(group="team", unit="%", availability="pre_event",
                             description="Constructor's mean race pace over previous events of the same season",
                             derivation="expanding mean, NaN at the first event of a season", sources=["tracinginsights"],
                             limitations=""),
    "team_season_events": dict(group="team", unit="events", availability="pre_event",
                               description="Previous events of the constructor in this season", derivation="count",
                               sources=["tracinginsights"], limitations=""),
    "team_quali_form": dict(group="team", unit="% gap to pole", availability="pre_event",
                            description="Constructor's EWMA qualifying gap to pole", derivation="F1DB qualifying",
                            sources=["f1db"], limitations=""),
    # --- weekend information (pre-race horizon only) -------------------------------------
    "evt_quali_gap": dict(group="weekend", unit="% gap to pole", availability="pre_race",
                          description="Driver's qualifying gap to pole at this event", derivation="F1DB qualifying",
                          sources=["f1db"], limitations="Only valid for a pre-race (post-qualifying) horizon."),
    "evt_team_quali_gap": dict(group="weekend", unit="% gap to pole", availability="pre_race",
                               description="Mean qualifying gap of the constructor's drivers at this event",
                               derivation="F1DB qualifying", sources=["f1db"], limitations="Pre-race horizon only."),
    # --- circuit ----------------------------------------------------------------------------
    "circuit_length_km": dict(group="track", unit="km", availability="static", description="Lap length",
                              derivation="F1DB course length", sources=["f1db"], limitations=""),
    "circuit_turns": dict(group="track", unit="count", availability="static", description="Number of turns",
                          derivation="F1DB", sources=["f1db"], limitations=""),
    "circuit_is_street": dict(group="track", unit="bool", availability="static", description="Street circuit",
                              derivation="F1DB circuit type == STREET", sources=["f1db"], limitations=""),
    "circuit_ref_lap_s": dict(group="track", unit="s", availability="pre_event",
                              description="Median clean race lap at this circuit in previous seasons",
                              derivation="previous seasons only", sources=["tracinginsights"],
                              limitations="NaN for circuits new to the dataset."),
    "circuit_frac_slow": dict(group="track", unit="fraction", availability="static",
                              description="Share of identified corners classified slow (< 125 km/h minimum speed)",
                              derivation="Corner analysis of qualifying telemetry (track property)",
                              sources=["tracinginsights"],
                              limitations="Corner speeds depend on the car generation; treated as a static descriptor."),
    "circuit_frac_fast": dict(group="track", unit="fraction", availability="static",
                              description="Share of identified corners classified fast (>= 200 km/h minimum speed)",
                              derivation="as circuit_frac_slow", sources=["tracinginsights"], limitations="as above"),
    "circuit_full_throttle_frac": dict(group="track", unit="fraction", availability="static",
                                       description="Share of lap distance at >= 98% throttle on reference laps",
                                       derivation="qualifying telemetry", sources=["tracinginsights"],
                                       limitations="as above"),
    # --- tyre -------------------------------------------------------------------------------
    "compound": dict(group="tyre", unit="category", availability="scenario",
                     description="Normalised compound (SOFT/MEDIUM/HARD/INTERMEDIATE/WET)",
                     derivation="source compound string", sources=["tracinginsights"],
                     limitations="SOFT/MEDIUM/HARD are relative names; the Pirelli C-number differs by event."),
    "tyre_life_laps": dict(group="tyre", unit="laps", availability="scenario", description="Tyre age at lap",
                           derivation="FastF1 TyreLife", sources=["tracinginsights"], limitations=""),
    "fresh_tyre": dict(group="tyre", unit="bool", availability="scenario", description="Set was new at fitting",
                       derivation="FastF1 FreshTyre", sources=["tracinginsights"], limitations=""),
    "stint": dict(group="tyre", unit="count", availability="scenario", description="Stint number",
                  derivation="FastF1 Stint", sources=["tracinginsights"], limitations=""),
    # --- weather ----------------------------------------------------------------------------
    "track_temp_c": dict(group="weather", unit="°C", availability="scenario", description="Track temperature",
                         derivation="FastF1 weather sample joined to the lap", sources=["tracinginsights"],
                         limitations="One trackside sensor per circuit."),
    "air_temp_c": dict(group="weather", unit="°C", availability="scenario", description="Air temperature",
                       derivation="as track_temp_c", sources=["tracinginsights"], limitations=""),
    "humidity_pct": dict(group="weather", unit="%", availability="scenario", description="Relative humidity",
                         derivation="as track_temp_c", sources=["tracinginsights"], limitations=""),
    "rainfall": dict(group="weather", unit="bool", availability="scenario", description="Rain detected",
                     derivation="FastF1 Rainfall", sources=["tracinginsights"],
                     limitations="Binary; no intensity."),
    "is_wet_compound": dict(group="weather", unit="bool", availability="scenario",
                            description="Intermediate or full-wet tyre fitted", derivation="compound",
                            sources=["tracinginsights"], limitations=""),
    # --- race context -----------------------------------------------------------------------
    "race_progress": dict(group="race_context", unit="fraction", availability="scenario",
                          description="Lap number / scheduled race distance (fuel-load proxy)",
                          derivation="F1DB scheduled laps", sources=["f1db", "tracinginsights"],
                          limitations="Fuel load is not observed; this is a proxy."),
    "lap_number": dict(group="race_context", unit="lap", availability="scenario", description="Lap number",
                       derivation="FastF1 LapNumber", sources=["tracinginsights"], limitations=""),
    "is_sprint": dict(group="race_context", unit="bool", availability="static", description="Sprint race session",
                      derivation="session code", sources=["f1db"], limitations=""),
}

FEATURE_GROUPS = ["driver", "team", "weekend", "track", "tyre", "weather", "race_context", "interaction", "corner"]


def features_in_group(group: str) -> list[str]:
    return [k for k, v in FEATURES.items() if v["group"] == group]
