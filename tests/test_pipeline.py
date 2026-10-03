"""Workflow checks for information cutoffs and invalid reporting attempts."""
import csv
from contextlib import closing
from datetime import date
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from pmcapital.analytics import money, subscription_line_example, xirr
from pmcapital.pipeline import analyze, build

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "data" / "sample"
ASOF = date(2026, 6, 30)
KNOWN = date(2026, 8, 15)


class WorkflowTests(unittest.TestCase):
    def test_knowledge_cutoff_preserves_original_then_revises(self):
        first, _ = analyze(SAMPLE, ASOF, KNOWN)
        revised, _ = analyze(SAMPLE, ASOF, date(2026, 9, 15))
        old = next(row for row in first["funds"] if row["fund_id"] == "ALPHA")
        new = next(row for row in revised["funds"] if row["fund_id"] == "ALPHA")
        self.assertEqual(first["excluded_records"], {"cashflows": 1, "valuations": 1})
        self.assertEqual(new["paid_in_cents"] - old["paid_in_cents"], money("250000"))
        self.assertEqual(new["nav_cents"] - old["nav_cents"], -money("400000"))
        self.assertGreater(old["tvpi"], new["tvpi"])
        self.assertEqual(analyze(SAMPLE, ASOF, KNOWN)[0], first)

    def test_unavailable_exact_asof_nav_withholds_terminal_metrics(self):
        payload, _ = analyze(SAMPLE, ASOF, date(2026, 6, 30))
        for row in payload["funds"]:
            if row["nav_cents"] is None:
                self.assertIsNone(row["rvpi"])
                self.assertIsNone(row["tvpi"])
                self.assertIsNone(row["ks_pme"])
                self.assertIsNone(row["xirr"]["value"])
        self.assertTrue(any(row["code"] in {"STALE_VALUATION", "NO_VALUATION"} for row in payload["controls"]))

    def test_sql_cash_totals_and_persisted_controls(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            output = Path(directory) / "output"
            result = build(SAMPLE, output, ASOF, KNOWN)
            status = json.loads((output / "run_status.json").read_text())
            self.assertEqual(status["status"], "REVIEW_REQUIRED")
            pack = output / status["pack"]
            with closing(sqlite3.connect(pack / "warehouse.sqlite")) as conn:
                total = conn.execute("SELECT SUM(paid_in_cents),SUM(distributed_cents) FROM fund_cash_summary").fetchone()
                control_count = conn.execute("SELECT COUNT(*) FROM controls").fetchone()[0]
            self.assertEqual(total, (sum(row["paid_in_cents"] for row in result["funds"]), sum(row["distributed_cents"] for row in result["funds"])))
            self.assertEqual(control_count, len(result["controls"]))
            self.assertTrue({"warehouse.sqlite", "analytics.json", "fund_metrics.csv", "report.html", "investor_statements.csv", "partnership_accounting.json", "accounting_journal.csv", "waterfall_scenarios.csv", "public_research.json"}.issubset(status["artifacts"]))

    def test_failed_attempt_blocks_current_report_and_keeps_history(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            data, output = root / "data", root / "output"
            shutil.copytree(SAMPLE, data)
            build(data, output, ASOF, KNOWN)
            original = json.loads((output / "run_status.json").read_text())
            with (data / "cashflows.csv").open(newline="") as stream:
                reader = csv.DictReader(stream)
                names, rows = reader.fieldnames, list(reader)
            rows.append(rows[0].copy())
            with (data / "cashflows.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=names)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "duplicate"):
                build(data, output, ASOF, KNOWN)
            failed = json.loads((output / "run_status.json").read_text())
            self.assertEqual(failed["status"], "FAILED")
            self.assertIsNone(failed["pack"])
            self.assertEqual(failed["artifacts"], {})
            self.assertIn("current report blocked", (output / "report.html").read_text())
            self.assertTrue((output / original["pack"] / "analytics.json").exists())

    def test_line_timing_increases_rate_and_reduces_profit(self):
        result = subscription_line_example()
        self.assertGreater(result["delayed_rate"], result["immediate_rate"])
        self.assertGreater(result["delayed_paid_in_cents"], result["immediate_paid_in_cents"])
        self.assertEqual(result["delayed_paid_in_cents"] - result["immediate_paid_in_cents"], result["financing_cost_cents"])

    def test_failed_primary_accounting_blocks_current_release(self):
        rejected = {"capital": {"status": "FAILED", "failed_event": {"message": "Insufficient cash"}}}
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            output = Path(directory) / "output"
            with patch("pmcapital.advanced.assemble_advanced", return_value=rejected):
                with self.assertRaisesRegex(ValueError, "Primary partnership accounting failed"):
                    build(SAMPLE, output, ASOF, KNOWN)
            status = json.loads((output / "run_status.json").read_text())
            self.assertEqual(status["status"], "FAILED")
            self.assertIsNone(status["pack"])
            self.assertEqual(status["artifacts"], {})

    def test_zero_irr_and_large_cents_contract(self):
        zero = xirr([(date(2024, 1, 1), -10000), (date(2025, 1, 1), 10000)])
        self.assertEqual(zero["value"], 0)
        self.assertEqual(zero["residual_cents"], 0)
        self.assertEqual(money("92233720368547758.07"), 2**63 - 1)
        for value in ("92233720368547758.08", "1000000000000000000000000000.001", "1e999999"):
            with self.assertRaises(ValueError):
                money(value)


if __name__ == "__main__":
    unittest.main()
