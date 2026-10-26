"""Secondary evaluations after training: explanation validation, ablations, corner experiments
(Model B), qualifying model (Model F) and error analysis. Results go to data/models/evaluation_runs/ and the model folders.

    python scripts/evaluate_models.py                # everything
    python scripts/evaluate_models.py --only ablations
"""

import argparse
import json
import logging
import warnings

from apexlens.evaluation.error_analysis import run_error_analysis
from apexlens.explainability.validation import validate_explanations
from apexlens.ingestion.context import configure_logging
from apexlens.modeling.ablation import run_ablations
from apexlens.modeling.quali_model import run_quali_model
from apexlens.modeling.train_pipeline import run_corner_experiments
from apexlens.storage.paths import DataPaths

STEPS = ("explanations", "ablations", "corners", "quali", "errors")

if __name__ == "__main__":
    warnings.filterwarnings("ignore", category=FutureWarning)
    p = argparse.ArgumentParser()
    p.add_argument("--only", choices=STEPS)
    a = p.parse_args()
    configure_logging(logging.INFO)
    paths = DataPaths.default()
    steps = [a.only] if a.only else list(STEPS)
    summary = {}
    if "explanations" in steps:
        for h in ("pre_event", "pre_race"):
            v = validate_explanations(paths, horizon=h)
            summary[f"explanations_{h}"] = {k: v.get(k) for k in ("additivity_max_abs_error", "treeshap_vs_shap_library_max_abs_diff")}
    if "ablations" in steps:
        r = run_ablations(paths)
        summary["ablations"] = {c["name"]: round(c["holdout"]["mae"], 4) for c in r["configs"]}
    if "corners" in steps:
        r = run_corner_experiments(paths)
        summary["corners"] = r["sector_model"]["pooled_mae"]
    if "quali" in steps:
        r = run_quali_model(paths)
        summary["quali"] = {m: round(v["mae"], 4) for m, v in r["models"].items()}
    if "errors" in steps:
        for h in ("pre_event", "pre_race"):
            r = run_error_analysis(paths, horizon=h)
            summary[f"errors_{h}"] = {c["by"]: round(c["estimate"], 3) for c in r["contrasts"]}
    print(json.dumps(summary, indent=2, default=str))
