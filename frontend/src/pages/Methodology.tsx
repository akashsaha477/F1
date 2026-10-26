import { useJson, useModels } from "../api/hooks";
import { Card, ErrorState, KV, LoadingState, PageHeader, StatusPill } from "../components/ui";
import { fmtNum, fmtSigned, titleFromId } from "../lib/format";

type Json = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const MODEL_LABEL: Record<string, string> = {
  hist_group_median: "Historical group median", team_adjusted_form: "Team-adjusted form", ridge: "Ridge",
  spline_gam: "Spline GAM", lightgbm: "LightGBM",
};

function Section({ title, children, subtitle }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return <Card title={title} subtitle={subtitle}>{children}</Card>;
}

export default function MethodologyPage() {
  const meth = useJson<Json>(["methodology"], "/methodology");
  const sources = useJson<Json>(["sources"], "/sources");
  const coverage = useJson<Json>(["coverage"], "/data-coverage");
  const features = useJson<Json>(["features"], "/features");
  const evaluation = useJson<Json>(["evaluation"], "/evaluation");
  const experiments = useJson<Json>(["experiments"], "/experiments");
  const clusters = useJson<Json>(["clusters"], "/driver-clusters");
  const models = useModels();
  const prodVersion = models.data?.production?.lap_pace_pre_event;
  const validation = useJson<Json>(["validation", prodVersion], prodVersion ? `/models/${prodVersion}/explanation-validation` : null);

  if (meth.isLoading) return <LoadingState />;
  if (meth.error) return <ErrorState error={meth.error} />;
  const m = meth.data!;
  const ev = evaluation.data;
  const exp = experiments.data;

  return (
    <div className="space-y-5">
      <PageHeader title="Data & methodology"
        description="How every number in ApexLens is produced: sources and licences, coverage, cleaning rules, feature definitions, models, evaluation protocol, results, model versions and limitations." />

      <Section title="Data sources" subtitle="Every retrieval is logged with provider, endpoint, time, hash and status">
        {sources.data && (
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-ink-muted"><tr><th className="py-1">Source</th><th>Role</th><th>Licence / terms</th><th>Retrievals</th></tr></thead>
            <tbody>{Object.entries(sources.data.catalog as Json).map(([k, v]) => {
              const r = (sources.data!.retrievals as Json[]).filter((x) => x.provider === k);
              return (
                <tr key={k} className="border-t border-line align-top">
                  <td className="py-1"><a className="text-accent" href={v.url} target="_blank" rel="noreferrer">{v.name}</a></td>
                  <td className="text-ink-2">{v.role}<div className="text-[11px] text-ink-muted">{v.notes}</div></td>
                  <td className="text-xs text-ink-2">{v.licence}</td>
                  <td className="text-xs tabular">{r.length ? r.map((x) => `${x.dataset}: ${x.n_ok} ok${x.n_missing ? `, ${x.n_missing} missing` : ""}${x.n_error ? `, ${x.n_error} errors` : ""}`).join("; ") : "—"}</td>
                </tr>
              );
            })}</tbody>
          </table>
        )}
      </Section>

      {coverage.data && (
        <Section title="Coverage" subtitle={`Generated ${coverage.data.generated_at}`}>
          <table className="w-full text-left text-sm tabular">
            <thead className="text-xs text-ink-muted"><tr><th className="py-1">Season</th><th>Sessions with timing</th><th>Laps</th><th>Clean</th><th>Valid tyre info</th><th>Weather</th><th>Telemetry laps</th><th>Wet clean laps</th></tr></thead>
            <tbody>{(coverage.data.per_season as Json[]).map((s) => (
              <tr key={s.season} className="border-t border-line"><td className="py-1">{s.season}</td><td>{s.sessions_with_timing} / {s.f1db_sessions}</td>
                <td>{s.laps}</td><td>{s.clean_laps}</td><td>{s.pct_laps_valid_tyre_info}%</td><td>{s.pct_laps_with_weather}%</td><td>{s.telemetry_laps}</td><td>{s.wet_clean_laps}</td></tr>
            ))}</tbody>
          </table>
          <div className="mt-3 text-xs text-ink-2">Quality checks failed: {(coverage.data.quality.failed_checks as Json[]).map((c) => `${c.check.replace(/_/g, " ")} (${c.severity}, ${c.n_rows})`).join("; ")}.
            {" "}Sessions excluded for fatal failures: {(coverage.data.quality.partitions_with_fatal_failures as Json[]).map((f) => f.partition).join(", ") || "none"}.</div>
        </Section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Cleaning rules">
          <p className="mb-2 text-sm text-ink-2">{m.cleaning.clean_lap} {m.cleaning.representative_lap}</p>
          <p className="mb-2 text-sm text-ink-2">{m.cleaning.session_reference}</p>
          <KV rows={Object.entries(m.cleaning.lap_exclusions as Json).map(([k, v]) => [k.replace(/_/g, " "), String(v)])} />
          <p className="mt-2 text-xs text-ink-muted">{m.cleaning.fatal_vs_warning}</p>
        </Section>
        <Section title="Feature definitions" subtitle="availability: static / pre-event / pre-race / scenario / target">
          <div className="max-h-[28rem] overflow-y-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-surface-1 text-ink-muted"><tr><th className="py-1">Feature</th><th>Group</th><th>Unit</th><th>Available</th><th>Definition</th></tr></thead>
              <tbody>{Object.entries((features.data ?? {}) as Json).map(([k, f]) => (
                <tr key={k} className="border-t border-line align-top"><td className="py-1 font-mono text-[11px]">{k}</td><td>{f.group}</td><td>{f.unit}</td><td>{f.availability}</td>
                  <td className="text-ink-2">{f.description}. <span className="text-ink-muted">{f.derivation}. {f.limitations}</span></td></tr>
              ))}</tbody>
            </table>
          </div>
        </Section>
      </div>

      {ev && (
        <Section title="Model A evaluation (lap pace)" subtitle={`Run ${ev.run_id}. Walk-forward by season; ${ev.horizons.pre_event?.holdout_season} is the untouched holdout. MAE in % of the session reference lap.`}>
          {Object.entries(ev.horizons as Json).map(([h, r]) => (
            <div key={h} className="mb-4">
              <div className="mb-1 text-sm font-medium">{h === "pre_race" ? "Pre-race horizon" : "Pre-event horizon"} — selected: {MODEL_LABEL[r.selected_model]}</div>
              <table className="w-full text-left text-sm tabular">
                <thead className="text-xs text-ink-muted"><tr><th className="py-1">Model</th><th>Dev MAE [95% CI]</th><th>Holdout MAE [95% CI]</th><th>Holdout ≈ s</th><th>Holdout R²</th><th>90% coverage (dry / wet)</th></tr></thead>
                <tbody>{Object.entries(r.pooled.holdout as Json).map(([k, v]) => {
                  const d = r.pooled.development[k];
                  return (
                    <tr key={k} className="border-t border-line"><td className="py-1">{MODEL_LABEL[k] ?? k}</td>
                      <td>{fmtNum(d.mae, 3)} [{fmtNum(d.mae_ci.lo, 3)}, {fmtNum(d.mae_ci.hi, 3)}]</td>
                      <td>{fmtNum(v.mae, 3)} [{fmtNum(v.mae_ci.lo, 3)}, {fmtNum(v.mae_ci.hi, 3)}]</td>
                      <td>{fmtNum(v.mae_seconds, 3)}</td><td>{fmtNum(v.r2, 3)}</td>
                      <td>{fmtNum(v.by_condition.dry?.coverage * 100, 1)}% / {fmtNum(v.by_condition.wet?.coverage * 100, 1)}%</td></tr>
                  );
                })}</tbody>
              </table>
              <ul className="mt-2 space-y-1 text-xs">
                {Object.entries(r.comparisons.holdout as Json).map(([k, c]) => (
                  <li key={k} className="flex items-center gap-2"><StatusPill status={c.significant ? "good" : "info"}>{c.significant ? "significant" : "not significant"}</StatusPill>
                    <span className="text-ink-2">{k.replace(/_/g, " ")} (holdout): ΔMAE {fmtSigned(c.estimate, 3)} [{fmtSigned(c.lo, 3)}, {fmtSigned(c.hi, 3)}]</span></li>
                ))}
              </ul>
              <div className="mt-2 text-xs text-ink-2">Grouped permutation importance (holdout, ΔMAE): {(r.global_explanations.lightgbm_permutation as Json[]).map((g) => `${g.group} ${fmtNum(g.mae_increase, 3)}`).join(" · ")}</div>
            </div>
          ))}
          {ev.horizon_gain_pre_race_vs_pre_event && (
            <p className="text-xs text-ink-2">Adding the weekend's qualifying (pre-race vs pre-event): ΔMAE holdout {fmtSigned(ev.horizon_gain_pre_race_vs_pre_event.holdout.estimate, 3)} [{fmtSigned(ev.horizon_gain_pre_race_vs_pre_event.holdout.lo, 3)}, {fmtSigned(ev.horizon_gain_pre_race_vs_pre_event.holdout.hi, 3)}].</p>
          )}
        </Section>
      )}

      {exp && (
        <div className="grid gap-4 lg:grid-cols-2">
          {exp.ablations && (
            <Section title="Ablations (LightGBM, pre-event)" subtitle="MAE on the holdout season; Δ vs the full feature set with 95% CI">
              <table className="w-full text-left text-xs tabular">
                <thead className="text-ink-muted"><tr><th className="py-1">Configuration</th><th>Features</th><th>Holdout MAE</th><th>Δ vs full</th></tr></thead>
                <tbody>{(exp.ablations.configs as Json[]).map((c) => (
                  <tr key={c.name} className="border-t border-line"><td className="py-1">{c.name.replace(/\+/g, " + ").replace(/_/g, " ")}</td><td>{c.n_features}</td>
                    <td>{fmtNum(c.holdout.mae, 3)}</td>
                    <td>{c.holdout.vs_full ? `${fmtSigned(c.holdout.vs_full.estimate, 3)} [${fmtSigned(c.holdout.vs_full.lo, 3)}, ${fmtSigned(c.holdout.vs_full.hi, 3)}]` : "—"}</td></tr>
                ))}</tbody>
              </table>
            </Section>
          )}
          <Section title="Secondary experiments">
            <ul className="space-y-2 text-sm text-ink-2">
              {exp.corner_experiments && <li><b className="text-ink">Model B (sector pace)</b>: adding driver corner-category profiles changes MAE by {fmtSigned(exp.corner_experiments.sector_model.profile_minus_base.lightgbm.estimate, 4)} pp [{fmtSigned(exp.corner_experiments.sector_model.profile_minus_base.lightgbm.lo, 4)}, {fmtSigned(exp.corner_experiments.sector_model.profile_minus_base.lightgbm.hi, 4)}]. Corner specialisation split-half r = {fmtNum(exp.corner_experiments.specialisation_reliability.special.split_half_r, 2)} (p = {fmtNum(exp.corner_experiments.specialisation_reliability.special.permutation_p, 2)}).</li>}
              {exp.tyre_degradation && <li><b className="text-ink">Model C (degradation)</b>: MAE flat {fmtNum(exp.tyre_degradation.mae_pct.flat, 3)}, compound {fmtNum(exp.tyre_degradation.mae_pct.compound, 3)}, + circuit {fmtNum(exp.tyre_degradation.mae_pct.compound_circuit, 3)}, + driver {fmtNum(exp.tyre_degradation.mae_pct.compound_circuit_driver, 3)} (% of lap).</li>}
              {exp.quali_model && <li><b className="text-ink">Model F (qualifying)</b>: LightGBM MAE {fmtNum(exp.quali_model.models.lightgbm.mae, 3)}% vs team-form baseline {fmtNum(exp.quali_model.models.team_form_baseline.mae, 3)}%; mean per-event Spearman {fmtNum(exp.quali_model.models.lightgbm.mean_event_spearman, 2)} vs {fmtNum(exp.quali_model.models.team_form_baseline.mean_event_spearman, 2)}; pole hit rate {fmtNum(exp.quali_model.models.lightgbm.pole_hit_rate * 100, 0)}% vs {fmtNum(exp.quali_model.models.team_form_baseline.pole_hit_rate * 100, 0)}%.</li>}
              {clusters.data && <li><b className="text-ink">Model E (profile clustering)</b>: {clusters.data.meta.interpretation}</li>}
            </ul>
          </Section>
        </div>
      )}

      {validation.data && (
        <Section title="Explanation validation" subtitle={`${validation.data.model_version}, ${validation.data.n_rows} rows of ${validation.data.sample}`}>
          <KV rows={[
            ["Additivity error (base + contributions − prediction)", fmtNum(validation.data.additivity_max_abs_error, 12)],
            ["TreeSHAP vs shap library (max abs diff)", fmtNum(validation.data.treeshap_vs_shap_library_max_abs_diff, 12)],
            ["Global importance rank agreement across 20 bootstrap refits (mean Spearman)", fmtNum(validation.data.global_stability?.mean_pairwise_spearman, 3)],
            ["Top-5 feature overlap across refits (mean Jaccard)", fmtNum(validation.data.global_stability?.mean_top5_jaccard, 3)],
            ["Local top-3 contribution sign agreement across refits", `${fmtNum((validation.data.local_stability?.top3_sign_agreement ?? 0) * 100, 1)}%`],
            ["Pre-event vs pre-race model importance agreement (Spearman)", fmtNum(validation.data.cross_version?.spearman_global_importance, 3)],
            ["LightGBM vs Ridge importance agreement (Spearman)", fmtNum(validation.data.vs_ridge?.spearman_mean_abs, 3)],
          ]} />
          <div className="mt-2 text-xs text-ink-2">Strongly correlated inputs (credit may be split arbitrarily): {(validation.data.correlated_pairs as Json[]).slice(0, 6).map((p) => `${p.a} ~ ${p.b} (${fmtNum(p.spearman, 2)})`).join("; ")}.</div>
          <ul className="mt-2 list-disc pl-4 text-xs text-ink-muted">{(validation.data.notes as string[]).map((n) => <li key={n}>{n}</li>)}</ul>
        </Section>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Model versions" subtitle="Versioned artifacts with training period, configuration and metrics">
          <div className="max-h-72 overflow-y-auto">
            <table className="w-full whitespace-nowrap text-left text-xs tabular">
              <thead className="sticky top-0 bg-surface-1 text-ink-muted"><tr><th className="py-1">Version</th><th>Trained on</th><th>Holdout MAE</th><th /></tr></thead>
              <tbody>{(models.data?.models ?? []).map((v) => (
                <tr key={v.model_version} className="border-t border-line"><td className="py-1">{v.model_version}</td><td>{v.train_period}</td>
                  <td>{fmtNum(v.test_metrics?.holdout?.mae, 3)}</td><td>{v.is_production && <StatusPill status="good">production</StatusPill>}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </Section>
        <Section title="Known limitations">
          <ul className="list-disc space-y-1 pl-4 text-sm text-ink-2">{(m.limitations as string[]).map((l) => <li key={l}>{l}</li>)}</ul>
          <div className="mt-3 text-xs text-ink-muted">{Object.entries(m.licences as Json).map(([k, v]) => <div key={k}><b>{titleFromId(k)}:</b> {String(v)}</div>)}</div>
        </Section>
      </div>
    </div>
  );
}
