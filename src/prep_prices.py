"""
prep_prices.py
Owner: Jingrong

PURPOSE
    Turn the price research (Eastern Gas South monthly hub index; EIA citygate
    prices by state) into two clean CSVs the model can read. This script reads
    your final price tables from data/raw/prices/ and reshapes them.

INPUTS
    data/raw/prices/      Source downloads, your notebook/Excel, and the final
                          monthly price tables, committed as-is.

OUTPUTS
    data/processed/hub_price.csv        12 rows
        month   str    YYYY-MM, 2025-04 .. 2026-03 (must match months.csv)
        price   float  Eastern Gas South monthly index, $/Dth      (P_t)

    data/processed/citygate_price.csv   36 rows (12 months x 3 markets)
        month   str    YYYY-MM
        market  str    NY | NJ | PA
        price   float  EIA citygate price, $/Dth                   (pi_j,t)

    Conversion: EIA citygate prices are in $/Mcf -> divide by 1.037 for $/Dth.
    Hub index in $/MMBtu is already $/Dth.

ALSO OWED
    1. Missing citygate months (PA Aug 2025 and Feb 2026, NY Mar 2026) are
       linearly interpolated: do it in this script and say so in a comment.
    2. data/processed/ranges/prices_ranges.csv with columns
       parameter, base, low, high, rationale
       (e.g. winter hub price, NY winter citygate premium), for Milestone 5.
       If you can, also save a few historical winters (e.g. 2021-22 .. 2024-25)
       to data/raw/prices/: the Monte Carlo will sample from them.
    3. Your Milestone 4 report section: final price table and assumptions.

RULES
    - Run from the repo root:  python src/prep_prices.py
    - Relative paths only.
    - Re-running must reproduce both CSVs exactly. Never edit them by hand.

DUE: Thu Oct 29 (pull request to main; Rob reviews)
"""


def main() -> None:
    """Read final price tables from data/raw/prices/ and write the two price CSVs."""
    raise NotImplementedError


if __name__ == "__main__":
    main()
