import argparse
import contextlib
import io
import hashlib
import json
import math
from pathlib import Path
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from model import solve
from src.load_data import load_data
from src import monte_carlo as mc
from validate import validate_solution


NAMES = ["x", "s", "qin", "qout", "I", "u", "k"]
LABELS = {"A": "Original fixed plan", "B": "Fixed capacity, foresight operations", "C": "Full foresight reoptimization"}
COLORS = {"A": "#c18b42", "B": "#3e759d", "C": "#39816a"}


def snapshot(model, variables, data):
    solution = {"status": "OPTIMAL", "objective": model.ObjVal}
    solution["costs"] = {name: value.getValue() for name, value in variables["cost_terms"].items()}
    solution.update({name: {key: value.X for key, value in variables[name].items()} for name in NAMES})
    solution["costs"]["purchase"] = sum(data["P"][t] * solution["x"][t] for t in data["T"])
    solution["costs"]["spot"] = sum(data["pi"][j, t] * solution["u"][j, t] for j in data["J"] for t in data["T"])
    return solution


def price_data(data, prices):
    return {**data, "P": {t: float(prices[t - 1, mc.HUB]) for t in data["T"]}, "pi": {(j, t): float(prices[t - 1, mc.LOCS.index(j)]) for j in data["J"] for t in data["T"]}}


def check_solution(solution, data):
    with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        problems = validate_solution(solution, data)
    if problems:
        raise ValueError("; ".join(problems[:5]))


def simulate(data, prices):
    baseline = solve(data)
    if baseline["status"] != "OPTIMAL":
        raise ValueError(f"Baseline status: {baseline['status']}")
    check_solution(baseline, data)
    models = mc.build_policy_models(data, baseline)
    try:
        mc.check_baseline_reproduced(models)
        keys = {name: list(baseline[name]) for name in NAMES}
        decisions = {policy: {name: np.empty((len(prices), len(keys[name]))) for name in NAMES} for policy in ["B", "C"]}
        costs = {"A": mc.cost_fixed_plan(models, prices), "B": np.empty(len(prices)), "C": np.empty(len(prices))}
        for draw, year in enumerate(prices):
            scenario = price_data(data, year)
            for policy in ["B", "C"]:
                costs[policy][draw] = mc._solve(models, policy, year)
                solution = snapshot(*models[policy], scenario)
                check_solution(solution, scenario)
                for name in NAMES:
                    decisions[policy][name][draw] = [solution[name][key] for key in keys[name]]
            if costs["A"][draw] + 0.001 < costs["B"][draw] or costs["B"][draw] + 0.001 < costs["C"][draw]:
                raise ValueError(f"Policy cost ordering failed at draw {draw + 1}")
            if (draw + 1) % 500 == 0:
                print(f"Validated {draw + 1} price scenarios", flush=True)
        return baseline, costs, decisions, keys
    finally:
        for policy in ["B", "C"]:
            models[policy][0].dispose()
        baseline["model"].dispose()


def summarize(costs):
    series = {**costs, "A_minus_B": costs["A"] - costs["B"], "B_minus_C": costs["B"] - costs["C"]}
    rows = []
    for name, values in series.items():
        se = values.std(ddof=1) / math.sqrt(len(values))
        rows.append({"policy": name, "mean_usd": values.mean(), "standard_deviation_usd": values.std(ddof=1), "p05_usd": np.quantile(values, 0.05), "median_usd": np.median(values), "p95_usd": np.quantile(values, 0.95), "cvar95_usd": mc.cvar(values), "mean_standard_error_usd": se, "mean_ci95_low_usd": values.mean() - 1.96 * se, "mean_ci95_high_usd": values.mean() + 1.96 * se})
    return pd.DataFrame(rows)


def decision_summary(baseline, decisions, keys, data):
    rows = []
    for policy in ["B", "C"]:
        for name in NAMES:
            for column, key in enumerate(keys[name]):
                values = decisions[policy][name][:, column]
                item = {"policy": policy, "variable": name, "index": str(key), "unit": "Dth/day" if name == "k" else "Dth", "baseline": baseline[name][key], "mean": values.mean(), "p05": np.quantile(values, 0.05), "median": np.median(values), "p95": np.quantile(values, 0.95), "positive_share": (values > 1e-6).mean(), "at_limit_share": np.nan}
                if name == "k":
                    item["at_limit_share"] = (np.abs(values - data["kbar"][key]) <= 1e-6).mean()
                if name == "s":
                    route, month = key
                    capacity = decisions[policy]["k"][:, keys["k"].index(route)]
                    item["at_limit_share"] = (np.abs(values - data["days"][month] * capacity) <= 1e-6).mean()
                rows.append(item)
    return pd.DataFrame(rows)


def plots(costs, decisions, keys, data, baseline, folder):
    fig, ax = plt.subplots(figsize=(9, 5))
    for policy in ["A", "B", "C"]:
        ax.hist(costs[policy] / 1e6, bins=40, alpha=0.4, color=COLORS[policy], label=LABELS[policy])
    ax.axvline(baseline["objective"] / 1e6, color="#333333", ls="--", label="2025–26 baseline")
    ax.set(xlabel="Annual modeled cost ($ million)", ylabel="Simulated price years", title=f"Costs across {len(costs['A']):,} price scenarios")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(folder / "monte_carlo_cost.png", dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for ax, name, title in zip(axes.flat, ["x", "u", "I", "s"], ["Hub purchases", "Local purchases, all markets", "Inventory, both storage positions", "Shipments, all routes"]):
        array = decisions["B"][name]
        totals = np.column_stack([array[:, [i for i, key in enumerate(keys[name]) if (key if name == "x" else key[1]) == t]].sum(axis=1) for t in data["T"]]) / 1e6
        base = [sum(value for key, value in baseline[name].items() if (key if name == "x" else key[1]) == t) / 1e6 for t in data["T"]]
        ax.fill_between(data["T"], np.quantile(totals, 0.05, axis=0), np.quantile(totals, 0.95, axis=0), alpha=0.2, label="5–95% scenario range")
        ax.plot(data["T"], np.median(totals, axis=0), label="Scenario median")
        ax.plot(data["T"], base, ls="--", color="#333333", label="2025–26 plan")
        ax.set(title=title, ylabel="Million Dth", xticks=data["T"], xticklabels=mc.TICKS)
        ax.tick_params(axis="x", labelsize=8)
    axes.flat[0].legend(fontsize=8)
    fig.suptitle("Monthly decisions with capacity fixed and full-year price foresight")
    fig.tight_layout()
    fig.savefig(folder / "monte_carlo_decisions.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5))
    limits = np.array([data["kbar"][route] for route in keys["k"]])
    ratio = decisions["C"]["k"] / limits * 100
    ax.boxplot([ratio[:, i] for i in range(len(limits))], tick_labels=[str(route) for route in keys["k"]], showfliers=True, flierprops={"markersize": 2, "alpha": 0.4})
    ax.scatter(range(1, len(limits) + 1), [baseline["k"][route] / data["kbar"][route] * 100 for route in keys["k"]], marker="D", color=COLORS["A"], label="Baseline")
    ax.set(xlabel="Pipeline route", ylabel="Reserved capacity (% of accessible limit)", title="Capacity decisions under full foresight", ylim=(-5, 105))
    ax.legend()
    fig.tight_layout()
    fig.savefig(folder / "monte_carlo_capacity.png", dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenarios", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=4004)
    parser.add_argument("--rho", type=float, default=0.8)
    parser.add_argument("--data-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--citygate-units", choices=["dth", "mcf"], default="dth")
    args = parser.parse_args()
    if args.scenarios < 2 or not -1 / 3 < args.rho < 1:
        parser.error("Use at least two scenarios and -1/3 < rho < 1")
    data = load_data(args.data_dir)
    means, variances = mc.load_price_moments(args.data_dir, citygate_units=args.citygate_units)
    prices = mc.sample_prices(means, variances, mc.equicorrelation(args.rho), n=args.scenarios, seed=args.seed, moment_match=False)
    baseline, costs, decisions, keys = simulate(data, prices)
    folder = args.output_dir
    folder.mkdir(parents=True, exist_ok=True)
    summary = summarize(costs)
    summary.to_csv(folder / "monte_carlo_summary.csv", index=False)
    pd.DataFrame({"scenario": np.arange(1, len(prices) + 1), **{f"cost_{policy}_usd": values for policy, values in costs.items()}, "A_minus_B_usd": costs["A"] - costs["B"], "B_minus_C_usd": costs["B"] - costs["C"]}).to_csv(folder / "monte_carlo_costs.csv", index=False)
    decision_summary(baseline, decisions, keys, data).to_csv(folder / "monte_carlo_decision_summary.csv", index=False)
    moments = [{"month": mc.TICKS[t], "location": location, "target_mean": means.iloc[t, j], "sample_mean": prices[:, t, j].mean(), "target_variance": variances.iloc[t, j], "sample_variance": prices[:, t, j].var(ddof=1)} for t in range(12) for j, location in enumerate(mc.LOCS)]
    pd.DataFrame(moments).to_csv(folder / "monte_carlo_sample_moments.csv", index=False)
    arrays = {"prices": prices}
    arrays.update({f"{policy}_{name}": values for policy, variables in decisions.items() for name, values in variables.items()})
    np.savez_compressed(folder / "monte_carlo_draws.npz", **arrays)
    metadata = {"scenarios": args.scenarios, "seed": args.seed, "rho": args.rho, "sampling": "independent lognormal year draws; Gaussian copula within month; months independent; no moment matching", "input_citygate_units": args.citygate_units, "price_array_locations": mc.LOCS, "decision_columns": {name: [list(key) if isinstance(key, tuple) else key for key in values] for name, values in keys.items()}, "baseline_cost_usd": baseline["objective"], "expected_fixed_plan_cost_usd": float(baseline["objective"] - baseline["costs"]["purchase"] - baseline["costs"]["spot"] + sum(means.loc[t, "HUB"] * baseline["x"][t] for t in data["T"]) + sum(means.loc[t, j] * baseline["u"][j, t] for j in data["J"] for t in data["T"])), "validated_optimized_solutions": 2 * args.scenarios, "max_policy_order_violation_usd": float(max(0, (costs["B"] - costs["A"]).max(), (costs["C"] - costs["B"]).max())), "input_sha256": {name: hashlib.sha256((args.data_dir / name).read_bytes()).hexdigest() for name in ["mc_means.csv", "mc_vars.csv", "months.csv", "prices.csv", "demand.csv", "storage.csv", "routes.csv"]}, "interpretation": "B and C use full-year price foresight; A-B and B-C are information benchmarks, not guaranteed achievable savings."}
    (folder / "monte_carlo_run.json").write_text(json.dumps(metadata, indent=2) + "\n")
    plots(costs, decisions, keys, data, baseline, folder)
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
