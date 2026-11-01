import calendar
import csv
import math
import warnings
from datetime import date
from pathlib import Path


DATA_DIR = "data/processed"


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
        spot = [{"month": row["month"], "market": market, "price": row[f"{market.lower()}_citygate"]} for row in rows for market in ["NY", "NJ", "PA"]]
    return hub, spot


def read_routes(folder, months, capacity_limits):
    columns = ["route", "market", "pipeline", "usage_charge", "reservation_charge", "full_capacity_dth_day", "access_share", "fuel_rate"]
    if (Path(folder) / "routes.csv").exists():
        return read_csv(folder, "routes.csv", columns, ["route"], columns[3:])
    source_columns = ["Route", "Market", "Pipeline", "Effective from", "Effective to", "Capacity (Dth/day)", "Usage ($/Dth)", "Reservation ($/Dth/day/month)"]
    rates = read_csv(folder, "Pipeline_data_cleaned.csv", source_columns, ["Route", "Effective from"], source_columns[5:])
    for row in rates:
        row["route"] = int(row["Route"])
        row["start"] = date(*map(int, row["Effective from"].replace("-", "/").split("/")))
        row["end"] = date(*map(int, row["Effective to"].replace("-", "/").split("/")))
    route_ids = sorted({row["route"] for row in rates})
    if set(route_ids) != set(capacity_limits):
        raise ValueError("Pipeline_data_cleaned.csv: capacity_limits must cover exactly the uploaded routes")
    warnings.warn(f"Pipeline upload has no access shares or fuel rates. Using provisional capacity_limits={capacity_limits} Dth/day from Team 23 Backup B and zero fuel retention. Pass capacity_limits to override; routes.csv supplies explicit shares and fuel rates.", stacklevel=2)
    routes = []
    for route in route_ids:
        records = [row for row in rates if row["route"] == route]
        first = records[0]
        for column in ["Market", "Pipeline", "Capacity (Dth/day)", "Usage ($/Dth)"]:
            if any(row[column] != first[column] for row in records):
                raise ValueError(f"Pipeline route {route}: changing {column} requires a model revision")
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
        capacity = first["Capacity (Dth/day)"]
        limit = capacity_limits[route]
        if not math.isfinite(limit) or capacity <= 0 or not 0 <= limit <= capacity:
            raise ValueError(f"Pipeline route {route}: invalid accessible capacity {limit}")
        routes.append(dict(zip(columns, [str(route), first["Market"], first["Pipeline"], first["Usage ($/Dth)"], sum(monthly_rates) / len(monthly_rates), capacity, limit / capacity, 0.0])))
    return routes

def load_data(data_dir=DATA_DIR, capacity_limits=None):
    if capacity_limits is None:
        capacity_limits = {1: 19178, 2: 19178, 3: 21308, 4: 25570}
    months = read_csv(data_dir, "months.csv", ["month", "t", "days"], ["month"], ["t", "days"])
    expected = [f"2025-{m:02d}" for m in range(4, 13)] + [f"2026-{m:02d}" for m in range(1, 4)]
    months.sort(key=lambda row: row["t"])
    if [row["month"] for row in months] != expected or [row["t"] for row in months] != list(range(1, 13)):
        raise ValueError("months.csv: expected April 2025 through March 2026 with t=1..12")
    for row in months:
        year, month = map(int, row["month"].split("-"))
        if row["days"] != calendar.monthrange(year, month)[1]:
            raise ValueError(f"months.csv: incorrect days for {row['month']}")
    time = {row["month"]: int(row["t"]) for row in months}
    demand = read_csv(data_dir, "demand.csv", ["month", "market", "demand_dth"], ["month", "market"], ["demand_dth"])
    hub, spot = read_prices(data_dir)
    routes = read_routes(data_dir, months, capacity_limits)
    field_columns = ["field", "market", "capacity_dth", "init_inv_dth", "max_inj_dth_day", "max_wd_dth_day", "inj_fee", "wd_fee"]
    storage = read_csv(data_dir, "storage.csv", field_columns, ["field"], field_columns[2:])
    for filename, rows in [("demand.csv", demand), ("hub_price.csv", hub), ("citygate_price.csv", spot)]:
        if any(row["month"] not in time for row in rows):
            raise ValueError(f"{filename}: month outside model horizon")
    for row in routes:
        try:
            row["route"] = int(row["route"])
        except ValueError:
            raise ValueError("routes.csv: route must be an integer") from None
        if not 0 <= row["access_share"] <= 1 or not 0 <= row["fuel_rate"] <= 1:
            raise ValueError(f"routes.csv: route {row['route']} has access_share or fuel_rate outside [0, 1]")
        if row["full_capacity_dth_day"] < 0:
            raise ValueError(f"routes.csv: route {row['route']} has negative full capacity")
    if len({row["route"] for row in routes}) != len(routes):
        raise ValueError("routes.csv: duplicate integer route ID")
    if {row["market"] for row in demand + spot + routes} - {"NY", "NJ", "PA"}:
        raise ValueError("Unknown market in demand, prices, or routes")
    if {(row["field"], row["market"]) for row in storage} != {("H", "HUB"), ("M", "NY")}:
        raise ValueError("storage.csv: expected H at HUB and M at NY")
    data = {
        "T": list(range(1, 13)), "J": ["NY", "NJ", "PA"],
        "L": sorted(row["route"] for row in routes), "F": sorted(row["field"] for row in storage),
        "L_j": {j: sorted(row["route"] for row in routes if row["market"] == j) for j in ["NY", "NJ", "PA"]},
        "F_j": {j: sorted(row["field"] for row in storage if row["market"] == j) for j in ["NY", "NJ", "PA"]},
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
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    data = load_data()
    print(f"Loaded {len(data['T'])} months, {len(data['J'])} markets, {len(data['L'])} routes and {len(data['F'])} storage fields.")
