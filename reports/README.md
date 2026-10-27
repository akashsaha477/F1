# ApexLens reports

_Generated 2026-10-27 08:10 UTC by `scripts/generate_reports.py` from `all outputs`. Do not edit by hand; re-run the script._

Latest evaluation run `20261027T075133Z`; dataset `{"sessions_manifest_sha": "565045d5ae37a4f5", "lap_features_sha": "5c799359d1af068f", "f1db_seasons": 77}`.

| Report | Contents |
|---|---|
| [coverage_report.md](coverage_report.md) | Sources, per-season coverage, quality checks, entity mapping |
| [eda.md](eda.md) | Volumes, exclusions, target distribution, compounds, weather, telemetry quality |
| [feature_engineering.md](feature_engineering.md) | Model inputs, availability, missingness, leakage controls, correlations |
| [driver_profiles.md](driver_profiles.md) | Variance components, team-adjusted pace, condition effects, clusters |
| [model_comparison.md](model_comparison.md) | Models A–F, walk-forward metrics, paired comparisons, ablations |
| [error_analysis.md](error_analysis.md) | Where the models fail: conditions, tyre age, experience, events, teams |
| [explainability.md](explainability.md) | Global and local explanations and their validation |
| [race_strategy.md](race_strategy.md) | Race week planner: strategy, pit windows and finishing order vs what happened |

Generated documentation: `docs/data_dictionary.md`, `docs/feature_definitions.md`, `docs/model_card.md`.

Regenerate everything after new data or training:

```bash
make features train evaluate reports
```
