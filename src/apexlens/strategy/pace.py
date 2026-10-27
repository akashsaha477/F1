"""Driver/car base pace for a race week, from the lap-pace model (Model A, pre-race horizon).

For a race in season S the model is the walk-forward fold trained only on seasons before S, so planning a
past race never uses that race (or anything after it). For races beyond the ingested data the production
model is used. Base pace is the model's expected representative lap on MEDIUM tyres at ``REF_AGE`` laps,
mid-race, in the weekend's weather; the strategy model adds tyre, fuel and pit effects around it.
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from apexlens.evaluation.splits import walk_forward_by_season
from apexlens.modeling import lap_pace as LP
from apexlens.modeling.models import LightGBMPaceModel
from apexlens.modeling.train_pipeline import dataset_version
from apexlens.predictions.service import PredictionService, ScenarioError
from apexlens.schemas.api import LapTimeRequest
from apexlens.storage.paths import DataPaths
from apexlens.strategy.params import REF_AGE

log = logging.getLogger(__name__)
HORIZON = "pre_race"


def season_model(paths: DataPaths, season: int, horizon: str = HORIZON, production: bool = False):
    """(model, description). Trained on seasons < ``season`` and cached; the production model (all data) when
    ``production`` is set, for the first season, or for seasons beyond the data."""
    df = LP.load_dataset(paths)
    seasons = sorted(df["season"].unique())
    if not production and season in seasons and season != seasons[0]:
        dv = dataset_version(paths)["lap_features_sha"]
        path = Path(paths.models) / "strategy" / f"lap_pace_{horizon}_before_{season}_{dv}.joblib"
        if path.exists():
            return joblib.load(path), f"lap-pace model trained on {seasons[0]}–{season - 1} only"
        spec = LP.feature_spec(horizon, available=set(df.columns))
        split = next(s for s in walk_forward_by_season(df, min_train_seasons=1) if s.test_period == str(season))
        split.check_temporal(df)
        tr, ca = df.loc[split.train_idx], df.loc[split.calib_idx]
        model = LightGBMPaceModel(spec).fit(tr, tr[LP.TARGET], X_val=ca, y_val=ca[LP.TARGET])
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, path)
        log.info("trained strategy pace model for %s (%s)", season, path.name)
        return model, f"lap-pace model trained on {seasons[0]}–{season - 1} only"
    svc = PredictionService(paths)
    obj = svc.artifact(horizon)[0]
    note = ("production lap-pace model trained on all ingested races" if production or season > seasons[-1]
            else "production lap-pace model (in-sample: no earlier season to train on)")
    return obj["model"], note


def base_paces(svc: PredictionService, model, *, event_id: str | None, circuit_id: str | None, weather: dict,
               overrides: dict[str, str] | None = None, drivers: list[str] | None = None) -> pd.DataFrame:
    """Expected pace (% of the session reference) of every driver at the reference condition."""
    cond = {"as_of_event_id": event_id} if event_id else {"circuit_id": circuit_id}
    req0 = LapTimeRequest(driver_id="_", horizon=HORIZON, compound="MEDIUM", tyre_life_laps=REF_AGE, race_progress=0.5,
                          stint=2, track_temp_c=weather.get("track_temp_c"), air_temp_c=weather.get("air_temp_c"),
                          humidity_pct=weather.get("humidity_pct"), **cond)
    ctx = svc._context(req0)
    form = ctx["form"]
    ids = drivers if drivers is not None else list(dict.fromkeys(form.index))
    rows, meta = [], []
    for d in ids:
        req = req0.model_copy(update={"driver_id": d, "constructor_override": (overrides or {}).get(d)})
        try:
            X, info = svc.build_row(req, ctx)
        except ScenarioError as exc:
            log.debug("no base pace for %s: %s", d, exc)
            continue
        rows.append(X)
        f = info["form_row"]
        meta.append({"driver_id": d, "constructor_id": info["team_id"], "drv_quali_form": f.get("drv_quali_form", np.nan),
                     "evt_quali_gap": X["evt_quali_gap"].iloc[0] if "evt_quali_gap" in X else np.nan,
                     "car_override": (overrides or {}).get(d)})
    if not rows:
        return pd.DataFrame(columns=["driver_id", "constructor_id", "base_pct"])
    X = pd.concat(rows, ignore_index=True)
    out = pd.DataFrame(meta)
    out["base_pct"] = model.predict(X)
    return out
