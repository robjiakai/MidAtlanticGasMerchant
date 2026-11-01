"""
load_data.py
Owner: Anthony

Reads data/processed/ into the input dict used by model.py, enforcing the CSV
schema and then calling validate.validate_inputs().

ROUTES
    Route parameters come from data/processed/routes.csv when it exists.
    routes.csv is generated, not hand-edited:

        python src/load_data.py --write-routes

    builds it from Pipeline_data_cleaned.csv (tariffs) and demand.csv
    (accessible capacity, assumption A9). If routes.csv is absent, the same
    derivation runs in memory, so both paths give identical inputs.

    Derivation (Milestone 3, A9): firm capacity into each market equals that
    market's average daily demand, split equally across its routes,
        kbar_l      = sum_t D[j,t] / sum_t days[t] / |L_j|,   j = market of route l
        access_share = kbar_l / K_l
    Reservation charge R_l is the average of the 12 monthly tariff rates
    (month-weighted); fuel retention is 0 (assumption A11).

SCENARIOS
    load_data(capacity_limits={route: Dth/day, ...}) overrides kbar for the
    listed routes, whichever source the routes came from. Routes not listed
    keep their baseline value. Example, scaling all firm capacity by theta:

        base = load_data()["kbar"]
        data = load_data(capacity_limits={l: theta * v for l, v in base.items()})
"""

import calendar
import csv
import math
import sys
import warnings
from datetime import date
from pathlib import Path


DATA_DIR = "data/processed"
ROUTE_COLUMNS = ["route", "market", "pipeline", "usage_charge", "reservation_charge",
                 "full_capacity_dth_day", "access_share", "fuel_rate"]
MARKETS = ["NY", "NJ", "PA"]


def read_csv(folder, filename, columns, keys, numbers):
    path = Path(folder) / filename
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != columns:
            raise ValueError(f"{filename}: expected columns {columns}, got {reader.fieldnames}")
        rows = []
        seen = set()
        for line, row in enumerate(reader, 2):
            if None in row or any(value is None or not value.strip() for value in row.values()):
                raise ValueError(f"{filename}:{line}: missing value")
            row = {key: value.strip() for key, value in row.items()}
            identity = tuple(row[key] for key in keys)
            if identity in seen:
                raise ValueError(f"{filename}:{line}: duplicate key {identity}")
            seen.add(identity)
            for name in numbers:
                try:
                    value = float(row[name])
                except ValueError:
                    raise ValueError(f"{filename}:{line}: invalid {name}={row[name]!r}") from None
                if not math.isfinite(value):
                    raise ValueError(f"{filename}:{line}: nonfinite {name}={value}")
                row[name] = value
            rows.append(row)
    return rows


def read_months(folder):
    months = read_csv(folder, "months.csv", ["month", "t", "days"], ["month"], ["t", "days"])
    expected = [f"2025-{m:02d}" for m in range(4, 13)] + [f"2026-{m:02d}" for m in range(1, 4)]
    months.sort(key=lambda row: row["t"])
    if [row["month"] for row in months] != expected or [row["t"] for row in months] != list(range(1, 13)):
        raise ValueError("months.csv: expected April 2025 through March 2026 with t=1..12")
    for row in months:
        year, month = map(int, row["month"].split("-"))
        if row["days"] != calendar.monthrange(year, month)[1]:
            raise ValueError(f"months.csv: incorrect days for {row['month']}")
    return months


def read_demand(folder):
    return read_csv(folder, "demand.csv", ["month", "market", "demand_dth"], ["month", "market"], ["demand_dth"])


def read_prices(folder):
    hub_exists = (Path(folder) / "hub_price.csv").exists()
    spot_exists = (Path(folder) / "citygate_price.csv").exists()
    if hub_exists != spot_exists:
        raise ValueError("Provide both hub_price.csv and citygate_price.csv, or only prices.csv")
    if hub_exists:
        hub = read_csv(folder, "hub_price.csv", ["month", "price"], ["month"], ["price"])
        spot = read_csv(folder, "citygate_price.csv", ["month", "market", "price"], ["month", "market"], ["price"])
    else:
        columns = ["month", "pa_hub", "pa_citygate", "ny_citygate", "nj_citygate"]
        rows = read_csv(folder, "prices.csv", columns, ["month"], columns[1:])
        hub = [{"month": row["month"], "price": row["pa_hub"]} for row in rows]
        spot = [{"month": row["month"], "market": market, "price": row[f"{market.lower()}_citygate"]} for row in rows for market in MARKETS]
    return hub, spot


def read_tariffs(folder, months):
    """One row per route from Pipeline_data_cleaned.csv: market, pipeline, usage
    charge, full capacity K, and the month-weighted reservation charge R."""
    source_columns = ["Route", "Market", "Pipeline", "Effective from", "Effective to", "Capacity (Dth/day)", "Usage ($/Dth)", "Reservation ($/Dth/day/month)"]
    rates = read_csv(folder, "Pipeline_data_cleaned.csv", source_columns, ["Route", "Effective from"], source_columns[5:])
    for row in rates:
        row["route"] = int(row["Route"])
        row["start"] = date(*map(int, row["Effective from"].replace("-", "/").split("/")))
        row["end"] = date(*map(int, row["Effective to"].replace("-", "/").split("/")))
    tariffs = []
    for route in sorted({row["route"] for row in rates}):
        records = [row for row in rates if row["route"] == route]
        first = records[0]
        for column in ["Market", "Pipeline", "Capacity (Dth/day)", "Usage ($/Dth)"]:
            if any(row[column] != first[column] for row in records):
                raise ValueError(f"Pipeline route {route}: changing {column} requires a model revision")
        if first["Capacity (Dth/day)"] <= 0:
            raise ValueError(f"Pipeline route {route}: full capacity must be positive")
        monthly_rates = []
        for month in months:
            year, number = map(int, month["month"].split("-"))
            daily_rates = []
            for day in range(1, int(month["days"]) + 1):
                current = date(year, number, day)
                matches = [row for row in records if row["start"] <= current <= row["end"]]
                if len(matches) != 1:
                    raise ValueError(f"Pipeline route {route}: missing or overlapping tariff at {current}")
                daily_rates.append(matches[0]["Reservation ($/Dth/day/month)"])
            if len(set(daily_rates)) != 1:
                raise ValueError(f"Pipeline route {route}: tariff changes within a month")
            monthly_rates.append(daily_rates[0])
        tariffs.append({
            "route": route, "market": first["Market"], "pipeline": first["Pipeline"],
            "usage_charge": first["Usage ($/Dth)"],
            "reservation_charge": sum(monthly_rates) / len(monthly_rates),
            "full_capacity_dth_day": first["Capacity (Dth/day)"],
        })
    return tariffs


def derive_routes(folder=DATA_DIR):
    """Build routes.csv rows from the tariffs and demand (assumption A9):
    kbar_l = average daily demand of the route's market / number of routes into it."""
    months = read_months(folder)
    demand = read_demand(folder)
    tariffs = read_tariffs(folder, months)
    total_days = sum(row["days"] for row in months)
    routes = []
    for row in tariffs:
        market = row["market"]
        annual = sum(d["demand_dth"] for d in demand if d["market"] == market)
        if annual <= 0:
            raise ValueError(f"Route {row['route']}: no demand for market {market}")
        n_routes = sum(1 for other in tariffs if other["market"] == market)
        kbar = annual / total_days / n_routes
        if kbar > row["full_capacity_dth_day"]:
            raise ValueError(f"Route {row['route']}: derived capacity {kbar:.0f} exceeds full capacity")
        routes.append({**row, "access_share": kbar / row["full_capacity_dth_day"], "fuel_rate": 0.0})
    return routes


def write_routes(folder=DATA_DIR):
    """Write data/processed/routes.csv from derive_routes()."""
    routes = derive_routes(folder)
    path = Path(folder) / "routes.csv"
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(ROUTE_COLUMNS)
        for row in routes:
            writer.writerow([row["route"], row["market"], row["pipeline"]]
                            + [f"{row[name]:.10g}" for name in ROUTE_COLUMNS[3:]])
    return path


def read_routes(folder):
    """Routes from routes.csv if present; otherwise derived in memory."""
    if (Path(folder) / "routes.csv").exists():
        routes = read_csv(folder, "routes.csv", ROUTE_COLUMNS, ["route"], ROUTE_COLUMNS[3:])
        for row in routes:
            try:
                row["route"] = int(row["route"])
            except ValueError:
                raise ValueError("routes.csv: route must be an integer") from None
        return routes
    warnings.warn("routes.csv not found; deriving route parameters from Pipeline_data_cleaned.csv and demand.csv. "
                  "Run `python src/load_data.py --write-routes` to commit them.", stacklevel=3)
    return derive_routes(folder)


def apply_capacity_limits(routes, capacity_limits):
    """Override accessible capacity (Dth/day) for the listed routes."""
    by_route = {row["route"]: row for row in routes}
    unknown = set(capacity_limits) - set(by_route)
    if unknown:
        raise ValueError(f"capacity_limits: unknown routes {sorted(unknown)}")
    for route, limit in capacity_limits.items():
        row = by_route[route]
        if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) \
                or not 0 <= limit <= row["full_capacity_dth_day"]:
            raise ValueError(f"capacity_limits[{route}]: {limit!r} must be between 0 and full capacity "
                             f"{row['full_capacity_dth_day']:,.0f} Dth/day")
        row["access_share"] = limit / row["full_capacity_dth_day"]
    return routes


def load_data(data_dir=DATA_DIR, capacity_limits=None):
    """Return the model input dict. capacity_limits optionally overrides kbar
    (Dth/day) for some or all routes; see the module docstring."""
    months = read_months(data_dir)
    time = {row["month"]: int(row["t"]) for row in months}
    demand = read_demand(data_dir)
    hub, spot = read_prices(data_dir)
    routes = read_routes(data_dir)
    if capacity_limits:
        routes = apply_capacity_limits(routes, capacity_limits)
    field_columns = ["field", "market", "capacity_dth", "init_inv_dth", "max_inj_dth_day", "max_wd_dth_day", "inj_fee", "wd_fee"]
    storage = read_csv(data_dir, "storage.csv", field_columns, ["field"], field_columns[2:])
    for filename, rows in [("demand.csv", demand), ("hub prices", hub), ("citygate prices", spot)]:
        if any(row["month"] not in time for row in rows):
            raise ValueError(f"{filename}: month outside model horizon")
    for row in routes:
        if not 0 <= row["access_share"] <= 1 or not 0 <= row["fuel_rate"] <= 1:
            raise ValueError(f"routes: route {row['route']} has access_share or fuel_rate outside [0, 1]")
        if row["full_capacity_dth_day"] < 0:
            raise ValueError(f"routes: route {row['route']} has negative full capacity")
    if len({row["route"] for row in routes}) != len(routes):
        raise ValueError("routes: duplicate integer route ID")
    if {row["market"] for row in demand + spot + routes} - set(MARKETS):
        raise ValueError("Unknown market in demand, prices, or routes")
    if {(row["field"], row["market"]) for row in storage} != {("H", "HUB"), ("M", "NY")}:
        raise ValueError("storage.csv: expected H at HUB and M at NY")
    data = {
        "T": list(range(1, 13)), "J": list(MARKETS),
        "L": sorted(row["route"] for row in routes), "F": sorted(row["field"] for row in storage),
        "L_j": {j: sorted(row["route"] for row in routes if row["market"] == j) for j in MARKETS},
        "F_j": {j: sorted(row["field"] for row in storage if row["market"] == j) for j in MARKETS},
        "F0": sorted(row["field"] for row in storage if row["market"] == "HUB"),
        "days": {int(row["t"]): int(row["days"]) for row in months},
        "P": {time[row["month"]]: row["price"] for row in hub},
        "D": {(row["market"], time[row["month"]]): row["demand_dth"] for row in demand},
        "pi": {(row["market"], time[row["month"]]): row["price"] for row in spot},
        "kbar": {row["route"]: row["access_share"] * row["full_capacity_dth_day"] for row in routes},
    }
    for name, column in {"c": "usage_charge", "R": "reservation_charge", "phi": "fuel_rate"}.items():
        data[name] = {row["route"]: row[column] for row in routes}
    for name, column in {"Ibar": "capacity_dth", "I0": "init_inv_dth", "r_in": "max_inj_dth_day", "r_out": "max_wd_dth_day", "c_in": "inj_fee", "c_out": "wd_fee"}.items():
        data[name] = {row["field"]: row[column] for row in storage}
    from validate import validate_inputs
    problems = validate_inputs(data)
    if problems:
        raise ValueError("Invalid model inputs:\n" + "\n".join(problems))
    return data


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    folder = root / DATA_DIR
    if "--write-routes" in sys.argv:
        print("Wrote", write_routes(folder))
    data = load_data(folder)
    print(f"Loaded {len(data['T'])} months, {len(data['J'])} markets, {len(data['L'])} routes and {len(data['F'])} storage fields.")
    for route in data["L"]:
        print(f"  route {route}: kbar = {data['kbar'][route]:,.1f} Dth/day, R = {data['R'][route]:.4f}")
