"""Cross-module evidence checks; preserve independent populations and dates."""
from datetime import date
from pathlib import Path
import unittest

from pmcapital.advanced import assemble_advanced

ROOT = Path(__file__).resolve().parents[1]


class AdvancedIntegrationTests(unittest.TestCase):
    def test_terminal_cash_drives_waterfall_and_every_account_closes(self):
        result = assemble_advanced(ROOT, date(2026, 6, 30), date(2026, 8, 15))
        opening, closed, linked = result["capital_before_distribution"], result["capital"], result["linked_exit"]
        self.assertEqual(linked["status"], "CLOSED")
        self.assertEqual(linked["waterfall"]["total_proceeds_cents"], opening["balances"]["cash_cents"])
        self.assertEqual(sum(linked["distribution_allocations"].values()), opening["balances"]["cash_cents"])
        self.assertEqual(closed["balances"]["equity_cents"], 0)
        self.assertTrue(all(row["capital_cents"] == 0 for row in closed["investors"]))
        self.assertEqual(closed["totals"]["unrealized_gain_cents"], 0)
        self.assertEqual(closed["totals"]["realized_gain_cents"], 300_000_000)

    def test_gp_promote_is_a_transfer_not_created_fund_wealth(self):
        result = assemble_advanced(ROOT, date(2026, 6, 30), date(2026, 8, 15))
        closed, terms = result["capital"], result["linked_exit"]["waterfall"]
        self.assertEqual(sum(row["carry_net_cents"] for row in closed["investors"]), 0)
        self.assertEqual(closed["totals"]["distributed_cents"], terms["lp_total_cents"] + terms["gp_total_cents"])
        for row in closed["investors"]:
            self.assertEqual(row["paid_in_cents"] + row["gain_cents"] - row["fee_cents"] - row["interest_cents"] + row["carry_net_cents"] - row["distributed_cents"], row["capital_cents"])
            self.assertEqual(row["rvpi"], 0)
            self.assertAlmostEqual(row["tvpi"], row["dpi"])

    def test_no_unobserved_asset_sale_is_invented_at_early_cutoff(self):
        result = assemble_advanced(ROOT, date(2026, 6, 30), date(2026, 6, 30))
        self.assertEqual(result["linked_exit"]["status"], "NOT_TERMINALLY_LIQUIDATED")
        self.assertGreater(result["capital"]["balances"]["investments_cents"], 0)
        self.assertEqual(result["capital"]["totals"]["distributed_cents"], 0)
        self.assertFalse(any(row["event_id"] == "TERMINAL_DISTRIBUTION" for row in result["capital"]["event_journal"]))

    def test_stress_is_preserved_as_a_separate_fixed_scenario(self):
        result = assemble_advanced(ROOT, date(2026, 6, 30), date(2026, 8, 15))
        scenarios = {row["name"]: row["result"] for row in result["capital_scenarios"]}
        self.assertEqual(scenarios["cash_shortfall"]["status"], "FAILED")
        self.assertIsNotNone(scenarios["cash_shortfall"]["failed_event"])
        self.assertEqual(scenarios["recallable"]["status"], "READY")
        self.assertEqual(scenarios["delayed_distribution"]["status"], "READY")
        self.assertNotEqual(scenarios["delayed_distribution"]["asof"], result["capital"]["asof"])
        self.assertEqual(result["capital"]["status"], "READY")


if __name__ == "__main__":
    unittest.main()
