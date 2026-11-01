import calendar
import csv
from datetime import date
from pathlib import Path

from load_data import DATA_DIR, read_csv


def write_csv(folder, filename, columns, rows):
    with (Path(folder) / filename).open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def prepare_inputs(data_dir=DATA_DIR):
    folder = Path(data_dir)
    prices = read_csv(folder, "prices.csv", ["month", "pa_hub", "pa_citygate", "ny_citygate", "nj_citygate"], ["month"], ["pa_hub", "pa_citygate", "ny_citygate", "nj_citygate"])
    assumptions = read_csv(folder, "route_assumptions.csv", ["route", "accessible_capacity_dth_day", "fuel_rate"], ["route"], ["accessible_capacity_dth_day", "fuel_rate"])
    assumptions = {int(row["route"]): row for row in assumptions}
    columns = ["Route", "Market", "Pipeline", "Effective from", "Effective to", "Capacity (Dth/day)", "Usage ($/Dth)", "Reservation ($/Dth/day/month)"]
    rates = read_csv(folder, "Pipeline_data_cleaned.csv", columns, ["Route", "Effective from"], columns[5:])
    months = read_csv(folder, "months.csv", ["month", "t", "days"], ["month"], ["t", "days"])
    for row in rates:
        row["start"] = date(*map(int, row["Effective from"].split("/")))
        row["end"] = date(*map(int, row["Effective to"].split("/")))
    routes = []
    route_ids = sorted({int(row["Route"]) for row in rates})
    if set(route_ids) != set(assumptions):
        raise ValueError("route_assumptions.csv must cover exactly the uploaded routes")
    for route in route_ids:
        records = [row for row in rates if int(row["Route"]) == route]
        first = records[0]
        for column in ["Market", "Pipeline", "Capacity (Dth/day)", "Usage ($/Dth)"]:
            if any(row[column] != first[column] for row in records):
                raise ValueError(f"Route {route}: {column} changes; requires an explicit model revision")
        monthly_rates = []
        for month in months:
            year, number = map(int, month["month"].split("-"))
            daily_rates = []
            for day in range(1, calendar.monthrange(year, number)[1] + 1):
                current = date(year, number, day)
                matches = [row for row in records if row["start"] <= current <= row["end"]]
                if len(matches) != 1:
                    raise ValueError(f"Route {route}: missing or overlapping tariff at {current}")
                daily_rates.append(matches[0]["Reservation ($/Dth/day/month)"])
            if len(set(daily_rates)) != 1:
                raise ValueError(f"Route {route}: tariff changes within a month")
            monthly_rates.append(daily_rates[0])
        capacity = first["Capacity (Dth/day)"]
        accessible = assumptions[route]["accessible_capacity_dth_day"]
        fuel = assumptions[route]["fuel_rate"]
        if capacity <= 0 or not 0 <= accessible <= capacity or not 0 <= fuel <= 1:
            raise ValueError(f"Route {route}: invalid capacity assumption or fuel rate")
        routes.append(dict(zip(["route", "market", "pipeline", "usage_charge", "reservation_charge", "full_capacity_dth_day", "access_share", "fuel_rate"], [route, first["Market"], first["Pipeline"], first["Usage ($/Dth)"], sum(monthly_rates) / len(monthly_rates), capacity, accessible / capacity, fuel])))
    write_csv(folder, "hub_price.csv", ["month", "price"], [{"month": row["month"], "price": row["pa_hub"]} for row in prices])
    write_csv(folder, "citygate_price.csv", ["month", "market", "price"], [{"month": row["month"], "market": market, "price": row[f"{market.lower()}_citygate"]} for row in prices for market in ["NY", "NJ", "PA"]])
    write_csv(folder, "routes.csv", ["route", "market", "pipeline", "usage_charge", "reservation_charge", "full_capacity_dth_day", "access_share", "fuel_rate"], routes)
    print("Prepared hub_price.csv, citygate_price.csv and routes.csv from uploaded processed tables.")


if __name__ == "__main__":
    prepare_inputs()
