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



from pathlib import Path
import csv
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]

INPUT_FILE = (
    ROOT / "data" / "raw" / "demand-raw"
    / "IEOR4004_Demand_Inventory_Updated.xlsx"
)

OUTPUT_FILE = ROOT / "data" / "processed" / "demand.csv"

MARKETS = ("NY", "NJ", "PA")

# Assumed annual merchant volumes, Bcf
ANNUAL_BCF = {
    "NY": 13.5,
    "NJ": 7.5,
    "PA": 9.0,
}

DTH_PER_MMCF = 1037

# DEMAND ASSUMPTIONS
# Source: EIA monthly natural gas deliveries, Apr 2025-Mar 2026.
# Annual merchant demand: 30 Bcf (assumed using NJR/BP benchmarks).
# Allocation: NY 45%, NJ 25%, PA 30%.
# Merchant shares are calculated from state annual EIA volumes.
#
# Five missing observations were imputed:
# NJ: Jul, Aug, Oct 2025
# PA: Nov, Dec 2025
# Method: historical same-month YoY growth adjustment.
#
# Conversion: 1 MMcf = 1,037 Dth (assumed heat content).
# See writeups/demand_storage_assumptions.md for details.
def main() -> None:
    workbook = load_workbook(
        INPUT_FILE, data_only=True, read_only=True
    )
    try:
        sheet = workbook["EIA_Demand"]
        observations = []

        for row in sheet.iter_rows(
            min_row=5, max_row=16,
            min_col=1, max_col=4, values_only=True
        ):
            month, ny, nj, pa = row

            observations.append({
                "month": str(month),
                "NY": float(ny),
                "NJ": float(nj),
                "PA": float(pa),
            })
    finally:
        workbook.close()

    expected_months = [
        f"{year}-{month:02d}"
        for year, start, end in [
            (2025, 4, 12),
            (2026, 1, 3),
        ]
        for month in range(start, end + 1)
    ]

    assert [r["month"] for r in observations] == expected_months

    # Calculate exact state-specific merchant shares.
    totals = {
        market: sum(r[market] for r in observations)
        for market in MARKETS
    }

    shares = {
        market: ANNUAL_BCF[market] * 1000 / totals[market]
        for market in MARKETS
    }

    results = []

    for row in observations:
        for market in MARKETS:
            demand = (
                row[market]
                * DTH_PER_MMCF
                * shares[market]
            )

            results.append({
                "month": row["month"],
                "market": market,
                "demand_dth": round(demand),
            })

    assert len(results) == 36
    assert all(r["demand_dth"] >= 0 for r in results)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open(
        "w", newline="", encoding="utf-8"
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["month", "market", "demand_dth"]
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"Created {OUTPUT_FILE} with {len(results)} rows.")
    print("Merchant shares:")
    for market in MARKETS:
        print(f"  {market}: {shares[market]:.6%}")


    # Demand sensitivity ranges for Milestone 5
    # Low and high are assumed scenarios, not statistical confidence intervals.

    ranges_file = (
        ROOT / "data" / "processed" / "ranges"
        / "demand_ranges.csv"
    )

    ranges_file.parent.mkdir(parents=True, exist_ok=True)

    with ranges_file.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=["parameter", "base", "low", "high", "rationale"]
        )
        writer.writeheader()

        for market in MARKETS:
            base = shares[market]

            writer.writerow({
                "parameter": f"alpha_{market}",
                "base": round(base, 8),
                "low": round(base * 0.8, 8),
                "high": round(base * 1.2, 8),
                "rationale": "Assumed +/-20% demand-share scenario"
            })
        writer.writerow({
            "parameter": "winter_demand_shock",
            "base": 0.00,
            "low": 0.00,
            "high": 0.20,
            "rationale": (
                "Assumed winter demand shock for Nov-Mar; "
                "scenario analysis only"
            )
        })
    print(f"Created {ranges_file}")

if __name__ == "__main__":
    main()

