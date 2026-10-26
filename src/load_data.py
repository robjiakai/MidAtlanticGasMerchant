"""
load_data.py
Owner: Anthony   (interface defined by Rob; do not change the return keys)

PURPOSE
    Single bridge between data/processed/*.csv and the Gurobi model. Reads the
    processed CSVs and returns plain Python dicts keyed by model indices, so
    model.py can write e.g. D[j, t] or kbar[l] directly, matching the
    Milestone 3 notation.

FIRST TASK (due Wed Oct 28)
    Create dummy versions of every processed CSV (format in the README "Data
    contract"; rough Milestone 3 numbers are fine) so load_data() and model.py
    can be tested before the real data lands. Put them in data/processed/
    and say in the commit message that they are dummies; the data owners'
    files will overwrite them.

RULES
    - Read only from data/processed/. Never from data/raw/.
    - No modeling logic here (no optimization, no imputation): load, index, convert.
    - Month labels (YYYY-MM) are mapped to t = 1..12 using months.csv.
    - Relative paths only. Must run in Colab from the repo root.

DUE: Fri Oct 30 working on the real CSVs (pull request; Rob reviews).
     Be ready to walk through the code at the TA check-in.
"""

DATA_DIR = "data/processed"


def load_data(data_dir: str = DATA_DIR) -> dict:
    """Load all model parameters from the processed CSVs.

    Parameters
    ----------
    data_dir : str
        Folder containing the processed CSVs (default: data/processed).

    Returns
    -------
    dict with exactly these keys (symbols as in the Milestone 3 report):

    Sets
        "T"     list[int]           months, [1, ..., 12] (t = 1 is 2025-04)
        "J"     list[str]           markets, ["NY", "NJ", "PA"]
        "L"     list[int]           routes, [1, 2, 3, 4]
        "F"     list[str]           storage fields, ["H", "M"]
        "L_j"   dict[str, list]     routes into each market,  e.g. {"NY": [1, 2], ...}
        "F_j"   dict[str, list]     fields in each market,    e.g. {"NY": ["M"], "NJ": [], "PA": []}
        "F0"    list[str]           fields at the hub,        ["H"]

    Time-indexed parameters
        "days"  dict[int, int]            days in month t
        "P"     dict[int, float]          hub price, $/Dth
        "D"     dict[(str, int), float]   demand D[j, t], Dth
        "pi"    dict[(str, int), float]   citygate price pi[j, t], $/Dth

    Route parameters (keyed by route l)
        "c"     dict[int, float]   usage charge, $/Dth
        "R"     dict[int, float]   reservation charge, $ per Dth/day per month
        "kbar"  dict[int, float]   accessible capacity = access_share * full capacity, Dth/day
        "phi"   dict[int, float]   fuel retention fraction

    Storage parameters (keyed by field f)
        "Ibar"  dict[str, float]   capacity, Dth
        "I0"    dict[str, float]   initial inventory, Dth
        "r_in"  dict[str, float]   max injection, Dth/day
        "r_out" dict[str, float]   max withdrawal, Dth/day
        "c_in"  dict[str, float]   injection fee, $/Dth
        "c_out" dict[str, float]   withdrawal fee, $/Dth
    """
    raise NotImplementedError


if __name__ == "__main__":
    data = load_data()
    for key, value in data.items():
        print(key, value)
