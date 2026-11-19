# Monte Carlo price analysis

Run `python monte_carlo.py` from the repository root after installing `requirements.txt`. It defaults to 2,000 scenarios, seed 4004, within-month correlation parameter 0.8, and outputs in `outputs/`. Tests run with `python -m unittest discover -s tests -v`.

This is a standalone runner for the team's existing `src/monte_carlo.py` and `model.py`. It adds full decision-variable recording and independent validation of every scenario solution. The existing notebook, solver, Monte Carlo module, historical price-statistics files, and published `mc_*` results are preserved.

## Inputs and sampling

The run uses the committed `data/processed/mc_means.csv` and `mc_vars.csv`, which the existing team implementation describes as monthly 2015–2024 means and sample variances. No provisional variances are estimated from the single baseline year. Means and variances are treated as $/Dth and ($/Dth)^2, matching the existing notebook. The raw historical series is not in the repository, so this analysis does not independently reconstruct those estimates or establish their original units. If citygate moments are in $/Mcf, run with `--citygate-units mcf`; the existing converter divides means by 1.037 and variances by 1.037 squared. It leaves the hub moments unchanged.

Each location-month price is lognormal with its specified mean and variance. A Gaussian copula uses correlation 0.8 between the latent normal variables within each month. This is an assumed correlation; it is not an estimated Pearson correlation of the resulting prices. Months are sampled independently. There is no estimated persistence or shared year-level weather process.

The runner uses independent price-year draws without moment matching. This makes the reported standard errors and normal-approximation confidence intervals for mean costs interpretable as Monte Carlo sampling uncertainty. These intervals do not describe uncertainty in estimated historical moments, input units, or the economic model. The existing notebook's separate 1,000-draw moment-matched correlation sweep is retained as a complementary analysis.

Demand, physical limits, fuel assumptions, fees, and contract obligations remain fixed across scenarios. Feasibility under price-only uncertainty is therefore structural: the baseline plan remains feasible when only objective coefficients change. Feasibility here does not establish robustness to supply failures or demand shocks.

## Three comparisons

- A: keep all decisions from the 2025–2026 baseline plan and reprice them under the simulated year.
- B: fix pipeline reservations at baseline levels and optimize the monthly operating decisions with the entire simulated price year known.
- C: optimize both reservations and operations with the entire simulated price year known.

B and C both have full-year price foresight. Their cost advantage over A is an information benchmark, not a guaranteed achievable trading profit. B minus C isolates the additional benefit of knowing the price year before reserving capacity, conditional on this model. A minus B includes the advantage of adapting operations with perfect price knowledge. A rolling-horizon or stochastic program would be needed to evaluate a realistic strategy that only sees prices as time passes.

## Results for the committed run

The 2025–2026 baseline cost is $103,971,952.58. Across the 2,000 sampled years:

- A mean cost is $91.119 million; its 5th–95th percentile range is $72.346–$115.485 million.
- B mean cost is $77.619 million; its 5th–95th percentile range is $64.159–$92.592 million.
- C mean cost is $77.616 million; its 5th–95th percentile range is $64.159–$92.592 million.
- Mean A minus B is $13.501 million, an operational perfect-information benchmark.
- Mean B minus C is about $2,814 per year, a capacity-commitment information benchmark.

The simulated price means differ from 2025–2026 actual prices. Therefore, comparing a simulated mean cost directly with the $103.972 million baseline confounds different price environments with different decisions. The paired A/B/C comparisons use the same simulated prices and avoid that mismatch. The exact expected cost of the fixed plan under the supplied means is $90.915 million; its simulated mean differs by about $204,430, within one Monte Carlo standard error ($306,041).

Pipeline reservations are stable in these scenarios. Under C, routes 1, 2, and 3 are at their accessible limits in 99.85%, 100%, and 100% of draws. Route 4 is at its limit in 64.3% of draws; its mean reservation is approximately 25,450 Dth/day versus its baseline of 25,570. This does not establish optimal reservations outside the assumed price distribution and capacity ceilings.

Operating decisions vary more substantially: the monthly hub-purchase and storage-inventory ranges are wide. Aggregate local purchases remain concentrated in winter. The CSV summaries contain results for all seven variable families, including injections and withdrawals separately. Capacity saturation and pipeline utilization are also recorded. Some operating decisions may have multiple equally good solutions; individual route allocations should not be overinterpreted as uniquely optimal.

## Files

- `outputs/monte_carlo_costs.csv`: paired costs for every draw.
- `outputs/monte_carlo_summary.csv`: means, standard deviations, quantiles, worst-5% mean cost (CVaR95), and Monte Carlo intervals for the means.
- `outputs/monte_carlo_decision_summary.csv`: 344 variable summaries (172 variables under each optimized policy), including baseline, mean, quantiles, positive shares, and relevant capacity-limit shares.
- `outputs/monte_carlo_sample_moments.csv`: target and sampled moments for all 48 location-month combinations.
- `outputs/monte_carlo_draws.npz`: the actual prices and all 172 decisions under B and C for each draw. Array column labels are in the run metadata.
- `outputs/monte_carlo_run.json`: seed, sampling assumptions, input hashes, validation count, column labels, and analytical fixed-plan expectation.
- `outputs/monte_carlo_cost.png`, `monte_carlo_decisions.png`, `monte_carlo_capacity.png`: plots for the report.

All 4,000 optimized scenario solutions passed independent balance, capacity, inventory, cyclic-inventory, nonnegativity, and cost checks. The scenario cost ordering A >= B >= C held within $0.001 throughout. Four regression tests also pass, covering baseline reproduction, fixed-capacity enforcement, lognormal moment conversion and reproducibility, an independent fresh-model solve at sampled prices, full variable coverage, and rejection of an invalid solution. This was executed with Gurobi 13.0.3, not a substitute LP solver.
