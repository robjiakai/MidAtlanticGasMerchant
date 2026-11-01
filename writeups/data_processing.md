# Data loading and validation

Anthony's Milestone 4 contribution connects the uploaded tables to Rob's existing model. All new Python code uses the standard library, except the integration test which uses Gurobi. The loader returns the same 21 keys requested in its original interface.

## Run from the repository root

```bash
python -m pip install -r requirements.txt
python src/prep_demand.py
python src/prep_storage.py
python src/prepare_inputs.py
python src/load_data.py
python -m unittest discover -s tests -v
python model.py
```

The existing notebook can also run unchanged once the six standard processed CSVs are present. To validate the solution directly:

```python
from src.load_data import load_data
from model import solve
from validate import validate_solution

data = load_data()
solution = solve(data)
problems = validate_solution(solution, data)
if problems:
    raise ValueError(problems)
```

## Preparation and provenance

`prepare_inputs.py` compiles the already uploaded processed tables. It does not replace the other owners' preparation scripts or redo their price research. Keep `prices.csv` and `Pipeline_data_cleaned.csv` as source tables. They remain byte-for-byte unchanged.

`prices.csv` is split into `hub_price.csv` (12 rows) and `citygate_price.csv` (36 rows). Values are preserved exactly as uploaded in $/Dth; there is no second heat-content conversion or additional interpolation. The uploaded prices do not carry observation/imputation flags, so the compilation cannot independently establish which values were estimated. Christine's raw price preparation and provenance remain a separate team task.

`Pipeline_data_cleaned.csv` contains five tariff periods for four routes. Route 1's reservation charge is `(7 * 7.0333 + 5 * 6.9613) / 12 = 7.0033` per Dth/day per month. Paying this average for 12 months is equal to paying each effective monthly tariff while holding capacity constant all year. The compiler checks that each calendar day is covered once and rejects tariff gaps, overlaps, changes within a month, or changes in usage charges/capacity that this fixed-parameter model cannot represent.

The uploaded pipeline table omits merchant access shares and fuel fractions. `route_assumptions.csv` explicitly records the provisional ceilings previously presented in Team 23's Backup B: routes 1 and 2: 19,178 Dth/day each; route 3: 21,308; route 4: 25,570. Fuel fractions remain zero, as in the preliminary model. The compiler calculates `access_share = accessible_capacity / full_capacity`, and the loader calculates `kbar = access_share * full_capacity`. These are scenario assumptions, not verified merchant rights. Source: [Team 23 presentation, Backup B](https://docs.google.com/presentation/d/1cf0DS7NZ_i4Q7Pm7k9NFa1AVPWL4PoU-/edit?slide=id.p9#slide=id.p9). Route 4's exact tariff service and rate provenance still require verification by its data owner.

Demand and storage are read from Rongjia's merged processed CSVs. The actual storage inputs include finite daily injection/withdrawal limits and $0.0381/Dth fees. The older slide assumptions of unlimited rates and zero storage usage fees do not describe this implementation. See `demand_storage_assumptions.md` for those estimates.

## Loading and checking

`load_data.py` reads only processed CSVs. It maps month labels to integer periods, forms the route and storage location mappings, and returns ordinary dictionaries. It performs no imputation, optimization, or silent replacement with dummy data. Missing files fail visibly. Header errors, blank cells, duplicate indices, invalid months, nonfinite numbers, and invalid route shares/fuel rates are rejected before solving.

`validate_inputs` checks the complete model interface, all expected index combinations, the exact calendar, nonnegative finite parameters, storage opening inventory, fuel fractions, and network mappings. Unusual demand or price magnitudes produce warnings for unit review. Access shares are checked in the CSV loader because the fixed model interface returns only their product `kbar`.

`validate_solution` matches the dictionaries returned by `model.solve`. It independently recomputes hub balance, market deliveries including fuel, storage continuity, capacity limits, cyclic inventory, all five cost components, and the objective. It uses an absolute tolerance of 1e-6 by default. Timing patterns outside the expected storage/local-purchase seasons are warnings, not failures. It checks feasibility and costs; the solver's optimal status supplies the optimality claim.

## Verification on 2026-10-31

Eight unittest cases pass, including invalid CSVs, missing indices, invalid shares, fuel accounting, broken solution constraints/costs, deterministic compilation, and a real Gurobi solve of Rob's unchanged model. The compiled case has 172 variables and 198 constraints. The annual objective is approximately $103,971,659.78. This is a reproducibility check for this input snapshot, not a validated forecast or an independently verified company trading plan.

No WhatsApp export or private discussion content is included in the repository.
