"""Three simple Matplotlib figures for MidAtlanticGasMerchant.

Run from the repository root:
    python visualizations.py

Input (already in GitHub):
    outputs/market_supply.csv, outputs/monthly_plan.csv,
    data/processed/prices.csv, data/processed/storage.csv

Output: outputs/figures/01_*.png through 03_*.png
No Gurobi required.  Units: Dth = dekatherm; 1 million Dth = 1e6 Dth.
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

# Consistent colors across the three figures.
BLUE = "#45749C"       # Pipeline / price / PA storage
GREEN = "#4D8C76"      # Storage withdrawal / NY storage / injection
ORANGE = "#CE9252"     # Citygate / storage withdrawal in Figure 3
GRAY = "#303841"
MONTHS = ["Apr-25", "May-25", "Jun-25", "Jul-25", "Aug-25", "Sep-25",
          "Oct-25", "Nov-25", "Dec-25", "Jan-26", "Feb-26", "Mar-26"]
TICKS = ["Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
         "Jan", "Feb", "Mar"]
MILLION = 1_000_000


def style_axes(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#E4E7EA", linewidth=0.65)
    ax.set_axisbelow(True)
    ax.tick_params(axis="both", length=0, pad=6, labelsize=9)
    ax.set_xlim(-0.55, 11.55)


def save(fig, output_dir, name):
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / name
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved {path}")


def plot_supply_mix(supply, output_dir):
    """Each bar is gas actually USED to meet demand, not gross delivered gas.

    For NY, gas injected into NY storage is subtracted from the pipeline
    portion; gas withdrawn from NY storage is a separate positive source.
    The three stacked components therefore sum exactly to contracted demand.
    """
    fig, axes = plt.subplots(3, 1, figsize=(10.5, 7.7), sharex=True, sharey=True)
    x = np.arange(12)
    for ax, market in zip(axes, ("NY", "NJ", "PA")):
        d = supply[supply["market"] == market].set_index("month").loc[MONTHS]
        net_storage = d["storage (net)"].to_numpy(float) / MILLION
        pipeline = d["pipeline"].to_numpy(float) / MILLION + np.minimum(net_storage, 0)
        withdrawal = np.maximum(net_storage, 0)
        citygate = d["citygate"].to_numpy(float) / MILLION
        demand = d["demand"].to_numpy(float) / MILLION
        if not np.allclose(pipeline + withdrawal + citygate, demand, atol=1e-7):
            raise ValueError(f"{market}: supply mix does not add up to demand")
        if np.any(pipeline < -1e-7):
            raise ValueError(f"{market}: pipeline supply net of injection is negative")

        ax.bar(x, pipeline, width=0.69, color=BLUE)
        ax.bar(x, withdrawal, bottom=pipeline, width=0.69, color=GREEN)
        ax.bar(x, citygate, bottom=pipeline + withdrawal, width=0.69, color=ORANGE)
        style_axes(ax)
        ax.set_ylim(0, 2.15)  # Same scale for a fair NY / NJ / PA comparison.
        ax.set_ylabel(f"{market}  |  Million Dth", fontsize=10)
    axes[-1].set_xticks(x, TICKS)
    axes[-1].set_xlabel("Month (Apr 2025–Mar 2026)", labelpad=7)
    fig.suptitle("Monthly supply mix", fontsize=15, fontweight="semibold", y=.99)
    fig.legend(handles=[Patch(color=BLUE, label="Pipeline to customers"),
                        Patch(color=GREEN, label="NY storage withdrawal"),
                        Patch(color=ORANGE, label="Citygate purchase")],
               loc="upper center", bbox_to_anchor=(.5, .955), ncol=3,
               frameon=False, fontsize=9)
    fig.text(.11, .018,
             "Stack height = contracted demand. NY pipeline supply excludes gas injected into NY storage.",
             fontsize=8.5, color=GRAY)
    fig.subplots_adjust(top=.88, bottom=.105, left=.15, right=.98, hspace=.26)
    save(fig, output_dir, "01_supply_mix.png")


def plot_storage_inventory(plan, storage, output_dir):
    """One plot: end-of-month inventories, with dashed capacity limits."""
    plan = plan.set_index("month").loc[MONTHS]
    caps = storage.set_index("field")["capacity_dth"]
    x = np.arange(12)
    fig, ax = plt.subplots(figsize=(10.5, 4.7))
    for f, color, name in [("H", BLUE, "PA hub (H)"), ("M", GREEN, "NY market (M)")]:
        ax.plot(x, plan[f"inv {f}"].to_numpy(float) / MILLION, "-o",
                color=color, linewidth=1.8, markersize=4, label=f"{name} inventory")
        ax.axhline(caps.loc[f] / MILLION, color=color, linestyle="--",
                   linewidth=1.2, label=f"{name} capacity")
    style_axes(ax)
    ax.set_xticks(x, TICKS)
    ax.set_xlabel("Month (Apr 2025–Mar 2026)", labelpad=8)
    ax.set_ylabel("End-of-month inventory (million Dth)", labelpad=7)
    ax.set_ylim(0, 2.48)
    fig.suptitle("Storage inventory", fontsize=15, fontweight="semibold", y=.98)
    handles, labels = ax.get_legend_handles_labels()
    labels = ["PA hub inventory", "PA hub capacity", "NY market inventory", "NY market capacity"]
    fig.legend(handles, labels, frameon=False, ncol=4, fontsize=9,
               loc="upper center", bbox_to_anchor=(.53, .91))
    fig.subplots_adjust(top=.80, bottom=.14, left=.12, right=.98)
    save(fig, output_dir, "02_storage_inventory.png")


def plot_price_vs_storage(plan, prices, output_dir):
    """Top: hub price. Bottom: total net injection (+) or withdrawal (-)."""
    plan = plan.set_index("month").loc[MONTHS]
    chronological_months = (pd.date_range("2025-04-01", periods=12, freq="MS")
                            .strftime("%Y-%m").tolist())
    prices = prices.set_index("month").loc[chronological_months]
    price = prices["pa_hub"].to_numpy(float)
    net = ((plan["inj H"] + plan["inj M"] - plan["wd H"] - plan["wd M"])
           .to_numpy(float) / MILLION)
    x = np.arange(12)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10.5, 6.4), sharex=True)
    ax1.plot(x, price, "-o", color=BLUE, markersize=4, linewidth=1.8)
    style_axes(ax1)
    ax1.set_ylim(0, 8.0)
    ax1.set_ylabel("Hub price ($/Dth)", labelpad=8)
    ax1.set_title("A. Hub purchase price", fontsize=11, loc="left", pad=9)

    ax2.bar(x, net, width=.68, color=[GREEN if v >= 0 else ORANGE for v in net])
    ax2.axhline(0, color=GRAY, linewidth=.8)
    style_axes(ax2)
    ax2.set_ylabel("Net storage flow (million Dth)", labelpad=8)
    ax2.set_title("B. Combined storage flow (H + M)", fontsize=11, loc="left", pad=9)
    ax2.set_xticks(x, TICKS)
    ax2.set_xlabel("Month (Apr 2025–Mar 2026)", labelpad=8)
    ax2.legend(handles=[Patch(color=GREEN, label="Injection (+): filling"),
                        Patch(color=ORANGE, label="Withdrawal (−): drawing down")],
               loc="lower left", frameon=False, fontsize=9, ncol=2)
    fig.suptitle("Hub price vs. storage decisions", fontsize=15,
                 fontweight="semibold", y=.99)
    fig.subplots_adjust(top=.89, bottom=.10, left=.15, right=.98, hspace=.40)
    save(fig, output_dir, "03_price_vs_storage.png")


def main(root=Path(".")):
    root = Path(root)
    out = root / "outputs" / "figures"
    supply = pd.read_csv(root / "outputs" / "market_supply.csv")
    plan = pd.read_csv(root / "outputs" / "monthly_plan.csv")
    storage = pd.read_csv(root / "data" / "processed" / "storage.csv")
    prices = pd.read_csv(root / "data" / "processed" / "prices.csv")
    plot_supply_mix(supply, out)
    plot_storage_inventory(plan, storage, out)
    plot_price_vs_storage(plan, prices, out)


if __name__ == "__main__":
    main()
