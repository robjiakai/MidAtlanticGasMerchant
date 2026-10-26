"""
validate.py
Owner: Anthony

PURPOSE
    Catch bad inputs before the model is built, and nonsense outputs after it
    solves ("the solver returned a number" is not the same as "the model is
    correct"). Every check prints a clear message naming the file/parameter
    and the offending value.

DUE: validate_inputs by Fri Oct 30; validate_solution by Tue Nov 3
     (it needs Rob's model.py, so agree on the solution format with Rob).
"""


def validate_inputs(data: dict) -> list[str]:
    """Check the dict returned by load_data() before building the model.

    Checks (at minimum):
      - every key in the load_data() docstring is present
      - 12 months for every time-indexed parameter; 3 markets x 12 for D and pi
      - no NaN, no negative volumes, capacities, rates or prices
      - 0 <= I0[f] <= Ibar[f] for every field
      - access shares and fuel rates within [0, 1]
      - days sum to 365
      - every market is reachable by at least one route or field (L_j, F_j)
      - order-of-magnitude checks (e.g. monthly demand between 1e5 and 1e8 Dth,
        prices between $0.5 and $50/Dth) to catch unit-conversion errors

    Returns a list of problems found (empty list = all good). Prints each one.
    """
    raise NotImplementedError


def validate_solution(solution: dict, data: dict, tol: float = 1e-6) -> list[str]:
    """Check an optimal solution from model.py against the data.

    Checks (at minimum):
      - demand met exactly in every market and month
      - inventory within [0, Ibar] every month, and ending = starting (cyclic)
      - shipments within days[t] * capacity contracted; capacity <= kbar
      - injections/withdrawals within daily rate limits
      - objective equals the sum of its cost components (recomputed here)
      - plausibility flags, printed as warnings rather than errors:
        storage injecting mostly in summer and withdrawing in winter;
        spot purchases concentrated in peak winter months

    Returns a list of problems found (empty list = all good). Prints each one.
    """
    raise NotImplementedError
