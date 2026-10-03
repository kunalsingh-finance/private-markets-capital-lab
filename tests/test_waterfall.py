"""Analytical tier cases and accounting invariants for the fictional waterfall."""

from datetime import date, datetime, timedelta
import json
import unittest

from pmcapital.waterfall import european_waterfall, run_waterfall_demo


class EuropeanWaterfallTests(unittest.TestCase):
    def setUp(self):
        self.start = date(2025, 1, 1)
        self.end = date(2026, 1, 1)
        self.calls = [(self.start, 100000)]  # $1,000, one exact 365-day year.

    def calculate(self, proceeds, **kwargs):
        return european_waterfall(self.calls, proceeds, self.end, **kwargs)

    def assert_conserved(self, result):
        self.assertEqual(result["lp_total_cents"] + result["gp_total_cents"], result["total_proceeds_cents"])
        self.assertEqual(sum(tier["total_cents"] for tier in result["tiers"]), result["total_proceeds_cents"])
        self.assertTrue(all(result["controls"].values()))

    def test_zero_proceeds_preserve_capital_and_preferred_shortfalls(self):
        result = self.calculate(0)
        self.assertEqual(result["capital_shortfall_cents"], 100000)
        self.assertEqual(result["preferred_due_cents"], 8000)
        self.assertEqual(result["preferred_unpaid_cents"], 8000)
        self.assertEqual(result["gp_total_cents"], 0)
        self.assert_conserved(result)

    def test_loss_returns_only_available_capital(self):
        result = self.calculate(90000)
        self.assertEqual(result["capital_return_cents"], 90000)
        self.assertEqual(result["preferred_paid_cents"], 0)
        self.assertEqual(result["gp_total_cents"], 0)
        self.assert_conserved(result)

    def test_exact_capital_has_no_preferred_or_carry_payment(self):
        result = self.calculate(100000)
        self.assertEqual(result["capital_return_cents"], 100000)
        self.assertEqual(result["preferred_paid_cents"], 0)
        self.assertEqual(result["gp_total_cents"], 0)
        self.assert_conserved(result)

    def test_partial_preferred_pays_only_lp(self):
        result = self.calculate(104000)
        self.assertEqual(result["preferred_paid_cents"], 4000)
        self.assertEqual(result["preferred_unpaid_cents"], 4000)
        self.assertEqual(result["gp_total_cents"], 0)
        self.assert_conserved(result)

    def test_exact_preferred_starts_no_catchup_without_cash(self):
        result = self.calculate(108000)
        self.assertEqual(result["preferred_paid_cents"], 8000)
        self.assertEqual(result["catchup_target_total_cents"], 2000)
        self.assertEqual(result["catchup_gp_cents"], 0)
        self.assertFalse(result["catchup_completed"])
        self.assert_conserved(result)

    def test_partial_full_gp_catchup_consumes_remaining_cash(self):
        result = self.calculate(109000)
        self.assertEqual(result["catchup_gp_cents"], 1000)
        self.assertEqual(result["catchup_lp_cents"], 0)
        self.assertEqual(result["residual_gp_cents"], 0)
        self.assertEqual(result["lp_total_cents"], 108000)
        self.assert_conserved(result)

    def test_full_catchup_reaches_twenty_percent_of_profit(self):
        result = self.calculate(110000)
        self.assertEqual(result["catchup_gp_cents"], 2000)
        self.assertEqual(result["gp_total_cents"], 2000)
        self.assertEqual(result["lp_total_cents"], 108000)
        self.assertTrue(result["catchup_completed"])
        self.assert_conserved(result)

    def test_residual_profit_split_after_catchup(self):
        result = self.calculate(120000)
        self.assertEqual(result["capital_return_cents"], 100000)
        self.assertEqual(result["preferred_paid_cents"], 8000)
        self.assertEqual(result["catchup_gp_cents"], 2000)
        self.assertEqual(result["residual_lp_cents"], 8000)
        self.assertEqual(result["residual_gp_cents"], 2000)
        self.assertEqual(result["gp_total_cents"], 4000)
        self.assert_conserved(result)

    def test_partial_split_catchup_allocates_lp_share_too(self):
        result = self.calculate(110000, catchup_bps=5000)
        self.assertEqual(result["catchup_target_total_cents"], 5333)
        self.assertEqual(result["catchup_total_cents"], 2000)
        self.assertEqual(result["catchup_gp_cents"], 1000)
        self.assertEqual(result["catchup_lp_cents"], 1000)
        self.assertEqual(result["residual_gp_cents"], 0)
        self.assert_conserved(result)

    def test_full_split_catchup_and_residual_are_within_one_cent_of_target(self):
        result = self.calculate(120000, catchup_bps=5000)
        self.assertEqual(result["catchup_total_cents"], 5333)
        self.assertEqual(result["catchup_gp_cents"], 2667)
        self.assertTrue(result["catchup_completed"])
        self.assertLessEqual(abs(result["gp_total_cents"] - 4000), 1)
        self.assert_conserved(result)

    def test_prior_carry_changes_trueup_only_not_lifetime_allocation(self):
        baseline = self.calculate(120000)
        result = self.calculate(120000, prior_gp_carry_cents=6000)
        self.assertEqual(result["lp_total_cents"], baseline["lp_total_cents"])
        self.assertEqual(result["gp_total_cents"], baseline["gp_total_cents"])
        self.assertEqual(result["clawback_due_cents"], 2000)
        self.assertEqual(result["gp_additional_due_cents"], 0)
        self.assert_conserved(result)

    def test_gp_additional_due_is_entitlement_less_prior_paid(self):
        result = self.calculate(120000, prior_gp_carry_cents=1500)
        self.assertEqual(result["clawback_due_cents"], 0)
        self.assertEqual(result["gp_additional_due_cents"], 2500)
        self.assert_conserved(result)

    def test_carry_below_preferred_is_fully_clawed_back(self):
        result = self.calculate(104000, prior_gp_carry_cents=3000)
        self.assertEqual(result["gp_total_cents"], 0)
        self.assertEqual(result["clawback_due_cents"], 3000)
        self.assert_conserved(result)

    def test_preferred_rounds_half_up_at_exact_half_cent(self):
        result = european_waterfall([(self.start, 25)], 100, self.end, hurdle_bps=200)
        self.assertEqual(result["preferred_due_cents"], 1)
        self.assert_conserved(result)

    def test_preferred_rounds_once_and_contribution_splitting_is_invariant(self):
        whole = european_waterfall([(self.start, 50)], 100, self.end, hurdle_bps=200)
        split = european_waterfall([(self.start, 25), (self.start, 25)], 100, self.end, hurdle_bps=200)
        self.assertEqual(whole["preferred_due_cents"], 1)
        for key in ("preferred_due_cents", "lp_total_cents", "gp_total_cents"):
            self.assertEqual(split[key], whole[key])
        self.assert_conserved(split)

    def test_actual_365_includes_leap_day(self):
        result = european_waterfall([(date(2024, 1, 1), 36500)], 50000, date(2025, 1, 1), hurdle_bps=1000)
        self.assertEqual(result["preferred_due_cents"], 3660)
        self.assert_conserved(result)

    def test_each_dated_contribution_has_its_own_accrual_period(self):
        result = european_waterfall(
            [(date(2021, 1, 1), 100000), (date(2022, 1, 1), 100000)],
            250000, date(2023, 1, 1),
        )
        self.assertEqual(result["preferred_due_cents"], 24000)
        self.assert_conserved(result)

    def test_same_day_contribution_has_zero_accrual(self):
        result = european_waterfall([(self.end, 100000)], 120000, self.end)
        self.assertEqual(result["preferred_due_cents"], 0)
        self.assertEqual(result["gp_total_cents"], 4000)
        self.assert_conserved(result)

    def test_zero_carry_is_all_lp_and_zero_hurdle_skips_preferred(self):
        result = self.calculate(120000, carry_bps=0, catchup_bps=0)
        self.assertEqual(result["lp_total_cents"], 120000)
        self.assertEqual(result["gp_total_cents"], 0)
        no_hurdle = self.calculate(120000, hurdle_bps=0)
        self.assertEqual(no_hurdle["preferred_due_cents"], 0)
        self.assertEqual(no_hurdle["catchup_total_cents"], 0)
        self.assertEqual(no_hurdle["gp_total_cents"], 4000)
        self.assert_conserved(result)
        self.assert_conserved(no_hurdle)

    def test_empty_zero_case_is_defined_but_cash_without_capital_is_rejected(self):
        result = european_waterfall([], 0, self.end)
        self.assertEqual(result["lp_total_cents"], 0)
        self.assertEqual(result["gp_total_cents"], 0)
        self.assert_conserved(result)
        with self.assertRaises(ValueError):
            european_waterfall([], 1, self.end)

    def test_penny_boundaries_and_rates_conserve_cash(self):
        for carry, catchup in ((0, 0), (2000, 5000), (2000, 10000), (9999, 10000)):
            for proceeds in range(0, 151):
                with self.subTest(carry=carry, catchup=catchup, proceeds=proceeds):
                    result = european_waterfall([(self.start, 100)], proceeds, self.end, carry_bps=carry, catchup_bps=catchup)
                    self.assert_conserved(result)

    def test_invalid_money_and_basis_points_are_rejected(self):
        cases = [
            {"proceeds_cents": -1}, {"proceeds_cents": 100.5}, {"proceeds_cents": True},
            {"prior_gp_carry_cents": -1}, {"prior_gp_carry_cents": 120001},
            {"hurdle_bps": -1}, {"hurdle_bps": 10001}, {"hurdle_bps": 800.0},
            {"carry_bps": 10000}, {"carry_bps": True},
            {"catchup_bps": 2000}, {"catchup_bps": 0}, {"catchup_bps": 10001},
        ]
        for overrides in cases:
            arguments = {"contributions": self.calls, "proceeds_cents": 120000, "distribution_date": self.end}
            arguments.update(overrides)
            with self.subTest(overrides=overrides):
                with self.assertRaises(ValueError):
                    european_waterfall(**arguments)

    def test_invalid_contribution_dates_amounts_and_terminal_date_are_rejected(self):
        for calls in (
            [(self.end + timedelta(days=1), 100)], [("2025-01-01", 100)],
            [(datetime(2025, 1, 1), 100)], [(self.start, 0)], [(self.start, -1)],
            [(self.start, 1.5)], [(self.start, True)], [(self.start,)], "not a tape",
        ):
            with self.subTest(calls=calls):
                with self.assertRaises(ValueError):
                    european_waterfall(calls, 120000, self.end)
        with self.assertRaises(ValueError):
            european_waterfall(self.calls, 120000, "2026-01-01")

    def test_demo_is_json_safe_and_clawback_scenario_is_visible(self):
        demo = run_waterfall_demo()
        json.dumps(demo, allow_nan=False)
        self.assertEqual(len(demo["scenarios"]), 4)
        by_key = {scenario["scenario_id"]: scenario["result"] for scenario in demo["scenarios"]}
        self.assertEqual(by_key["BASE"]["capital_cents"], 500000000)
        self.assertEqual(by_key["BASE"]["gp_total_cents"], 60000000)
        self.assertEqual(by_key["LOW_PROFIT"]["gp_total_cents"], 0)
        self.assertEqual(by_key["LOSS"]["capital_shortfall_cents"], 100000000)
        self.assertEqual(by_key["CLAWBACK"]["clawback_due_cents"], 30000000)
        for result in by_key.values():
            self.assert_conserved(result)


if __name__ == "__main__":
    unittest.main()
