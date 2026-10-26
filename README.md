# Mid-Atlantic Gas Merchant: Storage, Transport and Procurement Optimization

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/robjiakai/MidAtlanticGasMerchant/blob/main/run_model.ipynb)

A multi-period linear program, solved with Gurobi, that plans one storage year (April 2025 – March 2026) for a natural gas merchant serving New York, New Jersey and Pennsylvania. Each month the model decides how much gas to buy at the Appalachian supply hub, how much to inject into or withdraw from leased storage, how much to ship on each firm pipeline route, how much firm capacity to hold, and how much to buy on the spot market at the customer's citygate, all at minimum total cost.

*IEOR E4004 Optimization Models and Methods, Columbia University, Fall 2026. Team 23.*

---

## The business problem

The merchant (modeled on a major's U.S. gas marketing desk) buys Marcellus/Utica gas at Eastern Gas South and sells it under fixed contracts to wholesale customers in NY, NJ and PA. Because sale volumes and prices are fixed, minimizing supply cost is the same as maximizing margin.

The hard part is winter. Demand roughly doubles from shoulder months to January, and pipelines into New York are constrained exactly when demand peaks. The merchant has three ways to cover winter demand, each with a different cost profile:

| Lever | Pays for itself when… |
|---|---|
| **Firm pipeline capacity** | it is used year-round, since reservation charges are paid every month whether used or not |
| **Summer storage fills** | the summer–winter price spread exceeds storage fees, and summer pipeline capacity would otherwise sit idle |
| **Winter spot (citygate) purchases** | peaks are short, since no fixed cost but the highest unit price |

The model finds the cost-minimizing mix of these levers. Its dual values price each bottleneck, for example how much one more Dth/day of New York capacity would be worth.

## Model at a glance

| | |
|---|---|
| **Type** | Linear program (all variables continuous) |
| **Horizon** | 12 monthly periods, April 2025 – March 2026 |
| **Network** | 1 supply hub → 4 firm pipeline routes → 3 markets (NY, NJ, PA); storage at the hub and in New York |
| **Decisions** | hub purchases, storage injections/withdrawals/inventory, route shipments, citygate spot purchases, firm capacity per route |
| **Objective** | minimize purchase + pipeline usage + storage fees + spot purchases + pipeline reservation charges |
| **Constraints** | hub balance, market demand balance, inventory balance, pipeline capacity, storage limits, cyclic (start = end) inventory |
| **Size** | ≈170 variables and ≈200 constraints, which fits Gurobi's free pip licence |

The full algebraic formulation, parameter sources and modeling assumptions are in [`writeups/`](writeups/).

## Quick start

**In Google Colab (no setup).** Click the badge above, then *Runtime → Run all*. The first notebook cell clones this repository and installs the dependencies.

**Locally.**

```bash
git clone https://github.com/robjiakai/MidAtlanticGasMerchant.git
cd MidAtlanticGasMerchant
conda create -n gasmerchant python=3.13 -y
conda activate gasmerchant
pip install -r requirements.txt
pip install notebook      # Jupyter is only needed locally; Colab provides it
jupyter notebook run_model.ipynb
```

`requirements.txt` is pinned to the package versions in the current Colab runtime (Python 3.13), so local and Colab results match. `gurobipy` installs with a size-limited licence that is sufficient for this model; no academic licence is required.

## Repository structure

```
MidAtlanticGasMerchant/
├── run_model.ipynb          # Entry point: load data → build model → solve → report
├── model.py                 # Gurobi formulation (sets, variables, constraints, objective)
├── validate.py              # Sanity checks on input data and on the solution
├── visualizations.py        # Network flow diagram and monthly charts of the solution
├── requirements.txt         # Pinned dependencies (matches Colab)
│
├── src/
│   ├── load_data.py         # Reads data/processed/*.csv into model-ready dicts/Series
│   ├── prep_demand.py       # raw → data/processed/demand.csv
│   ├── prep_storage.py      # raw → data/processed/storage.csv
│   ├── prep_pipelines.py    # raw → data/processed/routes.csv
│   └── prep_prices.py       # raw → data/processed/hub_price.csv, citygate_price.csv
│
├── data/
│   ├── raw/                 # Source files as downloaded (EIA, FERC, filings); never edited by hand
│   └── processed/           # Clean, standardized CSVs; the only data the model reads
│
├── outputs/                 # Solver results and figures written by the notebook
└── writeups/                # Milestone reports (problem definition, formulation, results)
```

### How data flows

```
data/raw/  ──►  src/prep_*.py  ──►  data/processed/*.csv  ──►  src/load_data.py  ──►  model.py  ──►  outputs/
```

Every number the model uses can be traced back to a raw source file through a script. Nothing is reformatted by hand. Rerunning the prep scripts reproduces `data/processed/` exactly.

## Data contract

All processed files are long-format CSVs. Months are labeled `YYYY-MM`, volumes are in **Dth** (1 Dth = 1 MMBtu), and prices and fees are in **$/Dth** unless stated otherwise. Markets are `NY`, `NJ`, `PA`.

| File | Columns | Rows |
|---|---|---|
| `months.csv` | `month, t, days` | 12 |
| `demand.csv` | `month, market, demand_dth` | 36 |
| `hub_price.csv` | `month, price` | 12 |
| `citygate_price.csv` | `month, market, price` | 36 |
| `storage.csv` | `field, market, capacity_dth, init_inv_dth, max_inj_dth_day, max_wd_dth_day, inj_fee, wd_fee` | 2 (`H` at hub, `M` in NY; hub field uses market `HUB`) |
| `routes.csv` | `route, market, pipeline, usage_charge, reservation_charge, full_capacity_dth_day, access_share, fuel_rate` | 4 (`reservation_charge` in $ per Dth/day per month) |

`validate.py` checks these files against this contract (column names, row counts, units, no missing values) before the model is built.

## Data sources

| Data | Source |
|---|---|
| Monthly state deliveries, citygate prices, storage capacity and inventories | [U.S. Energy Information Administration](https://www.eia.gov/naturalgas/data.php) |
| Pipeline and storage tariffs (reservation, usage, capacity) | [FERC eTariff](https://etariff.ferc.gov) |
| Hub price (Eastern Gas South monthly index) | S&P Global Platts *Gas Daily* |
| Merchant book size benchmark | New Jersey Resources Corp. Form 10-K, FY2025 |

Full citations, imputation methods and assumptions are in the Milestone 3 report.

## Project status

| Milestone | Due | Status |
|---|---|---|
| 1. Literature review | Sep 23 | ✅ Done (individual) |
| 2. Problem definition and data exploration | Oct 7 | ✅ Done |
| 3. Parameter estimation and draft model | Oct 21 | ✅ Done |
| 4. Complete model and working code | Nov 4 | 🔄 In progress |
| 5. Results and sensitivity analysis (duals, scenarios, Monte Carlo) | Nov 18 | ⏳ |
| 6. Final report and reproducibility document | Dec 2 | ⏳ |

## Team and ownership

| Member | Responsibility |
|---|---|
| Rob | Model formulation and implementation (`model.py`, `load_data.py`), notebook, integration |
| Tianyi | Pipeline routes and tariffs (`prep_pipelines.py`) |
| Rongjia | Demand and storage (`prep_demand.py`, `prep_storage.py`) |
| Christine | Hub and citygate prices (`prep_prices.py`) |
| Anthony | Data and solution checks (`validate.py`), visualizations (`visualizations.py`) |

**Contributing:** edit only the files you own. Commit processed CSVs together with the script that produced them, and pull before you push. Only Rob edits `run_model.ipynb`.
