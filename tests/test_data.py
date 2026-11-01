import contextlib
import copy
import csv
import io
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import warnings

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from load_data import load_data
from prepare_inputs import prepare_inputs
from validate import PARAMETER_KEYS, validate_inputs, validate_solution


ROOT = Path(__file__).resolve().parents[1]


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name) / "processed"
        shutil.copytree(ROOT / "data" / "processed", self.folder)
        with contextlib.redirect_stdout(io.StringIO()):
            self.data = load_data(self.folder)

    def quiet(self, function, *args):
        with contextlib.redirect_stdout(io.StringIO()), warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return function(*args)

    def edit(self, filename, change):
        path = self.folder / filename
        with path.open(newline="") as file:
            reader = csv.DictReader(file)
            columns, rows = reader.fieldnames, list(reader)
        change(rows)
        with path.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)

    def local_solution(self):
        d = self.data
        solution = {"status": "OPTIMAL", "x": {t: 0.0 for t in d["T"]}, "k": {l: 0.0 for l in d["L"]}, "s": {(l, t): 0.0 for l in d["L"] for t in d["T"]}, "u": dict(d["D"])}
        solution.update({name: {(f, t): 0.0 for f in d["F"] for t in d["T"]} for name in ["qin", "qout"]})
        solution["I"] = {(f, t): d["I0"][f] for f in d["F"] for t in d["T"]}
        spot = sum(d["pi"][key] * value for key, value in d["D"].items())
        solution["costs"] = {"purchase": 0.0, "pipeline_usage": 0.0, "storage_fees": 0.0, "spot": spot, "reservation": 0.0}
        solution["objective"] = spot
        return solution

    def test_real_inputs_and_mapping(self):
        d = self.data
        self.assertEqual(set(d), PARAMETER_KEYS)
        self.assertEqual(self.quiet(validate_inputs, d), [])
        self.assertEqual(d["L_j"], {"NY": [1, 2], "NJ": [3], "PA": [4]})
        self.assertEqual(d["F_j"], {"NY": ["M"], "NJ": [], "PA": []})
        self.assertEqual(sum(d["days"].values()), 365)
        self.assertAlmostEqual(d["R"][1], (7 * 7.0333 + 5 * 6.9613) / 12)
        self.assertAlmostEqual(d["kbar"][1], 19178)
        self.assertEqual(d["P"][1], 3.16)
        self.assertEqual(d["pi"]["NY", 1], 4.879460)
        self.assertEqual(d["r_in"]["H"], 12280)
        self.assertEqual(d["c_in"]["M"], 0.0381)
        for j, bcf in [("NY", 13.5), ("NJ", 7.5), ("PA", 9.0)]:
            self.assertAlmostEqual(sum(v for (market, t), v in d["D"].items() if market == j), bcf * 1037000, delta=6)

    def test_loader_rejects_duplicate_missing_unknown_and_nonfinite(self):
        original = (self.folder / "demand.csv").read_bytes()
        changes = [lambda rows: rows.append(dict(rows[0])), lambda rows: rows.pop(), lambda rows: rows[0].update(month="2026-04"), lambda rows: rows[0].update(market="OH"), lambda rows: rows[0].update(demand_dth="nan"), lambda rows: rows[0].update(demand_dth=""), lambda rows: rows[0].update(demand_dth="-1")]
        for change in changes:
            with self.subTest(change=change):
                (self.folder / "demand.csv").write_bytes(original)
                self.edit("demand.csv", change)
                with self.assertRaises(ValueError):
                    self.quiet(load_data, self.folder)

    def test_loader_rejects_invalid_share_fuel_and_calendar(self):
        for column in ["access_share", "fuel_rate"]:
            original = (self.folder / "routes.csv").read_bytes()
            for value in [-0.1, 1.1]:
                self.edit("routes.csv", lambda rows: rows[0].update({column: str(value)}))
                with self.assertRaises(ValueError):
                    load_data(self.folder)
                (self.folder / "routes.csv").write_bytes(original)
        self.edit("months.csv", lambda rows: rows[0].update(days="31"))
        with self.assertRaises(ValueError):
            load_data(self.folder)

    def test_valid_solution(self):
        self.assertEqual(self.quiet(validate_solution, self.local_solution(), self.data), [])

    def test_solution_rejects_each_constraint_and_bad_costs(self):
        changes = [("x", 1, 1), ("u", ("NY", 1), 0), ("s", (1, 1), 1), ("qin", ("H", 1), 1e7), ("qout", ("M", 1), 1e7), ("I", ("H", 12), 0), ("k", 1, 1e6), ("x", 1, -1), ("u", ("NJ", 1), float("nan")), ("costs", "spot", 0)]
        for name, key, value in changes:
            with self.subTest(name=name, key=key):
                solution = self.local_solution()
                solution[name][key] = value
                self.assertTrue(self.quiet(validate_solution, solution, self.data))
        solution = self.local_solution()
        solution["objective"] += 1
        self.assertTrue(self.quiet(validate_solution, solution, self.data))
        solution["status"] = "INFEASIBLE"
        self.assertTrue(self.quiet(validate_solution, solution, self.data))
        solution = self.local_solution()
        del solution["s"][1, 1]
        self.assertTrue(self.quiet(validate_solution, solution, self.data))

    def test_fuel_retention_is_accounted_for(self):
        d = copy.deepcopy(self.data)
        d["phi"][1] = 0.02
        solution = self.local_solution()
        solution["x"][1] = 100
        solution["s"][1, 1] = 100
        solution["k"][1] = 100 / d["days"][1]
        solution["u"]["NY", 1] -= 98
        solution["costs"]["purchase"] = 100 * d["P"][1]
        solution["costs"]["pipeline_usage"] = 100 * d["c"][1]
        solution["costs"]["reservation"] = 12 * solution["k"][1] * d["R"][1]
        solution["costs"]["spot"] -= 98 * d["pi"]["NY", 1]
        solution["objective"] = sum(solution["costs"].values())
        self.assertEqual(self.quiet(validate_solution, solution, d), [])

    def test_preparation_is_reproducible(self):
        names = ["hub_price.csv", "citygate_price.csv", "routes.csv"]
        before = {name: (self.folder / name).read_bytes() for name in names}
        self.quiet(prepare_inputs, self.folder)
        self.assertEqual(before, {name: (self.folder / name).read_bytes() for name in names})
        self.edit("Pipeline_data_cleaned.csv", lambda rows: rows[0].update({"Effective to": "2025/10/30"}))
        with self.assertRaises(ValueError):
            prepare_inputs(self.folder)

    def test_gurobi_integration(self):
        try:
            from model import solve
        except ImportError:
            self.skipTest("Install gurobipy to run solver integration")
        solution = solve(self.data)
        self.assertEqual(solution["status"], "OPTIMAL")
        self.assertEqual(self.quiet(validate_solution, solution, self.data), [])
        self.assertLessEqual(solution["objective"], self.local_solution()["objective"])
        solution["model"].dispose()


if __name__ == "__main__":
    unittest.main()
