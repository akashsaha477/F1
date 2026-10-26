"""Train and evaluate the lap-pace models (walk-forward by season) and register versioned artifacts.

    python scripts/train_models.py            # both horizons
    python scripts/train_models.py --horizons pre_event
"""

import argparse
import json
import logging
import warnings

from apexlens.ingestion.context import configure_logging
from apexlens.modeling.train_pipeline import train_lap_pace
from apexlens.storage.paths import DataPaths

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=FutureWarning)
    p = argparse.ArgumentParser()
    p.add_argument("--horizons", default="pre_event,pre_race")
    p.add_argument("--n-boot", type=int, default=300)
    a = p.parse_args()
    configure_logging(logging.INFO)
    s = train_lap_pace(DataPaths.default(), horizons=tuple(a.horizons.split(",")), n_boot=a.n_boot)
    out = {h: {"selected": v["selected_model"], "versions": v["versions"],
               "dev_mae": {m: round(x["mae"], 4) for m, x in v["pooled"]["development"].items()},
               "holdout_mae": {m: round(x["mae"], 4) for m, x in v["pooled"]["holdout"].items()}}
           for h, v in s["horizons"].items()}
    print(json.dumps({"run_id": s["run_id"], **out}, indent=2))
