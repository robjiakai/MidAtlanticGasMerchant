# Demand and Storage: Parameter Estimation and Assumptions

## 1. Merchant Demand

**Source:** EIA monthly natural gas delivered to consumers, April 2025–March 2026.

We assume an annual contracted demand of 30 Bcf for a large natural gas merchant's Northeast regional division, using NJR Energy Services and publicly reported BP Energy transactions as industry benchmarks. The assumed annual volume is allocated across NY (45%), NJ (25%), and PA (30%), giving 13.5, 7.5, and 9.0 Bcf, respectively.

Merchant shares are estimated by dividing the assumed annual contracted volume in each state by its annual EIA delivered volume:

- NY: 0.9751%
- NJ: 1.0461%
- PA: 0.5379%

Monthly contracted demand is calculated as:

\(D_{j,t} = \text{EIA Monthly Volume}_{j,t} \times \alpha_j \times 1037\)

where EIA volumes are in MMcf and demand is converted into Dth.

**Missing data:** Five observations were estimated using corresponding 2024 monthly values adjusted by estimated historical year-over-year growth: NJ (July, August, October 2025) and PA (November, December 2025).

## 2. Storage Capacity and Initial Inventory

**Source:** EIA March 2025 state-level working gas capacity and inventory.

We assume the merchant leases 0.5% of PA's working gas capacity and 1.0% of NY's. These percentages represent preliminary regional operating-scale assumptions.

The initial fill ratios are based on actual March 2025 statewide inventory-to-capacity ratios: 29.74% for PA and 33.62% for NY.

The resulting model parameters are:

| Parameter | PA Hub | NY Market |
|---|---:|---:|
| Leased capacity (Dth) | 2,210,500 | 1,298,303 |
| Initial inventory (Dth) | 657,453 | 436,473 |

## 3. Maximum Injection and Withdrawal Rates

PA's maximum injection rate is estimated using UGI Storage's Tioga-Mansfield facility as a benchmark. NY's injection rate uses the historical injection-to-capacity ratio of Thomas Corners.

Withdrawal rates are estimated from the 2024 EIA-191 field-level storage data, using the median withdrawal-to-capacity ratios for operating facilities in each state.

The observed facility ratios are scaled to our assumed leased capacities:

| Parameter | PA Hub | NY Market |
|---|---:|---:|
| Maximum injection (Dth/day) | 12,280 | 12,983 |
| Maximum withdrawal (Dth/day) | 50,054 | 25,966 |

These are benchmark-based estimates, not actual contracted operating limits.

## 4. Storage Operating Costs

**Source:** National Fuel's published 2025 Firm Storage Service tariff.

We assume constant unit injection and withdrawal costs of $0.0381/Dth at both facilities. Additional surcharges and fuel-related charges are excluded.

## 5. Sensitivity Analysis

Merchant shares are tested at ±20% of their base values. Winter demand shocks are tested up to +20% for November–March, with zero additional shock in the base case.

Storage lease shares and daily operating limits are also tested at ±20%. Where lease shares are varied as an integrated storage-scale scenario, capacity, initial inventory, and operating limits should be adjusted consistently.

All sensitivity ranges are modeling scenarios, not statistical confidence intervals.

## 6. Modeling Limitations

Merchant shares and leased storage proportions are assumptions rather than actual company contracts. Statewide EIA data and individual facility benchmarks are used as proxies for regional operations. Storage operating limits are treated as constant, although actual injection and withdrawal capabilities may depend on inventory levels and contract terms.