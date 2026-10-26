"""Pydantic request schemas shared by the prediction service and the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

Compound = Literal["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]
Horizon = Literal["pre_event", "pre_race"]


class ScenarioConditions(BaseModel):
    """Conditions shared by every driver in a scenario."""

    circuit_id: str | None = Field(None, description="F1DB circuit id; derived from as_of_event_id when omitted")
    as_of_event_id: str | None = Field(
        None, description="Use form as it stood before this historical event (e.g. 2024-14). "
                          "Omit to use form after the most recent ingested event.")
    horizon: Horizon = "pre_event"
    compound: Compound = "MEDIUM"
    tyre_life_laps: float = Field(10, ge=0, le=80)
    race_progress: float = Field(0.5, ge=0.0, le=1.0, description="Lap / scheduled laps (fuel-load proxy)")
    track_temp_c: float | None = Field(None, ge=-10, le=75)
    air_temp_c: float | None = Field(None, ge=-15, le=55)
    humidity_pct: float | None = Field(None, ge=0, le=100)
    rainfall: bool = False
    fresh_tyre: bool | None = None
    stint: int = Field(2, ge=1, le=8)
    is_sprint: bool = False

    @model_validator(mode="after")
    def _need_location(self):
        if not self.circuit_id and not self.as_of_event_id:
            raise ValueError("either circuit_id or as_of_event_id is required")
        return self


class LapTimeRequest(ScenarioConditions):
    driver_id: str
    constructor_override: str | None = Field(
        None, description="Use this constructor's team features instead of the driver's own (counterfactual)")
    quali_gap_pct: float | None = Field(None, ge=0, le=20, description="Assumed qualifying gap to pole (pre_race)")


class ComparisonRequest(ScenarioConditions):
    driver_ids: list[str] = Field(..., min_length=2, max_length=2)
    common_car: bool = Field(False, description="Give both drivers the first driver's team features")


class DegradationRequest(BaseModel):
    driver_id: str | None = None
    circuit_id: str | None = None
    compound: Literal["SOFT", "MEDIUM", "HARD"] = "MEDIUM"
    season: int | None = None
    max_tyre_age: int = Field(30, ge=5, le=60)


class ExplainRequest(BaseModel):
    task: Literal["lap_time", "driver_comparison"] = "lap_time"
    lap: LapTimeRequest | None = None
    comparison: ComparisonRequest | None = None
