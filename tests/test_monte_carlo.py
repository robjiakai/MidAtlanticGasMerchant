from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import monte_carlo as runner
from src import monte_carlo as mc
from src.load_data import load_data


class MonteCarloTests(unittest.TestCase):
    def test_baseline_prices_reproduce_all_policies(self):
        data = load_data()
        year = np.array([[data["pi"][j, t] for j in data["J"]] + [data["P"][t]] for t in data["T"]])
        baseline, costs, decisions, keys = runner.simulate(data, np.repeat(year[None], 2, axis=0))
        for values in costs.values():
            np.testing.assert_allclose(values, baseline["objective"], rtol=0, atol=1e-3)
        np.testing.assert_allclose(decisions["B"]["k"], [[baseline["k"][key] for key in keys["k"]]] * 2, rtol=0, atol=1e-6)
        self.assertEqual(sum(len(values) for values in keys.values()), 172)

    def test_sampling_is_positive_reproducible_and_uses_supplied_moments(self):
        means, variances = mc.load_price_moments()
        first = mc.sample_prices(means, variances, mc.equicorrelation(0.8), n=50, seed=42, moment_match=False)
        second = mc.sample_prices(means, variances, mc.equicorrelation(0.8), n=50, seed=42, moment_match=False)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(first.shape, (50, 12, 4))
        self.assertTrue(np.isfinite(first).all() and (first > 0).all())
        mu, sigma = mc.lognormal_params(means, variances)
        np.testing.assert_allclose(np.exp(mu + sigma ** 2 / 2), means)
        np.testing.assert_allclose((np.exp(sigma ** 2) - 1) * np.exp(2 * mu + sigma ** 2), variances)

    def test_independent_full_rebuild_matches_updated_objective(self):
        data = load_data()
        means, variances = mc.load_price_moments()
        prices = mc.sample_prices(means, variances, mc.equicorrelation(0.8), n=2, seed=7, moment_match=False)
        baseline, costs, decisions, keys = runner.simulate(data, prices)
        solution = runner.solve(runner.price_data(data, prices[1]))
        self.assertAlmostEqual(costs["C"][1], solution["objective"], delta=1e-3)
        solution["model"].dispose()
        self.assertTrue(np.all(costs["A"] >= costs["B"] - 1e-3))
        self.assertTrue(np.all(costs["B"] >= costs["C"] - 1e-3))
        rows = runner.decision_summary(baseline, decisions, keys, data)
        self.assertEqual(len(rows), 344)
        self.assertEqual(set(rows["variable"]), set(runner.NAMES))

    def test_checker_rejects_changed_demand_without_delivery(self):
        data = load_data()
        solution = runner.solve(data)
        data["D"] = dict(data["D"])
        data["D"]["NY", 1] += 1000
        with self.assertRaises(ValueError):
            runner.check_solution(solution, data)
        solution["model"].dispose()


if __name__ == "__main__":
    unittest.main()
