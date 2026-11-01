# Mid-Atlantic Gas Merchant: Storage, Transport and Procurement Optimization

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/robjiakai/MidAtlanticGasMerchant/blob/main/run_model.ipynb)

A multi-period linear program, solved with Gurobi, that plans one storage year (April 2025 – March 2026) for a natural gas merchant serving New York, New Jersey and Pennsylvania. Each month the model decides how much gas to buy at the Appalachian supply hub, how much to inject into or withdraw from leased storage, how much to ship on each firm pipeline route, how much firm capacity to hold, and how much to buy at each market's citygate price. The objective is minimum total cost.

*IEOR E4004 Optimization Models and Methods, Columbia University, Fall 2026. Team 23.*

---

## The business problem

The merchant, modeled on a major's U.S. gas marketing desk, buys Marcellus/Utica gas at Eastern Gas South and sells it under fixed contracts to wholesale customers in NY, NJ and PA. Because sale volumes and prices are fixed, minimizing supply cost is the same as maximizing margin.

The hard part is winter. Demand roughly doubles from shoulder months to January, and pipelines into New York are constrained exactly when demand peaks. The merchant has three ways to cover winter demand, each with a different cost profile:

| Lever | Pays for itself when… |
|---|---|
| **Firm pipeline capacity** | it is used year-round, since reservation charges are paid every month whether used or not |
| **Summer storage fills** | the summer–winter price spread exceeds storage fees, and summer pipeline capacity would otherwise sit idle |
| **Citygate (spot) purchases** | peaks are short, since there is no fixed cost but the unit price is highest |

The model finds the cost-minimizing mix of these levers. Its dual values price each bottleneck, for example how much one more Dth/day of New York capacity would be worth.

## Model at a glance

| | |
|---|---|
| **Type** | Linear program (all variables continuous and non-negative) |
| **Horizon** | 12 monthly periods, April 2025 – March 2026 |
| **Network** | 1 supply hub → 4 firm pipeline routes → 3 markets; leased storage at the hub (`H`) and in New York (`M`) |
| **Routes** | 1 Empire Pipeline → NY; 2 National Fuel Gas Supply → NY; 3 Tennessee Gas Pipeline → NJ; 4 Texas Eastern Transmission → PA |
| **Decisions** | hub purchases `x`, route shipments `s`, storage injections `qin`, withdrawals `qout` and inventory `I`, citygate purchases `u`, firm capacity `k` |
| **Objective** | minimize hub purchases + pipeline usage + storage fees + citygate purchases + pipeline reservation charges |
| **Constraints** | `HB` hub balance, `DM` market balance, `IB` inventory balance, `PC` pipeline capacity, `KC` accessible capacity, `SL_in` / `SL_out` / `SL_cap` storage limits, `CI` cyclic inventory |
| **Size** | 172 variables, 198 constraints; well within the size-limited licence that ships with `gurobipy` |

Constraint names in the code match the labels in the written formulation. `KC` (contracted capacity ≤ accessible capacity) is written as a constraint rather than a variable bound so that its dual, the value of one more Dth/day of accessible capacity, is reported. The full formulation, parameter sources and modeling assumptions are in the Milestone 3 and 4 reports in [`writeups/`](writeups/).

## Quick start

**In Google Colab (no setup).** Click the badge above, then *Runtime → Run all*. The first cell clones this repository and installs `gurobipy` only; numpy, pandas and matplotlib come preinstalled in Colab. The notebook does not reinstall them, because downgrading packages inside a running Colab session can break imports until the runtime is restarted.

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

From the command line, `python model.py` solves the baseline and prints the cost breakdown.

`requirements.txt` pins the versions the model was tested with (Python 3.13, `gurobipy` 13.0.3). `gurobipy` installs with a size-limited licence that is sufficient for this model; no academic licence is required.

## Repository structure

```
MidAtlanticGasMerchant/
├── run_model.ipynb          # Entry point: load → validate → solve → report (tables only)
├── model.py                 # Gurobi formulation; build_model() and solve()
├── validate.py              # Input checks and solution feasibility checks
├── visualizations.py        # Figure stubs for Milestone 5 (not yet implemented)
├── requirements.txt         # Pinned dependencies for local runs
│
├── src/
│   ├── load_data.py         # Reads data/processed/ into the model's input dict
│   ├── prep_demand.py       # raw workbook → data/processed/demand.csv
│   └── prep_storage.py      # raw EIA exports + workbook → data/processed/storage.csv
│
├── data/
│   ├── raw/                 # Source downloads and the team's estimation workbooks
│   └── processed/           # Clean CSVs; the only data the model reads
│       └── ranges/          # Low/base/high values for sensitivity analysis
│
├── outputs/                 # Tables written by the notebook
└── writeups/                # Milestone reports and assumption notes
```

### How data flows

```
data/raw/  ──►  src/prep_*.py  ──►  data/processed/*.csv  ──►  src/load_data.py  ──►  model.py  ──►  outputs/
```

The pipeline is only partly scripted. Some parameters were estimated in spreadsheets, and the price and pipeline tables were assembled by hand. From `data/processed/` onward, everything is code and fully reproducible. Upstream of it, the table below states what can and cannot be regenerated.

### Data provenance

| Processed file | How it was produced | Rerun by script? |
|---|---|---|
| `demand.csv`, `ranges/demand_ranges.csv` | `prep_demand.py` reads the team's estimation workbook (`data/raw/demand-raw/`). The EIA pulls, merchant shares and the five imputed months were computed in that workbook. | Partly: the script rebuilds the CSV from the workbook, not the workbook from EIA |
| `storage.csv`, `ranges/storage_ranges.csv` | `prep_storage.py` reads EIA capacity and inventory exports plus a hand-compiled workbook of rate limits and fees (`data/raw/storage/`). | Partly: same as demand |
| `prices.csv` | Compiled by hand from the Eastern Gas South monthly index and EIA citygate prices; missing citygate months linearly interpolated. | No (`prep_prices.py` not yet written) |
| `Pipeline_data_cleaned.csv` | Compiled by hand from FERC eTariff filings (Empire, National Fuel, Tennessee, Texas Eastern). | No (`prep_pipelines.py` not yet written) |
| `months.csv` | Calendar table (month, index, days). | Static |

Every hand-entered value is documented, with its source and method, in the Milestone 3 report and [`writeups/demand_storage_assumptions.md`](writeups/demand_storage_assumptions.md). For prices and pipelines, those write-ups, not scripts, are the audit trail. Processed files are committed, so the model can always be rerun from them exactly.

## Data contract

All files in `data/processed/` are CSVs. Months are labeled `YYYY-MM`, volumes are in **Dth** (1 Dth = 1 MMBtu), and prices and fees are in **$/Dth** unless stated otherwise. Markets are `NY`, `NJ`, `PA`.

| File | Columns | Rows |
|---|---|---|
| `months.csv` | `month, t, days` | 12 |
| `demand.csv` | `month, market, demand_dth` | 36 (long format) |
| `prices.csv` | `month, pa_hub, pa_citygate, ny_citygate, nj_citygate` | 12 (wide format; `pa_hub` is the Eastern Gas South hub price) |
| `storage.csv` | `field, market, capacity_dth, init_inv_dth, max_inj_dth_day, max_wd_dth_day, inj_fee, wd_fee` | 2 (`H` at market `HUB`, `M` at `NY`) |
| `Pipeline_data_cleaned.csv` | `Route, Market, Pipeline, Effective from, Effective to, Capacity (Dth/day), Usage ($/Dth), Reservation ($/Dth/day/month)` | One row per route and tariff period (5 rows; Empire's rate changes on Nov 1, 2025) |

### What `load_data.py` derives

- **Reservation charge `R`.** Tariff periods must tile each month with no gaps or overlaps and may not change within a month. The loader averages the 12 monthly rates per route, so Empire's Nov 1 change is weighted by months.
- **Accessible capacity `kbar`.** Not in any CSV. It comes from the `capacity_limits` argument, which defaults to `{1: 19178, 2: 19178, 3: 21308, 4: 25570}` Dth/day (each market's average daily demand split across its routes; Milestone 3, assumption A9). Pass `load_data(capacity_limits={...})` to run a scenario. The loader prints a warning reminding you these defaults are in use.
- **Fuel retention `phi`.** Set to 0 for every route (assumption A11, deferred).

The loader also accepts an optional `routes.csv` (`route, market, pipeline, usage_charge, reservation_charge, full_capacity_dth_day, access_share, fuel_rate`) in place of `Pipeline_data_cleaned.csv`, and optional `hub_price.csv` plus `citygate_price.csv` in place of `prices.csv`. If present, they take precedence. None are committed today.

### Checks

`load_data.py` enforces the schema: exact column names, no missing or non-numeric values, no duplicate keys, the April 2025 – March 2026 calendar with correct day counts, and the expected markets and storage fields. It then calls `validate.validate_inputs`, which checks every parameter's index set, non-negativity, the network mapping (`L_j`, `F_j`, `F0`), opening inventory within capacity, and warns on values outside plausible ranges.

After solving, `validate.validate_solution` recomputes every constraint residual from the solution values, recomputes each cost term and the objective, and warns if storage injections, withdrawals or citygate purchases fall in the unexpected season.

## Data sources

| Data | Source |
|---|---|
| Monthly state deliveries, citygate prices, storage capacity and inventories | [U.S. Energy Information Administration](https://www.eia.gov/naturalgas/data.php) |
| Pipeline tariffs (reservation, usage, capacity) | [FERC eTariff](https://etariff.ferc.gov) |
| Storage injection and withdrawal fees | National Fuel Gas Supply, Firm Storage Service tariff |
| Hub price (Eastern Gas South monthly index) | S&P Global Platts *Gas Daily* |
| Merchant book size benchmark | New Jersey Resources Corp. Form 10-K, FY2025 |

Full citations, imputation methods and assumptions are in the Milestone 3 report.

## Project status

| Milestone | Due | Status |
|---|---|---|
| 1. Literature review | Sep 23 | ✅ Done (individual) |
| 2. Problem definition and data exploration | Oct 7 | ✅ Done |
| 3. Parameter estimation and draft model | Oct 21 | ✅ Done |
| 4. Complete model and working code | Nov 4 | 🔄 In progress: model solves to optimality and passes all solution checks |
| 5. Results and sensitivity analysis (duals, scenarios, Monte Carlo) | Nov 18 | ⏳ |
| 6. Final report and reproducibility document | Dec 2 | ⏳ |

Open items before Milestone 5: `prep_prices.py`, `prep_pipelines.py`, the figures in `visualizations.py`, and fuel retention rates.

## Team and ownership

| Member | Responsibility for Week 4 |
|---|---|
| Rob | `model.py`, `run_model.ipynb` |
| Tianyi | `prep_pipelines.py` |
| Rongjia Jasper | `prep_demand.py`, `prep_storage.py` |
| Jingrong Christine | `prep_prices.py` |
| Anthony | `load_data.py`, `validate.py` |

**Contributing:** edit only the files you own. Commit processed CSVs together with the script that produced them, and pull before you push. Only Rob edits `run_model.ipynb`.
