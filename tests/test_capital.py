"""Economic-accounting checks independent of the reporting presentation."""

from copy import deepcopy
from datetime import date
import json
import unittest

from pmcapital.capital import allocate_cents, load_capital_case, management_fee, run_capital_case


def event(event_id, day, kind, amount, **extra):
    return {"event_id": event_id, "effective_date": day, "recorded_date": day,
            "kind": kind, "amount_cents": amount, **extra}


def simple_case(events, commitments=(60, 38, 2), rate=0, limit=1000):
    return {"case_id": "TEST", "name": "Synthetic test partnership", "asof": "2026-06-30",
            "known_at": "2026-08-15", "facility_limit_cents": limit, "facility_rate_bps": rate,
            "management_fee_bps": 0,
            "investors": [{"investor_id": key, "name": key, "role": role, "commitment_cents": amount}
                          for key, role, amount in zip(("LP_A", "LP_B", "GP"), ("LP", "LP", "GP"), commitments)],
            "events": events}


class AllocationAndFeeTests(unittest.TestCase):
    def test_largest_remainder_exact_sum_stable_ties_and_zero_weight(self):
        weights = {"B": 1, "A": 1, "ZERO": 0}
        self.assertEqual(allocate_cents(1, weights), {"A": 1, "B": 0, "ZERO": 0})
        self.assertEqual(allocate_cents(3, weights), {"A": 2, "B": 1, "ZERO": 0})
        self.assertEqual(allocate_cents(-3, weights), {"A": -2, "B": -1, "ZERO": 0})
        self.assertEqual(allocate_cents(3, dict(reversed(list(weights.items())))), allocate_cents(3, weights))

    def test_nonproportional_pennies_reconcile_for_many_amounts(self):
        for amount in range(-200, 201):
            parts = allocate_cents(amount, {"LP_A": 60, "LP_B": 38, "GP": 2})
            self.assertEqual(sum(parts.values()), amount)
            for key, value in parts.items():
                self.assertLessEqual(abs(value - amount * {"LP_A": .6, "LP_B": .38, "GP": .02}[key]), 1)

    def test_invalid_integer_and_empty_weights_rejected(self):
        for amount, weights in ((True, {"A": 1}), (1.0, {"A": 1}), (1, {}), (1, {"A": 0}),
                                (1, {"A": -1}), (1, {"A": True})):
            with self.subTest(amount=amount, weights=weights), self.assertRaises(ValueError):
                allocate_cents(amount, weights)

    def test_committed_capital_management_fee_actual_365(self):
        self.assertEqual(management_fee(1_000_000_000, 200, date(2026, 1, 1), date(2026, 4, 1)), 4_931_507)
        self.assertEqual(management_fee(36_500, 50, date(2026, 1, 1), date(2026, 1, 2)), 1)
        self.assertEqual(management_fee(36_500_000, 100, date(2024, 1, 1), date(2025, 1, 1)), 366_000)

    def test_fee_contract_invalid_dates_and_boolean_rate_rejected(self):
        with self.assertRaises(ValueError):
            management_fee(100, 100, date(2026, 2, 1), date(2026, 1, 1))
        with self.assertRaises(ValueError):
            management_fee(100, True, date(2026, 1, 1), date(2026, 2, 1))
        case = load_capital_case()
        case["events"][5]["amount_cents"] += 1
        with self.assertRaisesRegex(ValueError, "rate-derived"):
            run_capital_case(case)


class LedgerTests(unittest.TestCase):
    def assert_reconciled(self, result):
        for row in result["event_journal"]:
            balances = row["balances_after"]
            nav = balances["cash_cents"] + balances["investments_cents"] - balances["debt_cents"] - balances["accrued_interest_cents"]
            self.assertEqual(nav, sum(row["investor_capital_after"].values()))
            self.assertEqual(balances["reconciliation_difference_cents"], 0)
            self.assertEqual(balances["equity_cents"], nav)
        self.assertEqual(result["balances"]["equity_cents"], sum(row["capital_cents"] for row in result["investors"]))
        self.assertEqual(result["nav_bridge"]["reconciliation_difference_cents"], 0)
        for row in result["investors"]:
            expected = row["paid_in_cents"] + row["gain_cents"] - row["fee_cents"] - row["interest_cents"] - row["distributed_cents"] + row["carry_net_cents"]
            self.assertEqual(row["capital_cents"], expected)
            self.assertEqual(row["gain_cents"], row["realized_gain_cents"] + row["unrealized_gain_cents"])
            self.assertEqual(row["unfunded_cents"], row["commitment_cents"] + row["recallable_cents"] - row["paid_in_cents"])

    def test_base_balance_sheet_and_nav_bridge(self):
        result = run_capital_case()
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["balances"]["cash_cents"], 930_627_397)
        for field in ("investments_cents", "debt_cents", "accrued_interest_cents"):
            self.assertEqual(result["balances"][field], 0)
        self.assertEqual(result["totals"]["interest_cents"], 9_509_589)
        self.assertEqual(result["totals"]["fee_cents"], 9_863_014)
        self.assertEqual(result["totals"]["gain_cents"], 300_000_000)
        self.assertEqual(result["totals"]["realized_gain_cents"], 300_000_000)
        self.assertEqual(result["totals"]["unrealized_gain_cents"], 0)
        self.assertTrue(all(row["unrealized_gain_cents"] == 0 for row in result["investors"]))
        self.assertEqual(result["totals"]["distributed_cents"], 0)
        self.assert_reconciled(result)
        json.dumps(result, allow_nan=False)

    def test_interest_is_accrued_before_repayment_and_payment_not_double_expensed(self):
        result = run_capital_case()
        accruals = [row for row in result["event_journal"] if row["kind"] == "INTEREST_ACCRUAL"]
        self.assertEqual(len(accruals), 1)
        self.assertEqual(accruals[0]["metadata"]["accrual_days"], 89)
        payment = next(row for row in result["event_journal"] if row["kind"] == "INTEREST_PAYMENT")
        self.assertEqual(payment["balances_before"]["accrued_interest_cents"], 9_509_589)
        self.assertEqual(sum(row["capital_cents"] for row in payment["investor_allocations"].values()), 0)
        self.assert_reconciled(result)

    def test_asof_accrual_and_negative_startup_equity_is_visible(self):
        case = simple_case([event("DRAW", "2026-01-01", "FACILITY_DRAW", 36_500)], rate=100, limit=40_000)
        result = run_capital_case(case, asof=date(2026, 1, 2))
        self.assertEqual(result["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["balances"]["accrued_interest_cents"], 1)
        self.assertEqual(result["balances"]["equity_cents"], -1)
        self.assertEqual(result["event_journal"][-1]["source_event_id"], "ASOF")
        self.assert_reconciled(result)

    def test_full_delayed_distribution_closes_every_capital_account(self):
        result = run_capital_case(load_capital_case("delayed_distribution"))
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["balances"]["equity_cents"], 0)
        self.assertTrue(all(row["capital_cents"] == 0 for row in result["investors"]))
        self.assert_reconciled(result)

    def test_cash_failure_preserves_last_valid_accounts_and_unposted_event(self):
        result = run_capital_case(load_capital_case("cash_shortfall"))
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failed_event"]["code"], "CASH_SHORTFALL")
        self.assertEqual(result["failed_event"]["event_id"], "NS005")
        self.assertEqual(result["balances"]["cash_cents"], 0)
        self.assertEqual(result["balances"]["accrued_interest_cents"], 9_509_589)
        self.assertIn("NS005", result["unposted_source_event_ids"])
        self.assertNotIn("NS005", [row["event_id"] for row in result["event_journal"]])
        self.assertEqual(result["effective_through"], "2026-04-01")
        self.assert_reconciled(result)

    def test_draw_limit_and_repayment_overpayment_reject_without_partial_post(self):
        case = simple_case([event("DRAW", "2026-01-01", "FACILITY_DRAW", 101)], limit=100)
        result = run_capital_case(case)
        self.assertEqual(result["failed_event"]["code"], "FACILITY_LIMIT")
        self.assertEqual(result["event_journal"], [])
        self.assertEqual(result["balances"]["cash_cents"], 0)
        case = load_capital_case()
        case["events"][3]["amount_cents"] += 1
        result = run_capital_case(case)
        self.assertEqual(result["failed_event"]["code"], "DEBT_OVERPAYMENT")
        self.assertEqual(result["balances"]["debt_cents"], 600_000_000)
        self.assert_reconciled(result)

    def test_accrued_interest_cannot_be_overpaid(self):
        case = load_capital_case()
        case["events"][4]["amount_cents"] += 1
        result = run_capital_case(case)
        self.assertEqual(result["failed_event"]["code"], "INTEREST_OVERPAYMENT")
        self.assertEqual(result["balances"]["accrued_interest_cents"], 9_509_589)
        self.assert_reconciled(result)

    def test_investment_book_cannot_be_over_realized_or_revalued_negative(self):
        case = load_capital_case()
        case["events"][7]["cost_cents"] += 1
        result = run_capital_case(case)
        self.assertEqual(result["failed_event"]["code"], "NEGATIVE_INVESTMENT_BOOK")
        self.assertEqual(result["balances"]["investments_cents"], 660_000_000)
        case = simple_case([event("CALL", "2026-01-01", "CALL", 100), event("INVEST", "2026-01-01", "INVEST", 100),
                            event("MARK", "2026-02-01", "REVALUE", 0, delta_cents=-101)])
        self.assertEqual(run_capital_case(case)["failed_event"]["code"], "NEGATIVE_INVESTMENT_BOOK")

    def test_realization_loss_and_markdown_allocate_signed_gains(self):
        case = simple_case([event("CALL", "2026-01-01", "CALL", 100), event("INVEST", "2026-01-01", "INVEST", 100),
                            event("MARK", "2026-02-01", "REVALUE", 0, delta_cents=-10),
                            event("EXIT", "2026-03-01", "REALIZATION", 80, cost_cents=90, historical_cost_cents=100)])
        result = run_capital_case(case)
        self.assertEqual(result["totals"]["gain_cents"], -20)
        self.assertEqual(result["totals"]["realized_gain_cents"], -20)
        self.assertEqual(result["totals"]["unrealized_gain_cents"], 0)
        self.assertEqual(result["balances"]["cash_cents"], 80)
        self.assert_reconciled(result)

    def test_recallable_call_capacity_allowed_and_regular_distribution_does_not_restore_it(self):
        case = load_capital_case("recallable")
        result = run_capital_case(case)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["totals"]["paid_in_cents"], 1_300_000_000)
        self.assertTrue(all(row["unfunded_cents"] == 0 for row in result["investors"]))
        self.assert_reconciled(result)
        case["events"][3]["kind"] = "DISTRIBUTION"
        rejected = run_capital_case(case)
        self.assertEqual(rejected["failed_event"]["code"], "OVER_COMMITMENT")
        self.assertEqual(rejected["totals"]["paid_in_cents"], 1_000_000_000)

    def test_recallable_capacity_is_investor_specific(self):
        case = load_capital_case("recallable")
        case["events"][3]["investor_allocations"] = {"LP_A": 300_000_000}
        result = run_capital_case(case)
        self.assertEqual(result["failed_event"]["code"], "OVER_COMMITMENT")
        self.assertIn("call exceeds original commitment", result["failed_event"]["message"])

    def test_partial_disposal_reclassifies_only_disposed_marked_gain(self):
        case = simple_case([event("CALL", "2026-01-01", "CALL", 100), event("INVEST", "2026-01-01", "INVEST", 100),
                            event("MARK", "2026-02-01", "REVALUE", 0, delta_cents=20),
                            event("PARTIAL", "2026-03-01", "REALIZATION", 75, cost_cents=60, historical_cost_cents=50)])
        result = run_capital_case(case)
        self.assertEqual(result["balances"]["investments_cents"], 60)
        self.assertEqual(result["balances"]["investment_cost_cents"], 50)
        self.assertEqual(result["totals"]["gain_cents"], 35)
        self.assertEqual(result["totals"]["realized_gain_cents"], 25)
        self.assertEqual(result["totals"]["unrealized_gain_cents"], 10)
        self.assert_reconciled(result)

    def test_downside_partial_then_full_exit_preserves_cost_and_clears_marks(self):
        case = simple_case([event("CALL", "2026-01-01", "CALL", 100), event("INVEST", "2026-01-01", "INVEST", 100),
                            event("MARK", "2026-02-01", "REVALUE", 0, delta_cents=-40),
                            event("PARTIAL", "2026-03-01", "REALIZATION", 20, cost_cents=30, historical_cost_cents=50)])
        partial = run_capital_case(case)
        self.assertEqual(partial["totals"]["realized_gain_cents"], -30)
        self.assertEqual(partial["totals"]["unrealized_gain_cents"], -20)
        self.assertEqual(partial["balances"]["investment_cost_cents"], 50)
        case["events"].append(event("FINAL", "2026-04-01", "REALIZATION", 20, cost_cents=30, historical_cost_cents=50))
        final = run_capital_case(case)
        self.assertEqual(final["totals"]["realized_gain_cents"], -60)
        self.assertEqual(final["totals"]["unrealized_gain_cents"], 0)
        self.assertTrue(all(row["unrealized_gain_cents"] == 0 for row in final["investors"]))
        self.assertEqual(final["balances"]["investment_cost_cents"], 0)
        self.assert_reconciled(final)

    def test_marked_sale_requires_historical_cost_and_cost_cannot_be_overdisposed(self):
        case = load_capital_case()
        del case["events"][7]["historical_cost_cents"]
        result = run_capital_case(case)
        self.assertEqual(result["failed_event"]["code"], "MISSING_HISTORICAL_COST")
        case["events"][7]["historical_cost_cents"] = 600_000_001
        result = run_capital_case(case)
        self.assertEqual(result["failed_event"]["code"], "NEGATIVE_INVESTMENT_COST")

    def test_full_disposal_unwinds_accumulated_penny_marks_per_investor(self):
        case = simple_case([event("CALL", "2026-01-01", "CALL", 100), event("INVEST", "2026-01-01", "INVEST", 100),
                            event("MARK1", "2026-02-01", "REVALUE", 0, delta_cents=1),
                            event("MARK2", "2026-03-01", "REVALUE", 0, delta_cents=1),
                            event("EXIT", "2026-04-01", "REALIZATION", 104, cost_cents=102, historical_cost_cents=100)])
        result = run_capital_case(case)
        self.assertEqual(result["totals"]["realized_gain_cents"], 4)
        self.assertTrue(all(row["unrealized_gain_cents"] == 0 for row in result["investors"]))
        self.assert_reconciled(result)

    def test_call_above_original_commitment_is_rejected(self):
        case = simple_case([event("CALL", "2026-01-01", "CALL", 101)])
        result = run_capital_case(case)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["totals"]["paid_in_cents"], 0)

    def test_cutoff_withholds_late_fee_then_selects_it_without_backfill(self):
        case = load_capital_case("recallable")
        early = run_capital_case(case)
        late = run_capital_case(case, known_at=date(2026, 9, 15))
        self.assertEqual(early["balances"]["cash_cents"] - late["balances"]["cash_cents"], 100_000)
        self.assertEqual(early["excluded_events"], [{"event_id": "NR006", "effective_date": "2026-05-15",
                                                    "recorded_date": "2026-09-01", "reason": "NOT_KNOWN_AT"}])
        self.assert_reconciled(late)

    def test_cutoff_does_not_inject_an_unknown_draw_to_hide_cash_shortfall(self):
        case = simple_case([event("DRAW", "2026-01-01", "FACILITY_DRAW", 100, recorded_date="2026-09-01"),
                            event("INVEST", "2026-01-02", "INVEST", 100)])
        result = run_capital_case(case)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["failed_event"]["code"], "CASH_SHORTFALL")
        self.assertEqual(result["excluded_events"][0]["event_id"], "DRAW")
        self.assertEqual(result["event_journal"], [])

    def test_events_sort_chronologically_and_preserve_same_day_input_order(self):
        case = simple_case([event("EXIT", "2026-03-01", "REALIZATION", 110, cost_cents=100),
                            event("CALL", "2026-01-01", "CALL", 100), event("INVEST", "2026-01-01", "INVEST", 100)])
        result = run_capital_case(case)
        self.assertEqual([row["event_id"] for row in result["event_journal"]], ["CALL", "INVEST", "EXIT"])
        self.assertEqual(result["balances"]["cash_cents"], 110)
        bad_order = deepcopy(case)
        bad_order["events"][1:3] = list(reversed(bad_order["events"][1:3]))
        self.assertEqual(run_capital_case(bad_order)["failed_event"]["code"], "CASH_SHORTFALL")

    def test_duplicate_source_ids_and_reserved_generated_ids_rejected(self):
        case = simple_case([event("DUP", "2026-01-01", "CALL", 1), event("DUP", "2026-02-01", "CALL", 1)])
        with self.assertRaisesRegex(ValueError, "replay"):
            run_capital_case(case)
        case["events"] = [event("ACCRUAL:ASOF", "2026-01-01", "CALL", 1)]
        with self.assertRaisesRegex(ValueError, "reserved"):
            run_capital_case(case)

    def test_explicit_allocation_exact_sum_known_investors_and_supported_kind_required(self):
        for explicit in ({"UNKNOWN": 100}, {"LP_A": 99}, {"LP_A": True}):
            case = simple_case([event("CALL", "2026-01-01", "CALL", 100, investor_allocations=explicit)])
            with self.subTest(explicit=explicit), self.assertRaises(ValueError):
                run_capital_case(case)
        case = simple_case([event("FEE", "2026-01-01", "FEE", 1, investor_allocations={"LP_A": 1})])
        with self.assertRaises(ValueError):
            run_capital_case(case)

    def test_carry_transfer_and_explicit_terminal_distribution_close_every_account(self):
        case = load_capital_case()
        case["events"].append(event("CARRY", "2026-06-30", "CARRY_ALLOCATION", 10_000_001, recipient_id="GP"))
        after_carry = run_capital_case(case)
        self.assertEqual(after_carry["balances"]["cash_cents"], 930_627_397)
        self.assertEqual(sum(row["carry_net_cents"] for row in after_carry["investors"]), 0)
        allocations = {row["investor_id"]: row["capital_cents"] for row in after_carry["investors"]}
        case["events"].append(event("FINAL", "2026-06-30", "DISTRIBUTION", sum(allocations.values()), investor_allocations=allocations))
        closed = run_capital_case(case)
        self.assertEqual(closed["status"], "READY")
        self.assertTrue(all(row["capital_cents"] == 0 for row in closed["investors"]))
        self.assertEqual(closed["balances"]["equity_cents"], 0)
        self.assertEqual([row["event_id"] for row in closed["event_journal"]][-2:], ["CARRY", "FINAL"])
        self.assert_reconciled(closed)

    def test_engine_does_not_mutate_caller_case_and_hash_identifies_input(self):
        case = load_capital_case()
        original = deepcopy(case)
        result = run_capital_case(case)
        self.assertEqual(case, original)
        self.assertEqual(result["input_sha256"], run_capital_case(case)["input_sha256"])
        case["name"] += " revised"
        self.assertNotEqual(result["input_sha256"], run_capital_case(case)["input_sha256"])


if __name__ == "__main__":
    unittest.main()
