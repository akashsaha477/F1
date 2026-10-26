"""Regenerate every report in reports/ and the generated docs from the stored data and evaluation outputs.

    python scripts/generate_reports.py               # everything
    python scripts/generate_reports.py --only eda model_comparison

Run after ``scripts/build_features.py``, ``scripts/train_models.py`` and ``scripts/evaluate_models.py``.
"""

import argparse
import logging
import warnings
from pathlib import Path

from apexlens.config.settings import get_settings
from apexlens.ingestion.context import configure_logging
from apexlens.reporting import reports as R
from apexlens.storage.paths import DataPaths

REPORTS = {
    "coverage_report": R.coverage, "eda": R.eda, "feature_engineering": R.feature_engineering,
    "driver_profiles": R.driver_profiles, "model_comparison": R.model_comparison, "error_analysis": R.error_analysis,
    "explainability": R.explainability,
}
DOCS = {"data_dictionary": R.data_dictionary, "feature_definitions": R.feature_definitions, "model_card": R.model_card}

if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    p = argparse.ArgumentParser()
    p.add_argument("--only", nargs="+", choices=[*REPORTS, *DOCS])
    a = p.parse_args()
    configure_logging(logging.INFO)
    log = logging.getLogger("reports")
    settings = get_settings()
    root = Path(__file__).resolve().parents[1]
    ctx = R.Ctx(paths=DataPaths.default(), reports=Path(settings.reports_dir), docs=root / "docs")
    ctx.figs.mkdir(parents=True, exist_ok=True)
    written = []
    for name, fn in {**REPORTS, **DOCS}.items():
        if a.only and name not in a.only:
            continue
        target = (ctx.docs if name in DOCS else ctx.reports) / f"{name}.md"
        log.info("writing %s", target)
        target.write_text(fn(ctx))
        written.append(target.name)
    if not a.only:
        (ctx.reports / "README.md").write_text(R.index(ctx, written))
    print("\n".join(written))
