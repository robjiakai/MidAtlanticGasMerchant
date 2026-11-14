"""
monte_carlo.py
Milestone 5: Monte Carlo price-uncertainty analysis.

Draws 1,000 synthetic price years (hub P[t] and citygate pi[j,t]) from
2015-2024 monthly moments and costs three policies on each year:

    A  fixed plan      baseline solution `sol` repriced, no solve
    B  fixed capacity  k fixed at the baseline values, monthly operations re-optimised
    C  re-optimised    everything free (perfect foresight within the year)

The LP in model.py is not changed. B and C are each built once with
build_model(); only the objective coefficients of x and u change per draw.

INPUTS (data/processed/)
    mc_means.csv  month, t, mu_ny, mu_nj, mu_pa, mu_h     ($/Dth)
    mc_vars.csv   month, t, Var_ny, Var_nj, Var_pa, Var_h (sample variance, n-1)
    mc_history.csv (optional) month (YYYY-MM), ny, nj, pa, h  raw monthly prices,
                  used only to estimate the 4x4 correlation matrix.
    Months are matched by name (Apr -> t=1 ... Mar -> t=12), not row order.

SAMPLING
    Each location-month price is lognormal with mean and variance equal to
    the inputs: sigma^2 = ln(1 + var/mean^2), mu = ln(mean) - sigma^2/2.
    The 4 locations are correlated within a month through a Gaussian copula
    (Cholesky of the correlation matrix). Months are drawn independently
    (assumption: no month-to-month persistence in prices).
    By default the underlying standard normals are moment-matched per month
    (sample mean exactly 0, sample covariance exactly I before applying the
    Cholesky factor). This is a variance-reduction step; it does not change
    the target distribution.

USAGE (from the repo root, src/ on sys.path)
    import monte_carlo as mc
    means, variances = mc.load_price_moments()
    prices = mc.sample_prices(means, variances, mc.equicorrelation(0.8))
    models = mc.build_policy_models(data, sol)
    res = mc.run_policies(models, prices)
    mc.summarize(res)
"""

import math
from pathlib import Path

import gurobipy as gp
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from gurobipy import GRB

from model import build_model

DATA_DIR = Path("data/processed")
OUT_DIR = Path("outputs")

MONTH_TO_T = {m: t for t, m in enumerate(
    ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"], start=1)}
TICKS = list(MONTH_TO_T)
LOCS = ["NY", "NJ", "PA", "HUB"]           # price array column order
SUFFIX = {"NY": "ny", "NJ": "nj", "PA": "pa", "HUB": "h"}
MARKETS = ["NY", "NJ", "PA"]               # model J, in LOCS order
HUB = LOCS.index("HUB")
WINTER = [8, 9, 10, 11, 12]                # Nov-Mar
SUMMER = [1, 2, 3, 4, 5, 6, 7]             # Apr-Oct
MCF_TO_DTH = 1.037                         # Dth per Mcf (EIA heat content)
POLICIES = ["A", "B", "C"]
POLICY_NAME = {"A": "A: fixed plan", "B": "B: fixed capacity", "C": "C: re-optimised"}
COLOR = {"A": "#CE9252", "B": "#45749C", "C": "#4D8C76"}
GRAY = "#303841"
ROUTE_NAME = {1: "Empire → NY", 2: "NFG → NY", 3: "TGP → NJ", 4: "TETCO → PA"}
TOL = 1e-3


# ----------------------------------------------------------------------------
# Inputs
# ----------------------------------------------------------------------------
def _read_monthly(path, prefix):
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    cols = [f"{prefix}_{SUFFIX[l]}" for l in LOCS]
    missing = [c for c in ["month"] + cols if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}; found {list(df.columns)}")
    df["month"] = df["month"].astype(str).str.strip().str[:3].str.title()
    if sorted(df["month"]) != sorted(MONTH_TO_T) or df["month"].duplicated().any():
        raise ValueError(f"{path}: expected one row for each of {TICKS}, got {list(df['month'])}")
    df["t_model"] = df["month"].map(MONTH_TO_T)          # Apr -> 1, explicitly
    if "t" in df.columns and not (df["t"].astype(int) == df["t_model"]).all():
        raise ValueError(f"{path}: column t disagrees with the month names (Apr must be t=1)")
    out = df.set_index("t_model").sort_index()[cols]
    out.columns = LOCS
    out.index.name = "t"
    if not np.isfinite(out.to_numpy()).all() or (out.to_numpy() <= 0).any():
        raise ValueError(f"{path}: values must be finite and positive")
    return out


def load_price_moments(data_dir=DATA_DIR, citygate_units="dth"):
    """Return (means, variances) as 12x4 DataFrames indexed by t=1..12, columns LOCS.
    citygate_units="mcf" converts citygate columns to $/Dth (mean/1.037, var/1.037^2);
    the hub column is already $/MMBtu = $/Dth and is never converted."""
    data_dir = Path(data_dir)
    means = _read_monthly(data_dir / "mc_means.csv", "mu")
    variances = _read_monthly(data_dir / "mc_vars.csv", "Var")
    if citygate_units == "mcf":
        means[MARKETS] = means[MARKETS] / MCF_TO_DTH
        variances[MARKETS] = variances[MARKETS] / MCF_TO_DTH ** 2
    elif citygate_units != "dth":
        raise ValueError("citygate_units must be 'dth' or 'mcf'")
    return means, variances


def equicorrelation(rho, k=len(LOCS)):
    """k x k correlation matrix with every off-diagonal equal to rho."""
    return np.full((k, k), rho) + (1 - rho) * np.eye(k)


def history_correlation(path=DATA_DIR / "mc_history.csv"):
    """Pooled 4x4 correlation of deseasonalised log prices, or None if the file is absent.
    Log prices minus each calendar month's mean log price (per location), all months pooled."""
    path = Path(path)
    if not path.exists():
        return None
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    cols = [SUFFIX[l] for l in LOCS]
    month = pd.to_datetime(df["month"]).dt.month
    logp = np.log(df[cols].astype(float))
    resid = logp - logp.groupby(month).transform("mean")
    corr = resid.corr().to_numpy()
    np.linalg.cholesky(corr)          # raises if not positive definite
    return corr


# ----------------------------------------------------------------------------
# Sampling
# ----------------------------------------------------------------------------
def lognormal_params(means, variances):
    sigma2 = np.log1p(variances.to_numpy() / means.to_numpy() ** 2)
    mu = np.log(means.to_numpy()) - sigma2 / 2
    return mu, np.sqrt(sigma2)                       # each 12 x 4


def sample_prices(means, variances, corr, n=1000, seed=4004, moment_match=True):
    """Return prices[n, 12, 4] ($/Dth), axis 1 = t-1, axis 2 = LOCS."""
    rng = np.random.default_rng(seed)
    mu, sigma = lognormal_params(means, variances)
    chol = np.linalg.cholesky(np.asarray(corr, float))
    prices = np.empty((n, 12, len(LOCS)))
    for i in range(12):                              # months independent
        z = rng.standard_normal((n, len(LOCS)))
        # numpy 2.x on macOS Accelerate emits spurious matmul FP warnings; checked finite below
        with np.errstate(all="ignore"):
            if moment_match:
                z -= z.mean(axis=0)
                z = z @ np.linalg.inv(np.linalg.cholesky(np.cov(z, rowvar=False))).T
            y = z @ chol.T                           # correlated N(0,1) within the month
        prices[:, i, :] = np.exp(mu[i] + sigma[i] * y)
    assert np.isfinite(prices).all() and (prices > 0).all()
    return prices


def check_sample_means(prices, means, tol=0.03):
    """Assert sample means are within tol of the targets in every location-month."""
    rel = prices.mean(axis=0) / means.to_numpy() - 1
    worst = np.abs(rel).max()
    assert worst <= tol, f"sample mean off target by {worst:.2%} (> {tol:.0%})"
    return pd.DataFrame(rel, index=means.index, columns=LOCS)


def hub_above_citygate(prices):
    """Share of (draw, month) cases where the hub price exceeds each citygate price."""
    hub = prices[:, :, HUB]
    share = {j: (hub > prices[:, :, LOCS.index(j)]).mean() for j in MARKETS}
    share["any market"] = (hub[:, :, None] > prices[:, :, :HUB]).any(axis=2).mean()
    return pd.Series(share)


def winter_summer_spread(prices):
    hub = prices[:, :, HUB]
    return hub[:, [t - 1 for t in WINTER]].mean(axis=1) - hub[:, [t - 1 for t in SUMMER]].mean(axis=1)


# ----------------------------------------------------------------------------
# Policies
# ----------------------------------------------------------------------------
def build_policy_models(data, sol):
    """Build the B (k fixed) and C (free) models once. Returns a dict used by run_policies."""
    T, J, L, F = data["T"], data["J"], data["L"], data["F"]
    assert list(J) == MARKETS, "market order must match LOCS"
    models = {"data": data, "sol": sol}
    for name in ["B", "C"]:
        m, v = build_model(data)
        m.Params.OptimalityTol = 1e-9            # tight tolerances so A >= B >= C holds to $1e-3
        m.Params.FeasibilityTol = 1e-9
        if name == "B":
            for l in L:
                v["k"][l].LB = v["k"][l].UB = sol["k"][l]
        m.update()
        models[name] = (m, v)
        models[name + "_xu"] = [v["x"][t] for t in T] + [v["u"][j, t] for t in T for j in J]
    # Policy A: the baseline plan repriced. Purchase and spot terms are the only price-dependent ones.
    models["A_const"] = sol["objective"] - sol["costs"]["purchase"] - sol["costs"]["spot"]
    models["x_base"] = np.array([sol["x"][t] for t in T])
    models["u_base"] = np.array([[sol["u"][j, t] for j in J] for t in T])
    return models


def _coeffs(p):
    """Objective coefficients for [x[t] ..., u[j,t] ...] from one price year p[12, 4]."""
    return list(p[:, HUB]) + list(p[:, :HUB].ravel())


def _solve(models, name, p):
    m, _ = models[name]
    m.setAttr("Obj", models[name + "_xu"], _coeffs(p))
    m.optimize()
    if m.Status != GRB.OPTIMAL:
        raise RuntimeError(f"policy {name}: status {m.Status}")
    return m.ObjVal


def cost_fixed_plan(models, prices):
    return (models["A_const"] + prices[:, :, HUB] @ models["x_base"]
            + (prices[:, :, :HUB] * models["u_base"]).sum(axis=(1, 2)))


def check_baseline_reproduced(models):
    """Feeding the baseline prices back in must give the baseline objective for A, B and C."""
    d = models["data"]
    p = np.array([[d["pi"][j, t] for j in MARKETS] + [d["P"][t]] for t in d["T"]])
    obj = models["sol"]["objective"]
    a = cost_fixed_plan(models, p[None])[0]
    for name, val in [("A", a), ("B", _solve(models, "B", p)), ("C", _solve(models, "C", p))]:
        assert abs(val - obj) <= 1e-6 * obj, f"policy {name} at baseline prices: {val:,.2f} vs {obj:,.2f}"


def run_policies(models, prices, record=True):
    """Cost A, B, C on every draw. Returns a dict of numpy arrays (one row per draw)."""
    d, n = models["data"], len(prices)
    T, L, F = d["T"], d["L"], d["F"]
    vB, vC = models["B"][1], models["C"][1]
    res = {"A": cost_fixed_plan(models, prices), "B": np.empty(n), "C": np.empty(n),
           "spread": winter_summer_spread(prices),
           "inj_B": np.empty(n), "citygate_B": np.empty(n),
           "k_C": np.empty((n, len(L))), "I_B": np.empty((n, len(F), len(T)))}
    for i in range(n):
        res["B"][i] = _solve(models, "B", prices[i])
        res["C"][i] = _solve(models, "C", prices[i])
        if record:
            res["inj_B"][i] = sum(vB["qin"][f, t].X for f in F for t in T)
            res["citygate_B"][i] = sum(vB["u"][j, t].X for j in MARKETS for t in T)
            res["k_C"][i] = [vC["k"][l].X for l in L]
            res["I_B"][i] = [[vB["I"][f, t].X for t in T] for f in F]
    gap_ab, gap_bc = res["A"] - res["B"], res["B"] - res["C"]
    assert (gap_ab >= -TOL).all(), f"cost A < cost B in {(gap_ab < -TOL).sum()} draws (min {gap_ab.min():.4f})"
    assert (gap_bc >= -TOL).all(), f"cost B < cost C in {(gap_bc < -TOL).sum()} draws (min {gap_bc.min():.4f})"
    res["A-B"], res["B-C"] = gap_ab, gap_bc
    return res


# ----------------------------------------------------------------------------
# Summary and outputs
# ----------------------------------------------------------------------------
def cvar(x, level=0.95):
    """Average of the worst (largest) 1-level share of outcomes."""
    x = np.sort(np.asarray(x))
    return x[int(math.floor(level * len(x))):].mean()


def summarize(res, baseline=None):
    rows = {}
    for key, label in [("A", POLICY_NAME["A"]), ("B", POLICY_NAME["B"]), ("C", POLICY_NAME["C"]),
                       ("A-B", "A − B: value of operational flexibility"),
                       ("B-C", "B − C: cost of committing capacity early")]:
        x = res[key]
        rows[label] = {"mean": x.mean(), "95% CI ±": 1.96 * x.std(ddof=1) / math.sqrt(len(x)),
                       "std": x.std(ddof=1), "P5": np.percentile(x, 5), "median": np.median(x),
                       "P95": np.percentile(x, 95), "CVaR95": cvar(x)}
    out = pd.DataFrame(rows).T
    if baseline is not None:
        out["mean vs baseline"] = np.where(out.index.str.startswith(("A:", "B:", "C:")),
                                           out["mean"] - baseline, np.nan)
    return out


def costs_frame(res, data):
    df = pd.DataFrame({"cost_A": res["A"], "cost_B": res["B"], "cost_C": res["C"],
                       "A_minus_B": res["A-B"], "B_minus_C": res["B-C"],
                       "hub_spread_winter_minus_summer": res["spread"],
                       "injections_B_dth": res["inj_B"], "citygate_B_dth": res["citygate_B"]})
    for i, l in enumerate(data["L"]):
        df[f"k_C_route{l}"] = res["k_C"][:, i]
    df.index.name = "draw"
    return df


def save_tables(res, summary, data, out_dir=OUT_DIR):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    costs_frame(res, data).to_csv(out_dir / "mc_costs.csv")
    summary.to_csv(out_dir / "mc_summary.csv")
    print(f"Wrote {out_dir / 'mc_costs.csv'} and {out_dir / 'mc_summary.csv'}")


def rho_sweep(models, means, variances, rhos=(0.0, 0.5, 0.8, 0.9), n=1000, seed=4004):
    """Re-run the simulation at several correlation levels with the same random numbers."""
    rows = []
    for rho in rhos:
        prices = sample_prices(means, variances, equicorrelation(rho), n=n, seed=seed)
        check_sample_means(prices, means)
        r = run_policies(models, prices)
        above = hub_above_citygate(prices)
        rows.append({"rho": rho, "mean cost B": r["B"].mean(), "P95 cost B": np.percentile(r["B"], 95),
                     "injections B P5": np.percentile(r["inj_B"], 5),
                     "injections B P95": np.percentile(r["inj_B"], 95),
                     "injections B P95-P5": np.percentile(r["inj_B"], 95) - np.percentile(r["inj_B"], 5),
                     "mean A-B": r["A-B"].mean(), "mean B-C": r["B-C"].mean(),
                     **{f"hub > {k} citygate": v for k, v in above.items()}})
    return pd.DataFrame(rows).set_index("rho")


# ----------------------------------------------------------------------------
# Figures
# ----------------------------------------------------------------------------
def _style(ax, grid="y"):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis=grid, color="#E4E7EA", linewidth=0.65)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0, pad=6, labelsize=9)


def _save(fig, out_dir, name):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / name
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {path}")
    return path


def plot_cost_distribution(res, baseline, out_dir=OUT_DIR):
    """Fig 10: cost histograms for A/B/C and running-mean convergence."""
    M = 1e6
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.4), gridspec_kw={"width_ratios": [1.4, 1]})
    allc = np.concatenate([res[p] for p in POLICIES]) / M
    bins = np.linspace(allc.min(), max(allc.max(), baseline / M), 50)
    for p in POLICIES:
        ax1.hist(res[p] / M, bins=bins, color=COLOR[p], alpha=0.45, label=f"{POLICY_NAME[p]} (mean ${res[p].mean() / M:,.1f}M)")
    ax1.axvline(baseline / M, color=GRAY, ls="--", lw=1.2, label=f"baseline 2025–26 (${baseline / M:,.1f}M)")
    ax1.set_xlabel("Annual cost ($ million)")
    ax1.set_ylabel("Number of simulated years")
    ax1.set_title("Annual cost over 1,000 simulated price years", fontsize=10, loc="left")
    ax1.legend(fontsize=8, frameon=False)
    _style(ax1)

    k = np.arange(1, len(res["A"]) + 1)
    for p in POLICIES:
        x = res[p] / M
        run = np.cumsum(x) / k
        sd = pd.Series(x).expanding().std().to_numpy()
        half = 1.96 * sd / np.sqrt(k)
        ax2.plot(k, run, color=COLOR[p], lw=1.3, label=POLICY_NAME[p])
        ax2.fill_between(k[1:], (run - half)[1:], (run + half)[1:], color=COLOR[p], alpha=0.15, lw=0)
    ax2.set_xlabel("Number of draws")
    ax2.set_ylabel("Running mean cost ($ million)")
    ax2.set_title("Convergence of the mean (±95% CI)", fontsize=10, loc="left")
    ax2.legend(fontsize=8, frameon=False)
    _style(ax2)
    fig.tight_layout()
    return _save(fig, out_dir, "10_mc_cost_distribution.png")


def plot_decision_stability(res, data, sol, out_dir=OUT_DIR):
    """Fig 11: re-optimised k as % of kbar; storage inventory fan charts under policy B."""
    L, F, T = data["L"], data["F"], data["T"]
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), gridspec_kw={"width_ratios": [1, 1.2, 1.2]})
    ax = axes[0]
    pct = res["k_C"] / np.array([data["kbar"][l] for l in L]) * 100
    pos = np.arange(1, len(L) + 1)
    ax.boxplot([pct[:, i] for i in range(len(L))], positions=pos, widths=0.55,
               medianprops={"color": COLOR["C"]}, flierprops={"markersize": 2, "alpha": 0.4})
    ax.scatter(pos, [sol["k"][l] / data["kbar"][l] * 100 for l in L], marker="D", color=COLOR["A"],
               zorder=3, s=28, label="baseline k")
    ax.set_xticks(pos)
    ax.set_xticklabels([ROUTE_NAME.get(l, str(l)) for l in L], fontsize=8)
    ax.set_ylabel("Contracted capacity k (% of accessible kbar)")
    ax.set_ylim(-5, 108)
    ax.set_title("Policy C: capacity chosen each year", fontsize=10, loc="left")
    ax.legend(fontsize=8, frameon=False, loc="lower left")
    _style(ax)

    x = np.arange(len(T))
    label = {"H": "Hub storage (H)", "M": "NY market storage (M)"}
    for ax, (fi, f) in zip(axes[1:], enumerate(F)):
        inv = res["I_B"][:, fi, :] / 1e6
        ax.fill_between(x, np.percentile(inv, 5, axis=0), np.percentile(inv, 95, axis=0),
                        color=COLOR["B"], alpha=0.22, lw=0, label="policy B, 5–95% range")
        ax.plot(x, np.median(inv, axis=0), color=COLOR["B"], lw=1.4, label="policy B, median")
        ax.plot(x, [sol["I"][f, t] / 1e6 for t in T], color=GRAY, ls="--", lw=1.2, label="baseline plan")
        ax.axhline(data["Ibar"][f] / 1e6, color=COLOR["A"], lw=1, label="capacity")
        ax.set_xticks(x)
        ax.set_xticklabels(TICKS, fontsize=8)
        ax.set_ylabel("End-of-month inventory (million Dth)")
        ax.set_title(f"{label.get(f, f)}: inventory under fixed capacity", fontsize=10, loc="left")
        ax.set_ylim(0, data["Ibar"][f] / 1e6 * 1.12)
        _style(ax)
    axes[1].legend(fontsize=8, frameon=False, loc="upper left")
    fig.tight_layout()
    return _save(fig, out_dir, "11_mc_decision_stability.png")


def plot_spread_vs_injections(res, data, sol, prices_base=None, out_dir=OUT_DIR):
    """Fig 12: winter-summer hub spread vs total injections under B."""
    fee = max(data["c_in"][f] + data["c_out"][f] for f in data["F"])
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.scatter(res["spread"], res["inj_B"] / 1e6, s=9, alpha=0.45, color=COLOR["B"], lw=0,
               label="one simulated year (policy B)")
    if prices_base is not None:
        ax.scatter(winter_summer_spread(prices_base[None])[0],
                   sum(sol["qin"].values()) / 1e6, marker="D", color=COLOR["A"], s=40, zorder=3,
                   label="baseline 2025–26")
    ax.axvline(fee, color=GRAY, ls="--", lw=1.1, label=f"storage fee in + out (${fee:.4f}/Dth)")
    ax.axvline(0, color="#9AA3AB", lw=0.8)
    ax.set_xlabel("Winter − summer hub price spread ($/Dth)\n(mean Nov–Mar minus mean Apr–Oct)")
    ax.set_ylabel("Total storage injections (million Dth)")
    r = np.corrcoef(res["spread"], res["inj_B"])[0, 1]
    ax.set_title(f"Seasonal hub spread vs storage injections (correlation {r:.2f})", fontsize=10, loc="left")
    ax.legend(fontsize=8, frameon=False)
    _style(ax, grid="both")
    fig.tight_layout()
    return _save(fig, out_dir, "12_mc_spread_vs_injections.png")


def plot_rho_sweep(sweep, out_dir=OUT_DIR):
    """Fig 13: mean and P95 cost of B, and P95 - P5 of injections, at each rho."""
    rho = sweep.index.to_numpy()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    ax1.plot(rho, sweep["mean cost B"] / 1e6, "o-", color=COLOR["B"], label="mean")
    ax1.plot(rho, sweep["P95 cost B"] / 1e6, "s--", color=COLOR["A"], label="P95 (bad year)")
    ax1.set_xlabel("Price correlation between locations (ρ)")
    ax1.set_ylabel("Policy B annual cost ($ million)")
    ax1.set_title("Cost under fixed capacity", fontsize=10, loc="left")
    ax1.legend(fontsize=8, frameon=False)
    ax2.plot(rho, sweep["injections B P95-P5"] / 1e6, "o-", color=COLOR["C"])
    ax2.set_xlabel("Price correlation between locations (ρ)")
    ax2.set_ylabel("P95 − P5 of total injections (million Dth)")
    ax2.set_title("How much the storage plan swings", fontsize=10, loc="left")
    ax2.set_ylim(0, sweep["injections B P95-P5"].max() / 1e6 * 1.2)
    for ax in (ax1, ax2):
        ax.set_xticks(rho)
        _style(ax)
    fig.tight_layout()
    return _save(fig, out_dir, "13_mc_rho_sweep.png")
