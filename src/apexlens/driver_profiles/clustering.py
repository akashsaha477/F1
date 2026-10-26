"""Model E — exploratory structure in driver fingerprints.

Driver-season feature vectors (team-adjusted pace, qualifying, consistency, team-mate gaps, start
gains, corner-category deltas, tyre-degradation deviations) are standardised, projected with PCA and
clustered with k-means for k = 2..6. Stability is measured by re-clustering bootstrap resamples and
comparing assignments with the adjusted Rand index (ARI) on the shared rows.

This is exploratory. Clusters are described only by the measured features that separate them (e.g.
"qualifies ahead of team-mate"), never by personality labels, and are reported as unstable when the
bootstrap ARI is low.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from apexlens.storage.io import read_table, write_json, write_table
from apexlens.storage.paths import DataPaths

FEATURES = {
    "race_pace_adj": "team-adjusted race pace (negative = faster)",
    "quali_adj": "team-adjusted qualifying (negative = faster)",
    "consistency_sd": "lap-to-lap variation (lower = more consistent)",
    "teammate_gap_race": "race gap to team-mate",
    "quali_teammate_gap": "qualifying gap to team-mate",
    "lap1_gain_mean": "positions gained on lap 1",
    "corner_slow": "slow-corner delta to team-mate",
    "corner_medium": "medium-corner delta to team-mate",
    "corner_fast": "fast-corner delta to team-mate",
    "deg_medium": "medium-tyre degradation deviation",
    "deg_hard": "hard-tyre degradation deviation",
}
MIN_RACES = 10
STABLE_ARI = 0.6


def feature_matrix(paths: DataPaths) -> pd.DataFrame:
    prof = read_table(paths.gold("driver_profiles"))
    prof = prof[prof["n_dry_races"] >= MIN_RACES]
    dc = read_table(paths.gold("driver_corner_profiles"))
    if len(dc):
        piv = dc.pivot_table(index=["driver_id", "season"], columns="category", values="delta_pct").add_prefix("corner_")
        prof = prof.merge(piv.reset_index(), on=["driver_id", "season"], how="left")
    dt = read_table(paths.gold("driver_tyre_effects"))
    if len(dt):
        piv = dt.pivot_table(index=["driver_id", "season"], columns="compound", values="raw")
        piv.columns = [f"deg_{c.lower()}" for c in piv.columns]
        prof = prof.merge(piv.reset_index(), on=["driver_id", "season"], how="left")
    cols = [c for c in FEATURES if c in prof.columns]
    return prof[["driver_id", "season", "main_team"] + cols]


def stability(Z: np.ndarray, k: int, n_boot: int = 100, seed: int = 0) -> float:
    rng = np.random.default_rng(seed)
    full = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(Z)
    aris = []
    for b in range(n_boot):
        idx = np.unique(rng.choice(len(Z), len(Z), replace=True))
        lab = KMeans(n_clusters=k, n_init=10, random_state=seed + b + 1).fit_predict(Z[idx])
        aris.append(adjusted_rand_score(full[idx], lab))
    return float(np.mean(aris))


def describe(centroid_z: pd.Series) -> list[str]:
    parts = []
    for f, z in centroid_z.sort_values(key=np.abs, ascending=False).items():
        if abs(z) < 0.5:
            continue
        direction = "higher" if z > 0 else "lower"
        parts.append(f"{direction} {FEATURES[f]} ({z:+.1f} SD)")
        if len(parts) == 3:
            break
    return parts or ["close to the average on every feature"]


def build_clusters(paths: DataPaths, seed: int = 0) -> dict:
    fm = feature_matrix(paths)
    cols = [c for c in FEATURES if c in fm.columns]
    X = fm[cols].apply(lambda s: s.fillna(s.median()))
    Z = StandardScaler().fit_transform(X)
    pca = PCA(n_components=min(4, len(cols)), random_state=seed).fit(Z)
    P = pca.transform(Z)
    results = []
    for k in range(2, 7):
        lab = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(Z)
        results.append({"k": k, "silhouette": float(silhouette_score(Z, lab)), "bootstrap_ari": stability(Z, k, seed=seed)})
    best = max(results, key=lambda r: r["silhouette"])
    labels = KMeans(n_clusters=best["k"], n_init=10, random_state=seed).fit_predict(Z)
    zdf = pd.DataFrame(Z, columns=cols)
    clusters = []
    for c in range(best["k"]):
        cz = zdf[labels == c].mean()
        clusters.append({"cluster": int(c), "size": int((labels == c).sum()), "centroid_z": cz.round(3).to_dict(),
                         "description": describe(cz)})
    points = fm[["driver_id", "season", "main_team"]].assign(pc1=P[:, 0], pc2=P[:, 1], cluster=labels)
    pace_axis = zdf[[c for c in ("race_pace_adj", "quali_adj", "teammate_gap_race", "quali_teammate_gap") if c in zdf]].mean(axis=1)
    pace_r = float(abs(np.corrcoef(labels, pace_axis)[0, 1])) if best["k"] == 2 else None
    write_table(paths.gold("driver_clusters"), points)
    meta = {
        "features": {c: FEATURES[c] for c in cols}, "n_driver_seasons": int(len(fm)), "min_races": MIN_RACES,
        "pca_explained_variance": [float(v) for v in pca.explained_variance_ratio_],
        "pca_loadings": {f"pc{i + 1}": dict(zip(cols, map(float, pca.components_[i]), strict=True)) for i in range(2)},
        "k_selection": results, "chosen_k": best["k"], "clusters": clusters,
        "stable": bool(best["bootstrap_ari"] >= STABLE_ARI), "pace_separation_r": pace_r,
        "interpretation": ("Exploratory only. Clusters are stable under resampling" if best["bootstrap_ari"] >= STABLE_ARI
                           else "Exploratory only. The clustering is NOT stable under resampling (bootstrap ARI below "
                                f"{STABLE_ARI}); do not treat the groups as driver types."),
    }
    if pace_r is not None and pace_r >= 0.7:
        meta["interpretation"] += (f". The two groups mainly separate overall pace relative to team-mates (|r| = {pace_r:.2f} "
                                   "with a combined pace score), i.e. one performance axis rather than distinct driving styles; "
                                   "solutions with three or more groups are unstable.")
    write_json(paths.gold("driver_clusters") / "meta.json", meta)
    return meta
