"""Report builders. Every number in the reports is read from the data or evaluation outputs at
generation time; nothing is typed in by hand. Run ``python scripts/generate_reports.py``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from apexlens.features.definitions import FEATURES
from apexlens.modeling import lap_pace as LP
from apexlens.modeling.registry import load_artifact, production_version
from apexlens.reporting import figures as F
from apexlens.reporting.markdown import ci, figure, fmt, table
from apexlens.storage.io import read_json, read_table
from apexlens.storage.paths import DataPaths

MODEL_LABELS = {"hist_group_median": "Historical group median", "team_adjusted_form": "Team-adjusted form baseline",
                "ridge": "Ridge", "spline_gam": "Spline GAM", "lightgbm": "LightGBM (Huber)"}


@dataclass
class Ctx:
    paths: DataPaths
    reports: Path
    docs: Path

    @property
    def figs(self) -> Path:
        return self.reports / "figures"

    @property
    def runs(self) -> Path:
        return self.paths.models / "evaluation_runs"

    def run(self) -> dict:
        rid = read_json(self.runs / "latest.json")["run_id"]
        return read_json(self.runs / f"{rid}.json")

    def optional(self, name: str) -> dict | None:
        f = self.runs / name
        return read_json(f) if f.exists() else None


def header(title: str, ctx: Ctx, sources: list[str]) -> str:
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    src = ", ".join(f"`{s}`" for s in sources)
    return (f"# {title}\n\n_Generated {stamp} by `scripts/generate_reports.py` from {src}. "
            "Do not edit by hand; re-run the script._\n")


def _rel(ctx: Ctx, name: str) -> str:
    return f"figures/{name}"


# --------------------------------------------------------------------------------------------------
# EDA
# --------------------------------------------------------------------------------------------------
def eda(ctx: Ctx) -> str:
    laps = read_table(ctx.paths.gold("all_laps_relative"))
    lf = read_table(ctx.paths.gold("lap_features"))
    tel = read_table(ctx.paths.silver("telemetry_laps"))
    wx = read_table(ctx.paths.silver("weather_observations"))
    rc = read_table(ctx.paths.silver("race_control_events"))
    out = [header("Exploratory data analysis", ctx, ["gold/all_laps_relative", "gold/lap_features", "silver/*"])]

    rows = []
    for s, g in laps.groupby("season"):
        race = g[g["session_type"].isin(["race", "sprint"])]
        rows.append({"season": int(s), "events": int(g["event_id"].nunique()), "sessions": int(g["session_id"].nunique()),
                     "drivers": int(g["driver_id"].nunique()), "laps": int(len(g)), "clean": float(g["is_clean"].mean()),
                     "race_laps": int(len(race)), "representative": int(race["is_representative"].fillna(False).sum()),
                     "wet": float(g["condition"].isin(["wet", "damp"]).mean()),
                     "telemetry_laps": int((tel["season"] == s).sum())})
    out += ["## Volume by season\n",
            table(rows, [("season", "Season"), ("events", "Events"), ("sessions", "Sessions"), ("drivers", "Drivers"),
                         ("laps", "Laps"), ("clean", "Clean share"), ("race_laps", "Race+sprint laps"),
                         ("representative", "Representative race laps"), ("wet", "Wet/damp share"),
                         ("telemetry_laps", "Telemetry laps")],
                  formats={"clean": lambda v: fmt(v, pct=True, nd=3), "wet": lambda v: fmt(v, pct=True, nd=3)}),
            "\nRepresentative laps (clean and within 5% of the driver's session median) are the modelling "
            "population for race pace. Telemetry is the fastest clean qualifying lap per driver and session.\n"]

    reasons = laps.loc[~laps["is_clean"], "exclusion_reason"].value_counts(normalize=False)
    share = (reasons / len(laps)).sort_values(ascending=False)
    F.hbar([r.replace("_", " ") for r in share.index], share.to_numpy(), ctx.figs / "eda_exclusions.png",
           "Why laps are excluded (share of all laps)", "share of all laps")
    out += ["## Lap exclusions\n",
            f"{fmt(float((~laps['is_clean']).mean()), pct=True, nd=3)} of {len(laps):,} laps are excluded from pace analysis; "
            "each keeps its first matching reason (the order is listed in the methodology).\n",
            figure(_rel(ctx, "eda_exclusions.png"), "Exclusion reasons"),
            "\n" + table([{"reason": k, "laps": int(v), "share": float(v / len(laps))} for k, v in reasons.items()],
                         [("reason", "Reason"), ("laps", "Laps"), ("share", "Share of all laps")],
                         formats={"share": lambda v: fmt(v, pct=True, nd=3)}) + "\n"]

    rep = lf[lf["is_representative"] & lf["rel_pace_pct"].notna()]
    q = rep["rel_pace_pct"].quantile([0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    F.histogram(rep["rel_pace_pct"], ctx.figs / "eda_rel_pace.png", "Representative race-lap pace",
                "% relative to session reference (negative = faster)", clip=(-6, 8))
    out += ["## Target distribution\n",
            f"Relative pace of {len(rep):,} representative race and sprint laps "
            f"(quantiles 1/5/25/50/75/95/99%: {', '.join(fmt(float(v), 2, signed=True) for v in q)}). "
            "The right tail comes from fuel-heavy opening stints, worn tyres and slower cars; values are clipped to "
            "[-6, 8] in the plot only.\n",
            figure(_rel(ctx, "eda_rel_pace.png"), "Histogram of relative pace") + "\n"]

    comp = (rep.groupby("season")["compound"].value_counts(normalize=True).unstack(fill_value=0))
    out += ["## Tyre compounds in representative race laps\n",
            table([{"season": int(s), **{c: float(comp.loc[s, c]) for c in comp.columns}} for s in comp.index],
                  ["season"] + list(comp.columns), formats={c: (lambda v: fmt(v, pct=True, nd=3)) for c in comp.columns}),
            "\nSOFT/MEDIUM/HARD are relative names; the Pirelli C-number differs by event and is not in the data.\n"]

    wq = wx.groupby("season")[["track_temp_c", "air_temp_c", "humidity_pct"]].quantile([0.05, 0.5, 0.95]).unstack()
    wrows = []
    for s in wq.index:
        wrows.append({"season": int(s), **{f"{v}_{k}": float(wq.loc[s, (v, k)]) for v in ["track_temp_c", "air_temp_c"]
                                            for k in [0.05, 0.5, 0.95]},
                      "rain_sessions": int(wx[(wx["season"] == s) & (wx["rainfall"].astype(bool))]["session_id"].nunique())})
    out += ["## Weather\n",
            table(wrows, [("season", "Season"), ("track_temp_c_0.05", "Track °C p5"), ("track_temp_c_0.5", "median"),
                          ("track_temp_c_0.95", "p95"), ("air_temp_c_0.05", "Air °C p5"), ("air_temp_c_0.5", "median"),
                          ("air_temp_c_0.95", "p95"), ("rain_sessions", "Sessions with rain detected")], nd=1),
            "\nOne trackside sensor per circuit, sampled about once a minute.\n"]

    qrows = {}
    for f in sorted((ctx.paths.manifests / "quality").glob("telemetry_*.json")):
        season = int(f.stem.split("_")[1][:4])
        for c in read_json(f)["checks"]:
            r = qrows.setdefault((season, c["name"]), {"season": season, "check": c["name"], "severity": c["severity"],
                                                       "sessions_failed": 0, "samples_failed": 0, "samples": 0})
            r["sessions_failed"] += int(not c["passed"])
            r["samples_failed"] += int(c["n_failed"])
            r["samples"] += int(c["n_total"])
    for r in qrows.values():
        r["share"] = r["samples_failed"] / r["samples"] if r["samples"] else None
    out += ["## Telemetry quality\n",
            "Checks run per qualifying session over all telemetry samples (`manifests/quality/telemetry_*.json`). "
            "Sessions with warnings are kept; corner metrics carry their own per-corner quality flags.\n",
            table([r for r in qrows.values() if r["sessions_failed"]],
                  [("season", "Season"), ("check", "Check"), ("severity", "Severity"), ("sessions_failed", "Sessions failing"),
                   ("samples_failed", "Samples failing"), ("share", "Share of samples")],
                  formats={"share": lambda v: fmt(v, pct=True, nd=4)}), ""]

    cat = rc.groupby(["season", "category"]).size().unstack(fill_value=0)
    out += ["## Race control messages\n",
            table([{"season": int(s), **{c: int(cat.loc[s, c]) for c in cat.columns}} for s in cat.index], ["season", *cat.columns])]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------------------------------
# Coverage (wraps the manifest written by the ingestion step)
# --------------------------------------------------------------------------------------------------
def coverage(ctx: Ctx) -> str:
    from apexlens.ingestion.context import IngestionContext
    from apexlens.ingestion.coverage import build_coverage_report

    ictx = IngestionContext.create()
    build_coverage_report(ictx)
    return (Path(ictx.settings.reports_dir) / "coverage_report.md").read_text()


# --------------------------------------------------------------------------------------------------
# Feature engineering
# --------------------------------------------------------------------------------------------------
def feature_engineering(ctx: Ctx) -> str:
    lf = read_table(ctx.paths.gold("lap_features"))
    rep = lf[lf["is_representative"] & lf["rel_pace_pct"].notna()]
    out = [header("Feature engineering", ctx, ["gold/lap_features", "features/definitions.py"])]
    out += ["Model A inputs by group. *Availability* is the latest point in time at which a value is known "
            "(`pre_event` = only earlier events; `pre_race` = adds the same weekend's qualifying; `scenario` = a "
            "condition set by the user or observed on the lap). Statistics are over representative race laps.\n"]
    rows = []
    for group in ["driver", "team", "weekend", "track", "corner", "tyre", "weather", "race_context", "interaction"]:
        for f in LP.GROUPS.get(group, []):
            if f == "compound" or f not in rep.columns:
                continue
            v = pd.to_numeric(rep[f], errors="coerce").astype(float)
            meta = FEATURES.get(f, {})
            rows.append({"feature": f"`{f}`", "group": group, "unit": meta.get("unit", ""),
                         "availability": meta.get("availability", ""), "missing": float(v.isna().mean()),
                         "p5": float(v.quantile(0.05)), "median": float(v.median()), "p95": float(v.quantile(0.95))})
    out.append(table(rows, [("feature", "Feature"), ("group", "Group"), ("unit", "Unit"), ("availability", "Availability"),
                            ("missing", "Missing"), ("p5", "p5"), ("median", "Median"), ("p95", "p95")], nd=2,
                     formats={"missing": lambda v: fmt(v, pct=True, nd=3)}))
    out += ["\nLightGBM handles missing values natively; the linear models impute training medians and winsorise "
            "inputs at the 1st/99th training percentiles. Full definitions: `docs/feature_definitions.md`.\n",
            "## Leakage controls\n",
            "* Form features are exponentially weighted means (half-life 4 events) of results from events that "
            "finished before the event's first session (shifted EWMA); `drv_form_n` counts those events, capped at 10.",
            "* `circuit_ref_lap_s` and `drv_circuit_hist` use earlier seasons only.",
            "* Circuit corner profiles come from qualifying telemetry; for evaluation they are a fixed track descriptor.",
            "* `tests/modeling/test_leakage.py` perturbs future events and asserts that earlier features do not change; "
            "the walk-forward splitter raises if training data reaches the test period.\n"]
    corr = rep[[r["feature"].strip("`") for r in rows]].apply(lambda c: pd.to_numeric(c, errors="coerce").astype(float)).corr("spearman")
    pairs = [{"a": f"`{a}`", "b": f"`{b}`", "rho": float(corr.loc[a, b])}
             for i, a in enumerate(corr.columns) for b in corr.columns[i + 1:]
             if np.isfinite(corr.loc[a, b]) and abs(corr.loc[a, b]) >= 0.7]
    out += ["## Strongly correlated inputs (|Spearman| ≥ 0.7)\n",
            table(sorted(pairs, key=lambda r: -abs(r["rho"])), [("a", "Feature"), ("b", "Feature"), ("rho", "Spearman")], nd=2),
            "\nCorrelated inputs share credit arbitrarily in SHAP explanations; grouped permutation importance "
            "is reported alongside for that reason.\n"]
    return "\n".join(out)


# --------------------------------------------------------------------------------------------------
# Driver profiles
# --------------------------------------------------------------------------------------------------
def driver_profiles(ctx: Ctx) -> str:
    prof = read_table(ctx.paths.gold("driver_profiles"))
    meta = read_json(ctx.paths.gold("driver_profiles") / "meta.json")
    cond = read_table(ctx.paths.gold("driver_condition_effects"))
    clusters = read_json(ctx.paths.gold("driver_clusters") / "meta.json")
    corner = ctx.paths.models / "evaluation_runs" / "corner_experiments.json"
    out = [header("Driver performance profiles", ctx, ["gold/driver_profiles", "gold/driver_condition_effects",
                                                         "gold/driver_clusters"])]
    rm, qm = meta["race_model"], meta["quali_model"]
    vrows = [{"component": k.replace("driver_id", "driver").replace("_", "-"), "race": rm["variances"].get(k),
              "quali": qm["variances"].get(k)} for k in ["driver_id", "driver_season", "team_season", "residual"]]
    tot = {m: sum(v for v in d["variances"].values()) for m, d in (("race", rm), ("quali", qm))}
    for r in vrows:
        r["race_share"], r["quali_share"] = r["race"] / tot["race"], r["quali"] / tot["quali"]
    out += ["## Method\n",
            "Stage 1 removes, per session, the effects of compound, compound-specific tyre age and lap number from each "
            "driver's representative laps (OLS; non-identifiable terms dropped in a fixed order). Stage 2 fits crossed "
            "random effects for driver, driver-season and team-season with session fixed effects by REML:\n",
            f"`{rm['formula']}`  \n`{qm['formula']}`\n",
            "## Variance components (%²)\n",
            table(vrows, [("component", "Component"), ("race", "Race pace"), ("race_share", "share"),
                          ("quali", "Qualifying gap"), ("quali_share", "share")],
                  formats={"race_share": lambda v: fmt(v, pct=True, nd=3), "quali_share": lambda v: fmt(v, pct=True, nd=3)}),
            f"\nRace model: {rm['n_obs']:,} driver-sessions; qualifying model: {qm['n_obs']:,} driver-sessions. "
            f"{meta['identification_note']}\n"]

    latest = int(prof["season"].max())
    d = prof[(prof["season"] == latest) & prof["race_pace_adj"].notna()].sort_values("race_pace_adj")
    F.interval_dots(d["driver_id"].tolist(), d["race_pace_adj"].tolist(), d["race_pace_adj_lo"].tolist(),
                    d["race_pace_adj_hi"].tolist(), ctx.figs / "profiles_race_pace.png",
                    f"Team-adjusted race pace, {latest} (90% posterior interval)", "% of reference lap (negative = faster)")
    overlap = 0
    lo, hi = d["race_pace_adj_lo"].to_numpy(), d["race_pace_adj_hi"].to_numpy()
    for i in range(len(d) - 1):
        overlap += int(hi[i] >= lo[i + 1])
    out += [f"## Team-adjusted race pace, {latest}\n",
            figure(_rel(ctx, "profiles_race_pace.png"), "Team-adjusted race pace with intervals"),
            f"\n{overlap} of {len(d) - 1} adjacent pairs in this ordering have overlapping intervals; the ordering is "
            "not a ranking with that precision. Drivers with few races are wide by construction.\n",
            table(d.head(10).to_dict("records"), [("driver_id", "Driver"), ("main_team", "Team"), ("n_dry_races", "Dry races + sprints"),
                                                  ("race_pace_adj", "Adj. pace %"), ("race_pace_adj_lo", "lo"),
                                                  ("race_pace_adj_hi", "hi"), ("teammate_gap_race", "Gap to team-mate %"),
                                                  ("quali_teammate_gap", "Quali gap to team-mate %")]),
            "\n_First ten rows of the ordering; the full table is served by `/api/driver-effects`._\n"]

    srows = []
    for dim, g in cond.groupby("dimension"):
        srows.append({"dimension": dim, "drivers": int(len(g)), "tau": float(g["tau"].iloc[0]) if "tau" in g else None,
                      **{s: int((g["status"] == s).sum()) for s in sorted(cond["status"].unique())}})
    out += ["## Condition-specific deviations\n",
            "Deviation of a driver from their own dry, car-adjusted expectation, shrunk towards zero with empirical Bayes "
            "(`tau` = estimated between-driver SD of the deviation). A driver is only *distinguishable* when the 90% "
            "posterior interval excludes zero.\n",
            table(srows, ["dimension", "drivers", "tau", *sorted(cond["status"].unique())]), "\n"]

    if corner.exists():
        ce = read_json(corner)
        rel = ce.get("specialisation_reliability") or {}
        if rel.get("overall"):
            names = {"overall": "overall corner delta to team-mate", "special": "slow-minus-fast corner specialisation"}
            out += ["## Corner-type specialisation\n",
                    "Is a driver's corner delta to their team-mate a repeatable trait? Each driver-season's qualifying "
                    f"sessions (≥ {rel.get('min_sessions')}) are split into odd and even rounds and the halves are correlated "
                    "across drivers; the "
                    "two-sided permutation p-value shuffles drivers between halves.\n",
                    table([{"measure": names.get(k, k), **rel[k]} for k in ("overall", "special") if k in rel],
                          [("measure", "Measure"), ("n_driver_seasons", "Driver-seasons"), ("split_half_r", "Split-half r"),
                           ("spearman_brown_reliability", "Spearman–Brown"), ("permutation_p", "Permutation p")]), ""]
    out += ["## Clusters (exploratory)\n",
            table(clusters["k_selection"], [("k", "k"), ("silhouette", "Silhouette"), ("bootstrap_ari", "Bootstrap ARI")]),
            f"\nChosen k = {clusters['chosen_k']} on {clusters['n_driver_seasons']} driver-seasons with ≥ "
            f"{clusters['min_races']} dry races. {clusters['interpretation']}\n",
            table([{"cluster": c["cluster"], "size": c["size"], "description": "; ".join(c["description"])}
                   for c in clusters["clusters"]], ["cluster", "size", "description"])]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------------------------------
# Model comparison
# --------------------------------------------------------------------------------------------------
def model_comparison(ctx: Ctx) -> str:
    run = ctx.run()
    out = [header("Model comparison", ctx, [f"evaluation_runs/{run['run_id']}.json", "evaluation_runs/*.json"])]
    out += [f"Run `{run['run_id']}`; dataset version `{json.dumps(run['dataset_version'])}`; seed {run['seed']}.\n",
            "Protocol: walk-forward by season (train on all earlier seasons, calibrate conformal intervals on the most "
            "recent training events, test on the next season). The last season is a holdout reported once; model "
            "selection uses development folds only. Intervals are 95% event-cluster bootstrap; `*` marks an interval "
            "that excludes zero.\n"]
    for horizon, h in run["horizons"].items():
        out.append(f"## Model A — lap pace, `{horizon}`\n")
        frows = []
        for fold in h["folds"]:
            for m, x in fold["metrics"].items():
                frows.append({"fold": fold["test_period"], "model": MODEL_LABELS.get(m, m), "n": x["n"], "mae": x["mae"],
                              "mae_ci": f"[{fmt(x['mae_ci']['lo'])}, {fmt(x['mae_ci']['hi'])}]", "rmse": x["rmse"],
                              "r2": x["r2"], "coverage": x.get("coverage"), "width": x.get("interval_width"),
                              "mae_s": x.get("mae_seconds")})
        out.append(table(frows, [("fold", "Test season"), ("model", "Model"), ("n", "Laps"), ("mae", "MAE %"),
                                 ("mae_ci", "95% CI"), ("rmse", "RMSE"), ("r2", "R²"), ("coverage", "90% PI coverage"),
                                 ("width", "PI width"), ("mae_s", "MAE s")],
                         formats={"coverage": lambda v: fmt(v, pct=True, nd=3), "mae_ci": str}))
        groups = [f["test_period"] for f in h["folds"]]
        series = {}
        for m in ["team_adjusted_form", "ridge", "spline_gam", "lightgbm"]:
            e = [f["metrics"][m]["mae"] for f in h["folds"]]
            series[MODEL_LABELS[m]] = (e, [f["metrics"][m]["mae_ci"]["lo"] for f in h["folds"]],
                                       [f["metrics"][m]["mae_ci"]["hi"] for f in h["folds"]])
        name = f"models_{horizon}_folds.png"
        F.grouped_dots(groups, series, ctx.figs / name, f"Walk-forward MAE by test season ({horizon})", "MAE, % of reference lap")
        out += ["\n" + figure(_rel(ctx, name), "MAE by fold and model"), "\n### Paired comparisons (MAE difference, % points)\n"]
        crows = []
        for part in ("development", "holdout"):
            for k, v in h["comparisons"][part].items():
                crows.append({"part": part, "comparison": k.replace("_vs_", " − "), "diff": ci(v)})
        out.append(table(crows, [("part", "Split"), ("comparison", "MAE(a) − MAE(b)"), ("diff", "Estimate [95% CI]")],
                         formats={"diff": str}))
        ek = h["event_kfold"]["metrics"]
        out += [f"\nSelected: **{MODEL_LABELS.get(h['selected_model'], h['selected_model'])}** — {h['selection_rule']}.\n",
                "Secondary split — event-held-out 5-fold (not temporal; shows how much the temporal split matters):\n",
                table([{"model": MODEL_LABELS.get(m, m), "mae": x["mae"], "coverage": x.get("coverage")} for m, x in ek.items()],
                      [("model", "Model"), ("mae", "MAE %"), ("coverage", "90% PI coverage")],
                      formats={"coverage": lambda v: fmt(v, pct=True, nd=3)}), "\n"]
    hg = run.get("horizon_gain_pre_race_vs_pre_event")
    if hg:
        out += ["### Value of the same weekend's qualifying\n",
                f"MAE(pre_race) − MAE(pre_event), selected models: development {ci(hg['development'], 4)}, "
                f"holdout {ci(hg['holdout'], 4)}.\n"]

    ab = ctx.optional("ablations.json")
    if ab:
        rows = []
        for c in ab["configs"]:
            rows.append({"name": c["name"].replace("+", " + "), "kind": c["kind"], "k": c["n_features"],
                         "dev": c["development"]["mae"], "dev_vs": ci(c["development"].get("vs_full"), 4),
                         "hold": c["holdout"]["mae"], "hold_vs": ci(c["holdout"].get("vs_full"), 4)})
        out += ["## Feature-group ablations (LightGBM, pre-event)\n",
                f"Each configuration vs the full model (`{ab['full_config']}`) on identical laps; positive = worse "
                "than full.\n",
                table(rows, [("name", "Configuration"), ("kind", "Kind"), ("k", "Features"), ("dev", "Dev MAE"),
                             ("dev_vs", "Δ vs full (dev)"), ("hold", "Holdout MAE"), ("hold_vs", "Δ vs full (holdout)")],
                      nd=4, formats={"dev_vs": str, "hold_vs": str}), "\n"]

    ce = ctx.optional("corner_experiments.json")
    if ce and "sector_model" in ce:
        sm = ce["sector_model"]
        out += ["## Model B — sector pace with driver corner profiles\n",
                table([{"model": k, "mae": v} for k, v in sm["pooled_mae"].items()], [("model", "Model"), ("mae", "Pooled MAE %")], nd=4),
                f"\nProfile − base: LightGBM {ci(sm['profile_minus_base']['lightgbm'], 4)}, Ridge "
                f"{ci(sm['profile_minus_base']['ridge'], 4)}. Profile coverage {fmt(sm['profile_coverage'], pct=True, nd=3)} of "
                "sector rows.\n"]
    td = ctx.optional("tyre_degradation.json")
    if td:
        out += ["## Model C — tyre degradation\n",
                f"{td['protocol']}; {td['n_predicted_laps']:,} predicted laps in {td['n_events']} events.\n",
                table([{"model": k, "mae": v, "mae_s": td["mae_s"][k]} for k, v in td["mae_pct"].items()],
                      [("model", "Slope model"), ("mae", "MAE %"), ("mae_s", "MAE s")], nd=4),
                "\n" + table([{"c": k.replace("_vs_", " − "), "v": ci(v, 4)} for k, v in td["comparisons"].items()],
                             [("c", "Comparison"), ("v", "MAE difference [95% CI]")], formats={"v": str}), "\n"]
    qm = ctx.optional("quali_model.json")
    if qm:
        out += ["## Model F — pre-event qualifying gap\n",
                f"Target: {qm['target']}; {qm['n_rows']:,} driver-events. {qm['note']}\n",
                table([{"model": k, **v} for k, v in qm["models"].items()],
                      [("model", "Model"), ("mae", "MAE %"), ("mean_event_spearman", "Mean event Spearman"),
                       ("pole_hit_rate", "Pole hit rate"), ("top3_overlap", "Top-3 overlap"), ("n_events", "Events")]),
                f"\nLightGBM − baseline MAE: {ci(qm['lightgbm_vs_baseline'])}.\n"]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------------------------------
# Error analysis
# --------------------------------------------------------------------------------------------------
def error_analysis(ctx: Ctx) -> str:
    out = [header("Error analysis", ctx, ["evaluation_runs/error_analysis_*.json"])]
    for horizon in ("pre_event", "pre_race"):
        ea = ctx.optional(f"error_analysis_{horizon}.json")
        if not ea:
            continue
        out += [f"## `{horizon}` — {MODEL_LABELS.get(ea['model'], ea['model'])} (run `{ea['run_id']}`)\n",
                " ".join(ea["notes"]) + "\n", "### Contrasts (MAE difference, % points, event-cluster bootstrap 95% CI)\n",
                table([{"by": c["by"], "c": f"{c['a']} − {c['b']}", "v": ci(c)} for c in ea["contrasts"]],
                      [("by", "Dimension"), ("c", "Groups"), ("v", "Estimate [95% CI]")], formats={"v": str}), ""]
        for dim, rows in ea["breakdowns"]["holdout"].items():
            if dim == "constructor_id" or not rows:
                continue
            out += [f"### Holdout by {dim.replace('_', ' ')}\n",
                    table(rows, [("group", "Group"), ("n_laps", "Laps"), ("n_events", "Events"), ("mae", "MAE %"),
                                 ("bias", "Bias"), ("baseline_mae", "Baseline MAE"), ("skill_vs_baseline", "Skill vs baseline"),
                                 ("coverage_90", "90% PI coverage"), ("interval_width", "PI width")],
                          formats={"coverage_90": lambda v: fmt(v, pct=True, nd=3),
                                   "skill_vs_baseline": lambda v: fmt(v, pct=True, nd=3)}), ""]
        out += ["### Largest event errors (holdout)\n",
                table(ea["worst_events"].get("holdout", []),
                      [("event_id", "Event"), ("name", "Name"), ("n_laps", "Laps"), ("mae", "MAE %"), ("bias", "Bias"),
                       ("baseline_mae", "Baseline MAE"), ("wet_share", "Wet share"), ("ratio_to_median_event", "× median event")],
                      formats={"wet_share": lambda v: fmt(v, pct=True, nd=3)}),
                "\n### Team bias by half-season (prediction − actual; positive = team faster than predicted)\n",
                table(ea["team_drift"][:12], [("season", "Season"), ("constructor_id", "Team"), ("bias_first_half", "First half"),
                                              ("bias_second_half", "Second half"), ("change", "Change"), ("n_laps", "Laps")]),
                "\n### Ordering of drivers within a session (all walk-forward test seasons; Spearman of mean predicted vs actual pace)\n",
                table([{"model": MODEL_LABELS.get(k, k), **v} for k, v in ea["session_ranking"].items()],
                      [("model", "Model"), ("n_sessions", "Sessions"), ("median", "Median"), ("q25", "q25"), ("q75", "q75"),
                       ("share_below_0_5", "Share < 0.5")], formats={"share_below_0_5": lambda v: fmt(v, pct=True, nd=3)}), ""]
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------------------------------
# Explainability
# --------------------------------------------------------------------------------------------------
def explainability(ctx: Ctx) -> str:
    run = ctx.run()
    out = [header("Explainability", ctx, [f"evaluation_runs/{run['run_id']}.json", "models/*/explanation_validation.json"])]
    out += ["All explanations describe how the fitted models use their inputs. They are associations learned from "
            "observational data and never causal effects.\n"]
    for horizon, h in run["horizons"].items():
        ge = h["global_explanations"]
        out.append(f"## `{horizon}`: global explanations ({ge['explained_on']}, {ge['n_rows']:,} laps)\n")
        perm = ge["lightgbm_permutation"]
        name = f"explain_{horizon}_permutation.png"
        F.hbar([p["group"].replace("_", " ") for p in perm], [p["mae_increase"] for p in perm], ctx.figs / name,
               "Grouped permutation importance (MAE increase when a group is shuffled)", "MAE increase, % points",
               value_fmt="{:.3f}")
        out += [figure(_rel(ctx, name), "Grouped permutation importance"), "",
                table(ge["lightgbm_contributions"]["features"][:12],
                      [("feature", "Feature"), ("group", "Group"), ("mean_abs", "Mean |SHAP| %"), ("mean_signed", "Mean SHAP %")]),
                f"\nLightGBM vs Ridge importance ranking: Spearman "
                f"{fmt(ge['method_agreement'].get('spearman_lightgbm_vs_ridge'), 2)} over "
                f"{len(ge['method_agreement'].get('features_compared', []))} shared features.\n"]
        if horizon == "pre_event" and ge.get("ale"):
            panels = [(a["feature"], a["grid"], np.asarray(a["ale"]) - np.mean(a["ale"])) for a in ge["ale"][:6]]
            F.small_multiples([(n, x, list(y)) for n, x, y in panels], ctx.figs / "explain_ale.png",
                              "Accumulated local effects (centred)", "effect on rel. pace %")
            out += [figure(_rel(ctx, "explain_ale.png"), "ALE curves",
                           "ALE curves show the model's average response to one input, accounting for correlated inputs; "
                           "they are not causal effects."), ""]
        version = production_version(ctx.paths.models, f"{LP.TASK}_{horizon}")
        vf = ctx.paths.models / version / "explanation_validation.json" if version else None
        if vf and vf.exists():
            v = read_json(vf)
            gs, ls = v.get("global_stability", {}), v.get("local_stability", {})
            checks = [
                {"check": "Additivity (base + contributions − prediction), max abs", "value": _sci(v["additivity_max_abs_error"])},
                {"check": "TreeSHAP vs `shap` library, max abs difference",
                 "value": _sci(v.get("treeshap_vs_shap_library_max_abs_diff"))},
                {"check": f"Global ranking stability across {gs.get('n_models')} bootstrap refits (mean / min Spearman)",
                 "value": f"{fmt(gs.get('mean_pairwise_spearman'), 2)} / {fmt(gs.get('min_pairwise_spearman'), 2)}"},
                {"check": "Top-5 feature sets across refits (mean Jaccard)", "value": fmt(gs.get("mean_top5_jaccard"), 2)},
                {"check": "Local top-3 contribution sign agreement across refits", "value": fmt(ls.get("top3_sign_agreement"), 3)},
                {"check": "Mean SD of local top-3 contributions across refits (%)",
                 "value": fmt(ls.get("mean_sd_of_top3_contributions_pct"), 3)},
                {"check": "Agreement with the other horizon's model (Spearman of importance)",
                 "value": fmt((v.get("cross_version") or {}).get("spearman_global_importance"), 2)},
                {"check": "Agreement with Ridge (Spearman of mean |contribution| / sign agreement)",
                 "value": f"{fmt((v.get('vs_ridge') or {}).get('spearman_mean_abs'), 2)} / "
                          f"{fmt((v.get('vs_ridge') or {}).get('sign_agreement_of_mean_effect'), 2)}"},
            ]
            sens = list(v["sensitivity_5pct_sd"].items())[:5]
            out += [f"### Explanation validation (`{version}`, {v['sample']}, {v['n_rows']:,} laps)\n",
                    table(checks, [("check", "Check"), ("value", "Result")], formats={"value": str}),
                    "\nTop-5 frequency across refits: " + ", ".join(f"`{k}` {fmt(x, pct=True, nd=2)}"
                                                                    for k, x in gs.get("top5_frequency", {}).items()) + ".\n",
                    "Sensitivity (mean |Δprediction| % for ±5% SD perturbations): "
                    + ", ".join(f"`{k}` {fmt(x['mean_abs_change_pct'], 3)}" for k, x in sens) + ".\n",
                    "Correlated pairs whose credit SHAP may split arbitrarily: "
                    + ", ".join(f"`{p['a']}`/`{p['b']}` ({fmt(p['spearman'], 2)})" for p in v["correlated_pairs"][:6]) + ".\n"]
    ex = _worked_example(ctx)
    if ex:
        out += ["## Worked local explanation\n", ex]
    return "\n".join(out) + "\n"


def _sci(v) -> str:
    return "–" if v is None else f"{v:.1e}"


def _worked_example(ctx: Ctx) -> str | None:
    from apexlens.predictions.service import PredictionService
    from apexlens.schemas.api import LapTimeRequest

    lf = read_table(ctx.paths.gold("lap_features"), columns=["event_id", "season", "circuit_id", "driver_id"])
    prof = read_table(ctx.paths.gold("driver_profiles"))
    last_event = sorted(lf["event_id"].unique())[-1]
    latest = prof[prof["season"] == prof["season"].max()].dropna(subset=["race_pace_adj"])
    drivers = set(lf.loc[lf["event_id"] == last_event, "driver_id"])
    latest = latest[latest["driver_id"].isin(drivers)].sort_values("race_pace_adj")
    if latest.empty:
        return None
    driver = latest.iloc[len(latest) // 2]["driver_id"]
    req = LapTimeRequest(driver_id=driver, as_of_event_id=last_event, compound="MEDIUM", tyre_life_laps=12, race_progress=0.5)
    try:
        r = PredictionService(ctx.paths).predict_lap(req)
    except Exception as exc:  # noqa: BLE001 - the report should still build
        return f"_Worked example unavailable: {exc}_\n"
    p = r["prediction"]
    rows = sorted(r["contributions"], key=lambda c: -abs(c["contribution_pct"]))[:8]
    for c in rows:
        c["value_str"] = f"{c['value']:g}" if isinstance(c["value"], (int, float)) else str(c["value"])
    return "\n".join([
        f"Scenario: `{driver}` before event `{last_event}` ({r['inputs']['circuit_name']}), medium tyres 12 laps old, half "
        f"race distance, `{r['horizon']}` model `{r['model_version']}`.\n",
        f"Prediction {fmt(p['value_pct'], 3, signed=True)}% of the reference lap "
        f"(90% interval {fmt(p['interval']['lo_pct'], 2, signed=True)} … {fmt(p['interval']['hi_pct'], 2, signed=True)}; "
        f"model spread {fmt((p.get('model_uncertainty') or {}).get('sd_pct'), 3)}% SD across bootstrap refits).\n",
        table(rows, [("label", "Input"), ("value_str", "Value"), ("contribution_pct", "Contribution %")],
              formats={"value_str": str}),
        "\n> " + r["narrative"].replace("\n", "\n> ") + "\n",
        "Warnings: " + ("; ".join(r["warnings"]) if r["warnings"] else "none") + ".\n",
    ])


# --------------------------------------------------------------------------------------------------
# Race strategy planner (Model G)
# --------------------------------------------------------------------------------------------------
def race_strategy(ctx: Ctx) -> str:
    b = ctx.optional("strategy_backtest.json")
    out = [header("Race strategy planner — backtest", ctx, ["evaluation_runs/strategy_backtest.json"])]
    if not b:
        return "\n".join(out + ["_Not run yet: `python scripts/evaluate_models.py --only strategy`._\n"])
    out += ["Every race from the second ingested season on is planned with data available before its start "
            "(strategy parameters from earlier races, a lap-pace model trained on earlier seasons, weather from the "
            "weekend's sessions) and compared with what happened. Method: `docs/methodology.md` §7, code: "
            "`src/apexlens/strategy/`.\n",
            f"{b['races_total']} races; {b['races_strategy_evaluated']} dry races without a red flag are used for "
            f"the strategy comparison (excluded: wet {', '.join(b['excluded_from_strategy']['wet']) or '–'}; "
            f"red flag {', '.join(b['excluded_from_strategy']['red_flag']) or '–'}).\n"]
    names = {"stops_match": "Stop count = top-10's most common", "plan_match": "Stops + set of compounds = top-10's most common",
             "start_match": "Starting compound = top-10's most common", "stops_match_winner": "Stop count = winner's",
             "first_stop_error": "First stop vs top-10 with that stop count (laps)",
             "window_hit": "Top-10 first stops inside the planned window"}
    for part, label_ in (("all", "All evaluated races"), ("green", "Races without safety car or VSC"),
                         ("safety_car_or_vsc", "Races with a safety car or VSC")):
        blk = b["strategy"][part]
        rows = []
        for k, name in names.items():
            rows.append({"metric": name, "physical": _ci_str(blk["physical"].get(k), k),
                         "calibrated": _ci_str(blk["calibrated"].get(k), k),
                         "previous": _ci_str(blk["previous_edition"].get(k), k) if k in blk["previous_edition"] else "–",
                         "common": _ci_str(blk["most_common_stops"].get(k), k) if k in blk["most_common_stops"] else "–"})
        out += [f"## {label_} ({blk['races']} races)\n",
                table(rows, [("metric", "Measure"), ("physical", "Planner (lap-time costs only)"),
                             ("calibrated", "Planner (calibrated)"), ("previous", "Copy previous race here"),
                             ("common", "Most common stop count so far")],
                      formats={k: str for k in ("physical", "calibrated", "previous", "common")}), ""]
        diffs = [{"c": f"calibrated − previous race: {k.replace('_', ' ')}", "v": ci(v)}
                 for k, v in blk["calibrated_minus_previous_edition"].items()]
        diffs += [{"c": f"calibrated − physical: {k.replace('_', ' ')}", "v": ci(v)}
                  for k, v in blk["calibrated_minus_physical"].items()]
        out += [table(diffs, [("c", "Paired difference (same races)"), ("v", "Estimate [95% CI]")], formats={"v": str}), ""]
    cal = b.get("latest_calibration") or {}
    out += ["## Calibration\n",
            f"Hidden costs fitted on earlier races (latest fit, {cal.get('races', 0)} races): "
            f"{fmt(cal.get('stop_s'), 1)} s per pit stop (track position, traffic) and {fmt(cal.get('soft_stint_s'), 1)} s per "
            "SOFT stint (set availability after qualifying, graining). Agreement with the top-10's most common plan on "
            f"those races: {fmt(cal.get('agreement'), pct=True, nd=3)}.\n"]
    fo = b["finishing_order"]
    rows = [{"model": {"blend": "Planner (grid + pace blend)", "grid_order": "Grid order", "pace_order": "Pace order"}[k],
             **{m: _ci_str(v.get(m), m) for m in ("spearman", "winner_correct", "podium_overlap", "position_mae")}}
            for k, v in fo.items()]
    out += ["## Finishing order\n",
            table(rows, [("model", "Prediction"), ("spearman", "Rank correlation"), ("winner_correct", "Winner correct"),
                         ("podium_overlap", "Podium overlap"), ("position_mae", "Position error")],
                  formats={m: str for m in ("spearman", "winner_correct", "podium_overlap", "position_mae")}),
            f"\nBlend − grid order, rank correlation: {ci(b['blend_minus_grid_spearman'])}. Classified finishers only.\n"]
    lr = b.get("lap_replay") or {}
    if lr:
        out += ["## Lap times\n",
                f"The top-10's actual tyre sequences replayed through the model ({lr['drivers']} driver-races, "
                f"{lr['laps']:,} representative laps): mean absolute error {_ci_str(lr['model_mae_s'], 's')} s per lap vs "
                f"{_ci_str(lr['constant_pace_mae_s'], 's')} s for a constant lap time at the predicted pace "
                f"(difference {ci(lr['model_minus_constant'])}). Most of the remaining error is the level of the race's "
                "lap times (estimated from qualifying), not the shape over the race.\n"]
    td = ctx.optional("tyre_degradation.json")
    if td and "temp_vs_circuit" in td.get("comparisons", {}):
        out += ["## Temperature\n",
                "Adding a within-circuit track-temperature adjustment to the degradation slopes changed held-out stint "
                f"predictions by {ci(td['comparisons']['temp_vs_circuit'], 4)} % points (positive = worse), so the planner "
                "does not adjust tyre wear for temperature.\n"]
    races = [{"event": r["event_id"], "circuit": r["circuit_id"], "plan": r["calibrated"]["plan"],
              "actual": (r.get("actual_modal_plan") or "–").replace("|", " stop(s): "), "winner": r.get("winner_strategy") or "–",
              "ok": "yes" if (r["calibrated"].get("plan_match")) else ("no" if r.get("strategy_evaluated") else "not evaluated"),
              "sc": "SC/VSC" if not r["green"] else ""} for r in b["races"]]
    out += ["## Race by race\n",
            table(races, [("event", "Race"), ("circuit", "Circuit"), ("plan", "Planned (calibrated)"),
                          ("actual", "Top-10 most common"), ("winner", "Winner"), ("ok", "Match"), ("sc", "Neutralised")],
                  formats={k: str for k in ("plan", "actual", "winner", "ok", "sc")})]
    return "\n".join(out) + "\n"


def _ci_str(c: dict | None, kind: str) -> str:
    if not c or c.get("estimate") is None:
        return "–"
    if kind in ("first_stop_error", "position_mae", "spearman", "s"):
        return f"{c['estimate']:.2f} [{c['lo']:.2f}, {c['hi']:.2f}]"
    return f"{100 * c['estimate']:.0f}% [{100 * c['lo']:.0f}, {100 * c['hi']:.0f}]"


# --------------------------------------------------------------------------------------------------
# Generated docs
# --------------------------------------------------------------------------------------------------
DICT_TABLES = {
    "silver": ["events", "sessions", "drivers", "constructors", "circuits", "race_results", "qualifying_results",
               "laps", "stints", "weather_observations", "race_control_events", "track_status_events", "telemetry_laps",
               "telemetry_samples", "corner_markers", "session_drivers"],
    "gold": ["all_laps_relative", "lap_features", "driver_session_summary", "driver_event_form", "driver_profiles",
             "driver_condition_effects", "driver_session_adjusted", "team_season_effects", "driver_clusters",
             "corner_definitions", "corner_metrics", "driver_corner_profiles", "circuit_profiles", "sector_profiles",
             "track_maps", "tyre_stints", "tyre_degradation", "tyre_degradation_circuit", "driver_tyre_effects"],
}


def data_dictionary(ctx: Ctx) -> str:
    out = [header("Data dictionary", ctx, ["data/processed (silver)", "data/features (gold)"]),
           "Generated from the stored Parquet tables: column, type, share non-null and an example value. "
           "Feature semantics are in `docs/feature_definitions.md`; sources and licences in `docs/data_sources.md`.\n"]
    for layer, tables in DICT_TABLES.items():
        out.append(f"## {layer.capitalize()} layer\n")
        for t in tables:
            path = ctx.paths.silver(t) if layer == "silver" else ctx.paths.gold(t)
            if not path.exists():
                continue
            df = read_table(path)
            if t == "telemetry_samples":
                df = df.head(200_000)
            rows = []
            for c in df.columns:
                s = df[c]
                nn = s.dropna()
                ex = nn.iloc[0] if len(nn) else None
                if isinstance(ex, float):
                    ex = round(ex, 4)
                exs = str(ex)
                rows.append({"column": f"`{c}`", "dtype": str(s.dtype), "non_null": float(s.notna().mean()) if len(s) else None,
                             "example": exs[:40] + ("…" if len(exs) > 40 else "")})
            out += [f"### `{t}` — {len(df):,} rows{' (first 200k sampled)' if t == 'telemetry_samples' else ''}\n",
                    table(rows, [("column", "Column"), ("dtype", "Type"), ("non_null", "Non-null"), ("example", "Example")],
                          formats={"non_null": lambda v: fmt(v, pct=True, nd=3), "example": str}), ""]
    return "\n".join(out) + "\n"


def feature_definitions(ctx: Ctx) -> str:
    out = [header("Feature definitions", ctx, ["src/apexlens/features/definitions.py"]),
           "Each feature with its meaning, unit, derivation, sources, availability and known limitations. "
           "Availability: `static` (known before the season), `pre_event` (only events that finished before the "
           "event's first session), `pre_race` (adds the same weekend's qualifying), `scenario` (a condition set by "
           "the user or observed on the lap), `target` (never an input).\n"]
    by_group: dict[str, list] = {}
    for name, f in FEATURES.items():
        by_group.setdefault(f["group"], []).append((name, f))
    for group, items in by_group.items():
        out.append(f"## {group.replace('_', ' ').capitalize()}\n")
        out.append(table([{"name": f"`{n}`", "unit": f.get("unit", ""), "availability": f.get("availability", ""),
                           "description": f.get("description", ""), "derivation": f.get("derivation", ""),
                           "sources": ", ".join(f.get("sources", [])), "limitations": f.get("limitations", "")}
                          for n, f in items],
                         [("name", "Feature"), ("unit", "Unit"), ("availability", "Availability"), ("description", "Description"),
                          ("derivation", "Derivation"), ("sources", "Sources"), ("limitations", "Limitations")]))
        out.append("")
    return "\n".join(out) + "\n"


def model_card(ctx: Ctx) -> str:
    run = ctx.run()
    failure_modes: list[str] = []
    out = [header("Model card — ApexLens lap-pace models (Model A)", ctx,
                  [f"evaluation_runs/{run['run_id']}.json", "models/*/metadata.json"])]
    out += ["## Intended use\n",
            "Research and education: estimating a driver's expected representative race-lap pace relative to the session "
            "reference under stated conditions, comparing drivers under a common scenario, and explaining which inputs the "
            "model relied on. **Not** for betting, safety, team operations, or any claim about causes of performance.\n",
            "## Target\n",
            "`rel_pace_pct` = 100 × (lap time / session reference − 1) for representative race and sprint laps, where the "
            "session reference is the median clean lap of all drivers in that session. Negative is faster. Seconds shown in "
            "the UI are a conversion using the circuit's median reference lap.\n"]
    for horizon, h in run["horizons"].items():
        version = h["versions"][h["selected_model"]]
        _, meta = load_artifact(ctx.paths.models, version)
        hold, dev = meta["test_metrics"]["holdout"], meta["test_metrics"]["development"]
        conf = meta["conformal"]
        out += [f"## `{horizon}` — `{version}`\n",
                f"* Model: {MODEL_LABELS.get(meta['model'], meta['model'])}; selected by {h['selection_rule']}.",
                f"* Training period: {meta['train_period']}; calibration events: {len(meta['calibration_events'])}.",
                f"* Inputs: {len(meta['features']['numeric'])} numeric + {len(meta['features']['categorical'])} categorical "
                f"(feature-set version `{meta['feature_set_version']}`).",
                f"* Intervals: {conf.get('method', 'split conformal')} at level {conf.get('level')}, separate for dry and wet laps.",
                f"* Dataset version: `{json.dumps(meta['dataset_version'])}`.\n",
                table([{"split": "development (pooled walk-forward)", **dev}, {"split": f"holdout season {h['holdout_season']}", **hold}],
                      [("split", "Split"), ("n", "Laps"), ("mae", "MAE %"), ("rmse", "RMSE"), ("r2", "R²"), ("bias", "Bias"),
                       ("coverage", "90% PI coverage"), ("interval_width", "PI width")],
                      formats={"coverage": lambda v: fmt(v, pct=True, nd=3)}), ""]
        bc = dev.get("by_condition") or {}
        if bc:
            out += [table([{"condition": k, **v} for k, v in bc.items()],
                          [("condition", "Condition (development)"), ("n", "Laps"), ("mae", "MAE %"), ("coverage", "90% PI coverage")],
                          formats={"coverage": lambda v: fmt(v, pct=True, nd=3)}), ""]
    for horizon, h in run["horizons"].items():
        sel = h["selected_model"]
        tied = [k.split("_vs_")[1] for k, v in h["comparisons"]["holdout"].items() if k.startswith(f"{sel}_vs_")
                and not v["significant"]]
        if tied:
            failure_modes.append(f"`{horizon}`: on the holdout season, {MODEL_LABELS.get(sel, sel)} is not significantly "
                                 "better than " + " or ".join(MODEL_LABELS.get(t, t) for t in tied)
                                 + "; the simpler model would serve almost as well.")
    out += ["## Known failure modes\n",
            "* Intervals under-cover nominal 90% (most clearly on wet laps); treat them as optimistic. See "
            "`reports/model_comparison.md` and `reports/error_analysis.md`.",
            "* Form features lag in-season car development; a team that upgrades strongly is predicted too slow for several events.",
            "* New circuits, rookies and wet races have little or no history; the API flags these cases as extrapolation.",
            *[f"* {m}" for m in failure_modes],
            "* The 2026 season introduced new technical regulations. 2026 races are included as they happen, but most "
            "training laps come from 2022–2025 cars; compare the 2026 fold with earlier ones before relying on 2026 "
            "predictions.\n",
            "## Ethical and legal notes\n",
            "Timing data is unofficial (FastF1 export); F1DB is CC BY 4.0. Driver comparisons are statistical summaries "
            "with uncertainty, not judgements of people. ApexLens is not associated with Formula 1, the FIA or any team.\n"]
    return "\n".join(out) + "\n"


def index(ctx: Ctx, written: list[str]) -> str:
    run = ctx.run()
    out = [header("ApexLens reports", ctx, ["all outputs"]),
           f"Latest evaluation run `{run['run_id']}`; dataset `{json.dumps(run['dataset_version'])}`.\n",
           "| Report | Contents |", "|---|---|"]
    desc = {
        "coverage_report.md": "Sources, per-season coverage, quality checks, entity mapping",
        "eda.md": "Volumes, exclusions, target distribution, compounds, weather, telemetry quality",
        "feature_engineering.md": "Model inputs, availability, missingness, leakage controls, correlations",
        "driver_profiles.md": "Variance components, team-adjusted pace, condition effects, clusters",
        "model_comparison.md": "Models A–F, walk-forward metrics, paired comparisons, ablations",
        "error_analysis.md": "Where the models fail: conditions, tyre age, experience, events, teams",
        "explainability.md": "Global and local explanations and their validation",
        "race_strategy.md": "Race week planner: strategy, pit windows and finishing order vs what happened",
    }
    for w in written:
        if w in desc:
            out.append(f"| [{w}]({w}) | {desc[w]} |")
    out += ["\nGenerated documentation: `docs/data_dictionary.md`, `docs/feature_definitions.md`, `docs/model_card.md`.\n",
            "Regenerate everything after new data or training:\n",
            "```bash\nmake features train evaluate reports\n```"]
    return "\n".join(out) + "\n"
