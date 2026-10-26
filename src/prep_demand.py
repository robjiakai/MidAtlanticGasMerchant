"""
prep_demand.py
Owner: Rongjia

PURPOSE
    Turn the merchant demand estimates (EIA monthly state deliveries scaled by
    merchant shares alpha_j) into one clean CSV the model can read. This script
    reads your final estimates from data/raw/demand/ and reshapes them; it does
    not need to redo the estimation.

INPUTS
    data/raw/demand/      EIA downloads, your estimation notebook/Excel, and
                          the final monthly demand table, committed as-is.

OUTPUT
    data/processed/demand.csv    36 rows (12 months x 3 markets), these columns:

    month        str    YYYY-MM, 2025-04 .. 2026-03 (must match months.csv)
    market       str    NY | NJ | PA
    demand_dth   float  merchant's contracted demand that month, Dth   (D_j,t)

    Conversion: EIA volumes in Mcf -> Dth at 1.037 Dth/Mcf (1 MMcf = 1,037 Dth).

ALSO OWED
    1. Document the five imputed months (which ones, and the method) in a
       comment in this script and in the report.
    2. data/processed/ranges/demand_ranges.csv with columns
       parameter, base, low, high, rationale
       (at minimum book size / alpha_j and a winter demand shock), for Milestone 5.
    3. Your Milestone 4 report section (demand + storage): final parameter
       table and assumptions.

RULES
    - Run from the repo root:  python src/prep_demand.py
    - Relative paths only.
    - Re-running must reproduce demand.csv exactly. Never edit the CSV by hand.

DUE: Thu Oct 29 (pull request to main; Rob reviews)
"""


def main() -> None:
    """Read final estimates from data/raw/demand/ and write data/processed/demand.csv."""
    raise NotImplementedError


if __name__ == "__main__":
    main()
