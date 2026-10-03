"""Missing reporting facts must fail, even if remaining identities balance."""
from contextlib import closing, redirect_stdout
from datetime import date
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from pmcapital.pipeline import build
from scripts import verify_reporting

ROOT = Path(__file__).resolve().parents[1]


class ReportingVerificationTests(unittest.TestCase):
    def test_missing_event_or_waterfall_facts_are_rejected(self):
        for table, expected in [("fact_accounting_event", "accounting events"), ("fact_waterfall_tier", "waterfall tiers")]:
            with self.subTest(table=table), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                output = root / "output"
                build(ROOT / "data" / "sample", output, date(2026, 6, 30), date(2026, 8, 15))
                manifest = json.loads((output / "run_status.json").read_text())
                warehouse = output / manifest["pack"] / "warehouse.sqlite"
                with patch.object(verify_reporting, "ROOT", root), redirect_stdout(io.StringIO()):
                    self.assertEqual(verify_reporting.main(), 0)
                    with closing(sqlite3.connect(warehouse)) as conn, conn:
                        conn.execute("DELETE FROM " + table)
                    with self.assertRaisesRegex(ValueError, expected):
                        verify_reporting.main()


if __name__ == "__main__":
    unittest.main()
