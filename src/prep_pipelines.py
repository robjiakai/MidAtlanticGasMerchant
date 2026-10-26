"""
prep_pipelines.py
Owner: Tianyi

PURPOSE
    Turn the pipeline tariff research (FERC eTariff: Empire, National Fuel Gas
    Supply, Tennessee Gas Pipeline) into one clean CSV the model can read.
    This script does NOT redo the research; it reads your final estimates from
    data/raw/pipelines/ and reshapes them into the standard format.

INPUTS
    data/raw/pipelines/   Your original source files, notebooks/Excel, and the
                          final estimates table, committed as-is.

OUTPUT
    data/processed/routes.csv    4 rows, one per route, exactly these columns:

    route                  int    1..4
    market                 str    NY | NJ | PA        (routes 1-2 NY, 3 NJ, 4 PA)
    pipeline               str    pipeline name
    usage_charge           float  $/Dth shipped                       (c_l)
    reservation_charge     float  $ per Dth/day of capacity per month (R_l),
                                  month-weighted across the Nov 1 rate change
    full_capacity_dth_day  float  pipeline's full firm capacity, Dth/day (K_l)
    access_share           float  merchant's accessible share, 0-1    (beta_l)
    fuel_rate              float  fuel retention fraction, 0-1        (phi_l; 0 for now)

    Accessible capacity used by the model is kbar_l = access_share * full_capacity.

ALSO OWED
    1. Route 4 (PA): identify the pipeline and verify c4, R4, K4. If a value
       cannot be verified, keep the Milestone 3 placeholder (kbar_4 = 25,570
       Dth/day) and state that clearly in the assumptions.
    2. data/processed/ranges/pipelines_ranges.csv with columns
       parameter, base, low, high, rationale
       (at minimum access_share and reservation_charge), for Milestone 5.
    3. Your Milestone 4 report section: final parameter table and assumptions.

RULES
    - Run from the repo root:  python src/prep_pipelines.py
    - Relative paths only (no C:\\Users\\... or /Users/...).
    - Units: Dth and $/Dth throughout (1 Dth = 1 MMBtu).
    - Re-running must reproduce routes.csv exactly. Never edit the CSV by hand.

DUE: Thu Oct 29 (pull request to main; Rob reviews)
"""


def main() -> None:
    """Read final estimates from data/raw/pipelines/ and write data/processed/routes.csv."""
    raise NotImplementedError


if __name__ == "__main__":
    main()
