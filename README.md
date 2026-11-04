# Mid-Atlantic Gas Merchant: Storage, Transport and Procurement Optimization

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/robjiakai/MidAtlanticGasMerchant/blob/main/run_model.ipynb)

A multi-period linear program, solved with Gurobi, that plans one storage year (April 2025 – March 2026) for a natural gas merchant serving New York, New Jersey and Pennsylvania. Each month it decides how much gas to buy at the Appalachian hub, how much to inject into or withdraw from storage, how much to ship on each pipeline, how much firm capacity to hold, and how much to buy at each market's citygate price, at minimum total cost.

*IEOR E4004 Optimization Models and Methods, Columbia University, Fall 2026. Team 23.*

## The problem

The merchant buys Marcellus/Utica gas at Eastern Gas South and sells it under fixed contracts in NY, NJ and PA, so minimizing supply cost maximizes margin. Winter is the hard part: demand roughly doubles from shoulder months to January, just as pipelines into New York tighten. The model chooses the cheapest mix of three ways to cover it:

| Lever | Cost profile |
|---|---|
| Firm pipeline capacity | Reservation charge paid every month, used or not |
| Summer storage fills | Pays off when the summer–winter spread exceeds storage fees |
| Citygate (spot) purchases | No fixed cost, highest unit price |

Dual values price each bottleneck, e.g. the annual value of one more Dth/day of New York pipeline capacity.

## Model

| | |
|---|---|
| Type | LP, all variables continuous and non-negative |
| Horizon | 12 months, April 2025 – March 2026 |
| Network | Hub → 4 routes → 3 markets; storage at the hub (`H`) and in New York (`M`) |
| Routes | 1 Empire → NY · 2 National Fuel → NY · 3 Tennessee → NJ · 4 Texas Eastern → PA |
| Variables | hub purchases `x`, shipments `s`, injections `qin`, withdrawals `qout`, inventory `I`, citygate purchases `u`, firm capacity `k` |
| Constraints | `HB` hub balance · `DM` market balance · `IB` inventory balance · `PC` pipeline capacity · `KC` accessible capacity · `SL_in`/`SL_out`/`SL_cap` storage limits · `CI` cyclic inventory |
| Size | 172 variables, 198 constraints (fits the free size-limited Gurobi license) |

Constraint names in the code match the written formulation. The full model, parameter sources and assumptions are in [`writeups/`](writeups/).

## Quick start

**Colab:** click the badge, then *Runtime → Run all*. The first cell clones the repo and installs `gurobipy`.

**Locally:**

```bash
git clone https://github.com/robjiakai/MidAtlanticGasMerchant.git
cd MidAtlanticGasMerchant
pip install -r requirements.txt notebook
jupyter notebook run_model.ipynb      # or: python model.py
```

Tested with Python 3.13 and `gurobipy` 13.0.3. No academic license is needed. Run from the repository root.

## Repository

```
run_model.ipynb      Entry point: load → validate → solve → report
model.py             Gurobi formulation: build_model(), solve()
validate.py          Input checks and independent solution checks
visualizations.py    Figures (Milestone 5, not yet implemented)
src/
  load_data.py       data/processed/ → model input dict
  prep_demand.py     raw workbook → demand.csv
  prep_storage.py    EIA exports + workbook → storage.csv
data/
  raw/               Source downloads and estimation workbooks
  processed/         Clean CSVs; the only data the model reads
    ranges/          Low/base/high values for sensitivity analysis
outputs/             Tables written by the notebook
writeups/            Milestone reports and assumption notes
```

## Data

```
data/raw/ → src/prep_*.py → data/processed/*.csv → src/load_data.py → model.py → outputs/
```

Everything from `data/processed/` onward is code and reproducible. Upstream, some steps are manual:

| Processed file | Produced by | Scripted? |
|---|---|---|
| `demand.csv` | `prep_demand.py`, from the team workbook in `data/raw/demand-raw/` | Partly (workbook → CSV) |
| `storage.csv` | `prep_storage.py`, from EIA exports and a hand-compiled fee workbook | Partly (workbook → CSV) |
| `prices.csv` | Eastern Gas South index and EIA citygate prices, compiled by hand | Not yet |
| `Pipeline_data_cleaned.csv` | FERC eTariff filings, compiled by hand | Not yet |
| `routes.csv` | `python src/load_data.py --write-routes` | Yes |
| `months.csv` | Calendar table | Static |

Hand-entered values are documented with sources in the Milestone 3 report and [`writeups/demand_storage_assumptions.md`](writeups/demand_storage_assumptions.md).

**Conventions.** Months are `YYYY-MM`, volumes in Dth (1 Dth = 1 MMBtu), prices and fees in $/Dth, markets `NY`, `NJ`, `PA`.

**Derived parameters** (in `load_data.py`):

- **Reservation charge `R`:** average of the 12 monthly tariff rates, so Empire's November 1 change is month-weighted.
- **Accessible capacity `kbar`:** each market's average daily demand split equally across its routes (assumption A9). Stored in `routes.csv`; rerun `--write-routes` if demand or tariffs change. For scenarios, pass `load_data(capacity_limits={route: Dth_per_day})`.
- **Fuel retention `phi`:** 0 on every route (A11, deferred).

**Checks.** `load_data()` enforces the CSV schema (columns, missing values, duplicates, calendar, markets) and calls `validate_inputs()`. After solving, `validate_solution()` recomputes every constraint residual and cost term from the solution.

## Sources

| Data | Source |
|---|---|
| State deliveries, citygate prices, storage capacity and inventories | [U.S. EIA](https://www.eia.gov/naturalgas/data.php) |
| Pipeline tariffs | [FERC eTariff](https://etariff.ferc.gov) |
| Storage fees | National Fuel Gas Supply, Firm Storage Service tariff |
| Hub price | S&P Global Platts *Gas Daily*, Eastern Gas South |
| Book size benchmark | New Jersey Resources Corp. Form 10-K, FY2025 |

## Status

| Milestone | Due | Status |
|---|---|---|
| 1. Literature review | Sep 23 | ✅ |
| 2. Problem definition and data | Oct 7 | ✅ |
| 3. Parameters and draft model | Oct 21 | ✅ |
| 4. Complete model and code | Nov 4 | ✅ |
| 5. Results and sensitivity | Nov 18 | ⏳ |
| 6. Final report and reproducibility | Dec 2 | ⏳ |

Open before Milestone 5: `prep_prices.py`, `prep_pipelines.py`, figures in `visualizations.py`, fuel retention.

## Team

| Member | Owns |
|---|---|
| Rob | `model.py`, `run_model.ipynb` |
| Tianyi | `prep_pipelines.py` |
| Rongjia Jasper | `prep_demand.py`, `prep_storage.py` |
| Jingrong Christine | `prep_prices.py` |
| Anthony | `load_data.py`, `validate.py` |

Edit only the files you own, commit processed CSVs with the script that made them, and pull before you push. Only Rob edits `run_model.ipynb`.
