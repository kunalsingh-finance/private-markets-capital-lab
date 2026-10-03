"""Financial checks against analytical results, independent of report rendering."""

from datetime import date, timedelta
import unittest

from pmcapital.analytics import ks_pme, metrics, money, xirr


class MoneyTests(unittest.TestCase):
    def test_exact_decimal_to_integer_cents(self):
        self.assertEqual(money("0.00"), 0)
        self.assertEqual(money("10.2"), 1020)
        self.assertEqual(money("1000000.99"), 100000099)

    def test_fractional_cents_are_rejected_instead_of_rounded(self):
        for raw in ("0.009", "1.001", "9.999"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    money(raw)

    def test_negative_and_nonfinite_money_are_rejected(self):
        for raw in ("-0.01", "NaN", "Infinity", "-Infinity", "", "missing"):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    money(raw)


class XirrTests(unittest.TestCase):
    def assert_ok_rate(self, flows, expected):
        result = xirr(flows)
        self.assertEqual(result["status"], "OK")
        self.assertAlmostEqual(result["value"], expected, places=8)
        self.assertLessEqual(abs(result["residual_cents"]), 0.5)
        return result

    def test_one_year_analytical_return(self):
        self.assert_ok_rate(
            [(date(2025, 1, 1), -10000), (date(2026, 1, 1), 11000)], 0.1
        )

    def test_loss_has_negative_irr(self):
        self.assert_ok_rate(
            [(date(2025, 1, 1), -10000), (date(2026, 1, 1), 9000)], -0.1
        )

    def test_actual_365_does_not_treat_leap_year_as_365_days(self):
        expected = 1.1 ** (365.0 / 366.0) - 1.0
        self.assert_ok_rate(
            [(date(2024, 1, 1), -10000), (date(2025, 1, 1), 11000)], expected
        )

    def test_same_date_flows_are_aggregated_before_sign_change_check(self):
        self.assert_ok_rate(
            [
                (date(2025, 1, 1), -12000),
                (date(2025, 1, 1), 2000),
                (date(2026, 1, 1), -1000),
                (date(2026, 1, 1), 12000),
            ],
            0.1,
        )

    def test_zero_and_input_order_do_not_change_rate(self):
        self.assert_ok_rate(
            [
                (date(2026, 1, 1), 11000),
                (date(2025, 6, 1), 0),
                (date(2025, 1, 1), -10000),
            ],
            0.1,
        )

    def test_currency_scaling_does_not_change_rate(self):
        self.assert_ok_rate(
            [(date(2025, 1, 1), -100000000), (date(2026, 1, 1), 110000000)],
            0.1,
        )

    def test_multiple_sign_changes_are_flagged(self):
        result = xirr(
            [
                (date(2024, 1, 1), -10000),
                (date(2024, 6, 1), 23000),
                (date(2025, 1, 1), -13200),
            ]
        )
        self.assertEqual(result["status"], "NON_CONVENTIONAL")
        self.assertIsNone(result["value"])

    def test_positive_then_negative_is_not_investor_conventional(self):
        result = xirr([(date(2025, 1, 1), 10000), (date(2026, 1, 1), -11000)])
        self.assertEqual(result["status"], "NON_CONVENTIONAL")
        self.assertIsNone(result["value"])

    def test_no_identifiable_return_is_undefined(self):
        examples = [
            [],
            [(date(2025, 1, 1), -10000)],
            [(date(2025, 1, 1), 10000)],
            [(date(2025, 1, 1), -10000), (date(2025, 1, 1), 10000)],
        ]
        for flows in examples:
            with self.subTest(flows=flows):
                result = xirr(flows)
                self.assertEqual(result["status"], "UNDEFINED")
                self.assertIsNone(result["value"])

    def test_numerically_unbounded_annual_rate_is_not_reported(self):
        result = xirr([(date(2025, 1, 1), -1), (date(2025, 1, 2), 10**15)])
        self.assertEqual(result["status"], "OUT_OF_RANGE")
        self.assertIsNone(result["value"])

    def test_text_date_is_rejected(self):
        with self.assertRaises(ValueError):
            xirr([("2025-01-01", -10000), (date(2026, 1, 1), 11000)])


class MultipleTests(unittest.TestCase):
    def test_distributions_and_nav_are_distinct_and_add_to_tvpi(self):
        result = metrics(paid_in=10000, distributed=6000, nav=8000)
        self.assertAlmostEqual(result["dpi"], 0.6)
        self.assertAlmostEqual(result["rvpi"], 0.8)
        self.assertAlmostEqual(result["tvpi"], 1.4)
        self.assertAlmostEqual(result["dpi"] + result["rvpi"], result["tvpi"])

    def test_zero_paid_in_does_not_create_infinite_multiples(self):
        self.assertEqual(
            metrics(paid_in=0, distributed=100, nav=200),
            {"dpi": None, "rvpi": None, "tvpi": None},
        )

    def test_aggregate_multiple_is_capital_weighted_not_fund_average(self):
        first = metrics(paid_in=10000, distributed=10000, nav=10000)
        second = metrics(paid_in=90000, distributed=0, nav=90000)
        aggregate = metrics(paid_in=100000, distributed=10000, nav=100000)
        self.assertAlmostEqual(aggregate["tvpi"], 1.1)
        self.assertNotAlmostEqual(
            aggregate["tvpi"], (first["tvpi"] + second["tvpi"]) / 2.0
        )


class KsPmeTests(unittest.TestCase):
    def setUp(self):
        self.start = date(2025, 1, 1)
        self.middle = date(2025, 6, 1)
        self.asof = date(2026, 1, 1)

    def flow(self, day, kind, amount):
        return {"date": day, "kind": kind, "amount_cents": amount}

    def test_matches_benchmark_when_cashflows_track_total_return(self):
        result = ks_pme(
            [self.flow(self.start, "CALL", 10000), self.flow(self.asof, "DISTRIBUTION", 6000)],
            nav=6000,
            asof=self.asof,
            benchmark=[(self.start, 100.0), (self.asof, 120.0)],
        )
        self.assertAlmostEqual(result, 1.0)

    def test_multiple_cashflow_dates_use_their_own_index_levels(self):
        result = ks_pme(
            [
                self.flow(self.start, "CALL", 10000),
                self.flow(self.middle, "CALL", 5000),
                self.flow(self.middle, "DISTRIBUTION", 4000),
            ],
            nav=12000,
            asof=self.asof,
            benchmark=[(self.start, 100.0), (self.middle, 125.0), (self.asof, 150.0)],
        )
        # Terminal-value contributions: 15000 + 6000; distributions: 4800.
        self.assertAlmostEqual(result, (4800.0 + 12000.0) / 21000.0)

    def test_positive_index_scaling_does_not_change_pme(self):
        flows = [self.flow(self.start, "CALL", 10000)]
        first = ks_pme(flows, 13000, self.asof, [(self.start, 100), (self.asof, 120)])
        second = ks_pme(flows, 13000, self.asof, [(self.start, 500), (self.asof, 600)])
        self.assertAlmostEqual(first, second)

    def test_seven_day_lookback_is_inclusive(self):
        result = ks_pme(
            [self.flow(self.start, "CALL", 10000)],
            12000,
            self.asof,
            [(self.start - timedelta(days=7), 100), (self.asof, 120)],
        )
        self.assertAlmostEqual(result, 1.0)

    def test_stale_or_future_only_flow_level_does_not_fill_silently(self):
        for benchmark in (
            [(self.start - timedelta(days=8), 100), (self.asof, 120)],
            [(self.start + timedelta(days=1), 100), (self.asof, 120)],
            [],
        ):
            with self.subTest(benchmark=benchmark):
                self.assertIsNone(
                    ks_pme([self.flow(self.start, "CALL", 10000)], 12000, self.asof, benchmark)
                )

    def test_missing_terminal_level_is_unavailable(self):
        self.assertIsNone(
            ks_pme([self.flow(self.start, "CALL", 10000)], 12000, self.asof, [(self.start, 100)])
        )

    def test_no_contributions_has_no_pme_denominator(self):
        self.assertIsNone(
            ks_pme(
                [self.flow(self.start, "DISTRIBUTION", 10000)],
                5000,
                self.asof,
                [(self.start, 100), (self.asof, 120)],
            )
        )

    def test_invalid_index_levels_are_rejected(self):
        for level in (0.0, -1.0, float("nan"), float("inf")):
            with self.subTest(level=level):
                with self.assertRaises(ValueError):
                    ks_pme(
                        [self.flow(self.start, "CALL", 10000)],
                        12000,
                        self.asof,
                        [(self.start, level), (self.asof, 120)],
                    )

    def test_duplicate_benchmark_dates_are_rejected(self):
        with self.assertRaises(ValueError):
            ks_pme(
                [self.flow(self.start, "CALL", 10000)],
                12000,
                self.asof,
                [(self.start, 100), (self.start, 101), (self.asof, 120)],
            )

    def test_after_asof_cashflow_is_rejected(self):
        with self.assertRaises(ValueError):
            ks_pme(
                [self.flow(self.asof + timedelta(days=1), "CALL", 10000)],
                12000,
                self.asof,
                [(self.start, 100), (self.asof, 120)],
            )


if __name__ == "__main__":
    unittest.main()
