from datetime import date, timedelta
import unittest
from pmcapital.return_diagnostics import root_diagnostics, benchmark_adjusted_return


class ReturnDiagnosticsTests(unittest.TestCase):
    def test_two_known_roots_are_preserved_for_review(self):
        start = date(2021, 1, 1)
        result = root_diagnostics([(start, -10000), (start + timedelta(days=365), 23000), (start + timedelta(days=730), -13200)])
        self.assertEqual(result["status"], "MIXED_FLOW_CANDIDATES_REVIEW")
        self.assertFalse(result["certified_by_sign_pattern"])
        self.assertEqual(len(result["candidate_rates"]), 2)
        self.assertAlmostEqual(result["candidate_rates"][0], 0.1, places=9)
        self.assertAlmostEqual(result["candidate_rates"][1], 0.2, places=9)

    def test_conventional_result_is_analytically_unique(self):
        result = root_diagnostics([(date(2021, 1, 1), -10000), (date(2022, 1, 1), 12000)])
        self.assertTrue(result["certified_by_sign_pattern"])
        self.assertAlmostEqual(result["candidate_rates"][0], 0.2, places=10)

    def test_benchmark_matched_cashflows_have_zero_adjusted_return(self):
        start, end = date(2021, 1, 1), date(2022, 1, 1)
        result = benchmark_adjusted_return([{"date": start, "kind": "CALL", "amount_cents": 10000}], 12000, end, [(start, 100.0), (end, 120.0)])
        self.assertEqual(result["value"], 0.0)
        self.assertEqual(result["status"], "OK")

    def test_missing_benchmark_is_unavailable(self):
        result = benchmark_adjusted_return([{"date": date(2021, 1, 1), "kind": "CALL", "amount_cents": 10000}], 12000, date(2022, 1, 1), [(date(2022, 1, 1), 120)])
        self.assertEqual(result["status"], "BENCHMARK_UNAVAILABLE")

    def test_candidate_scan_does_not_certify_tangent_roots(self):
        start = date(2021, 1, 1)
        result = root_diagnostics([(start, -10000), (start + timedelta(days=365), 22000), (start + timedelta(days=730), -12100)])
        self.assertFalse(result["certified_by_sign_pattern"])
        self.assertIn("Finite scan", result["limitation"])

    def test_no_contributions_is_not_mislabeled_as_missing_benchmark(self):
        result = benchmark_adjusted_return([], 12000, date(2022, 1, 1), [(date(2022, 1, 1), 120)])
        self.assertEqual(result["status"], "UNDEFINED_NO_CONTRIBUTIONS")


if __name__ == "__main__":
    unittest.main()
