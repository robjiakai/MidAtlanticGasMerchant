"""
visualizations.py
Owner:

PURPOSE
    Turn a solved model into figures a gas trading desk would read: where the
    gas came from each month, how storage was used, and which bottlenecks bind.
    These figures carry the Milestone 5 report and the Nov 23 presentation, so
    each one should answer one question and be readable without the math.

TIMING
    Not needed for Milestone 4. Start once model.py returns a solution
    (week of Nov 2); due with the Milestone 5 draft (Mon Nov 16).

RULES
    - matplotlib (and networkx for the network figure) only; see requirements.txt.
    - Every function takes the solution dict from model.py plus the data dict
      from load_data(), returns the matplotlib Figure, and optionally saves it to
      outputs/figures/<name>.png. No modeling logic here.
    - Label axes with units (Dth, $/Dth); months as Apr-25 .. Mar-26.
"""


def plot_supply_mix(solution: dict, data: dict, save: bool = False):
    """Stacked monthly bars per market: pipeline deliveries, storage withdrawals,
    and spot purchases meeting demand. The headline figure for the winter trade-off."""
    raise NotImplementedError


def plot_storage(solution: dict, data: dict, save: bool = False):
    """Inventory of each field over the 12 months, with capacity as a dashed line,
    plus injections/withdrawals as bars."""
    raise NotImplementedError


def plot_network(solution: dict, data: dict, month: int, save: bool = False):
    """Network diagram (hub, storage fields, routes, markets) for one month, with
    edge widths proportional to flow and saturated routes highlighted."""
    raise NotImplementedError


def plot_shadow_prices(solution: dict, data: dict, save: bool = False):
    """Dual values of the pipeline and storage capacity constraints:
    the marginal value of one more Dth/day of capacity. Milestone 5."""
    raise NotImplementedError
