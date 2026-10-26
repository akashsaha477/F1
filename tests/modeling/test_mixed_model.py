"""The crossed random-effects solver recovers known structure from simulated data."""

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from apexlens.driver_profiles.mixed_model import empirical_bayes, fit_mixed_model


def simulate(seed=0):
    rng = np.random.default_rng(seed)
    drivers = {f"d{i}": rng.normal(0, 0.4) for i in range(24)}
    rows = []
    for season in (2022, 2023, 2024):
        order = rng.permutation(list(drivers))
        teams = {f"t{j}-{season}": rng.normal(0, 0.6) for j in range(12)}
        team_of = {d: f"t{i // 2}-{season}" for i, d in enumerate(order)}
        ds = {d: rng.normal(0, 0.1) for d in drivers}
        for e in range(20):
            for d in drivers:
                y = drivers[d] + ds[d] + teams[team_of[d]] + rng.normal(0, 0.3)
                rows.append({"driver": d, "driver_season": f"{d}:{season}", "team_season": team_of[d],
                             "event": f"{season}-{e}", "y": y, "m": 0.01, "true_driver": drivers[d]})
    return pd.DataFrame(rows)


def test_reml_recovers_components_and_effects():
    df = simulate()
    res = fit_mixed_model(df, "y", random=["driver", "driver_season", "team_season"], meas_var="m")
    assert res.converged
    v = res.variances
    assert 0.06 < v["residual"] < 0.12  # true 0.09 + known 0.01 handled separately
    assert 0.08 < v["driver"] < 0.35  # true 0.16
    assert 0.2 < v["team_season"] < 0.6  # true 0.36
    est = res.effects["driver"].set_index("level")["estimate"]
    truth = df.groupby("driver")["true_driver"].first()
    assert np.corrcoef(est.loc[truth.index], truth)[0, 1] > 0.9  # driver and car are only partly separable
    assert (res.effects["driver"]["pev"] > 0).all()
    e, pev = res.combined([("driver", "d0"), ("driver_season", "d0:2022")])
    assert np.isfinite(e) and pev > 0


def test_matches_statsmodels_for_single_random_effect():
    rng = np.random.default_rng(3)
    g = np.repeat(np.arange(30), 15)
    u = rng.normal(0, 0.5, 30)
    y = 1.0 + u[g] + rng.normal(0, 0.7, len(g))
    df = pd.DataFrame({"y": y, "g": g.astype(str)})
    ours = fit_mixed_model(df, "y", random=["g"])
    sm = smf.mixedlm("y ~ 1", df, groups=df["g"]).fit(reml=True)
    assert abs(ours.variances["g"] - float(sm.cov_re.iloc[0, 0])) < 0.02
    assert abs(ours.variances["residual"] - float(sm.scale)) < 0.02
    assert abs(ours.fixed["intercept"] - float(sm.fe_params["Intercept"])) < 1e-3


def test_empirical_bayes_shrinks_noisy_estimates_more():
    est = np.array([1.0, 1.0, 0.0, -0.5, 0.2, 0.4])
    var = np.array([0.01, 4.0, 0.05, 0.05, 0.05, 0.05])
    post, pvar, tau2 = empirical_bayes(est, var)
    assert tau2 > 0
    assert abs(post[0]) > abs(post[1])  # same raw estimate, the noisy one is shrunk harder
    assert (pvar <= var + 1e-12).all()
