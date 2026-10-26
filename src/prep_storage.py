"""
prep_storage.py
Owner: Rongjia

PURPOSE
    Turn the storage estimates (EIA working-gas capacity and March 2025
    inventories, National Fuel FSS fees, UGI/Crestwood injection and withdrawal
    rates) into one clean CSV the model can read. This script reads your final
    estimates from data/raw/storage/ and reshapes them.

INPUTS
    data/raw/storage/     Source files, your estimation notebook/Excel, and the
                          final storage parameter table, committed as-is.

OUTPUT
    data/processed/storage.csv    2 rows, one per leased field, these columns:

    field            str    H (hub, PA) | M (market area, NY)
    market           str    HUB for H, NY for M
    capacity_dth     float  leased working-gas capacity, Dth        (Ibar_f)
    init_inv_dth     float  inventory at start of April 2025, Dth   (I_f,0)
    max_inj_dth_day  float  maximum injection rate, Dth/day         (r_in_f)
    max_wd_dth_day   float  maximum withdrawal rate, Dth/day        (r_out_f)
    inj_fee          float  injection charge, $/Dth                 (c_in_f)
    wd_fee           float  withdrawal charge, $/Dth                (c_out_f)

    Must hold: 0 <= init_inv_dth <= capacity_dth.

ALSO OWED
    data/processed/ranges/storage_ranges.csv with columns
    parameter, base, low, high, rationale
    (at minimum the leased shares behind capacity_dth, and the rate limits),
    for Milestone 5. Report section is shared with prep_demand.py.

RULES
    - Run from the repo root:  python src/prep_storage.py
    - Relative paths only. Units: Dth and $/Dth.
    - Re-running must reproduce storage.csv exactly. Never edit the CSV by hand.

DUE: Thu Oct 29 (pull request to main; Rob reviews)
"""


def main() -> None:
    """Read final estimates from data/raw/storage/ and write data/processed/storage.csv."""
    raise NotImplementedError


if __name__ == "__main__":
    main()
