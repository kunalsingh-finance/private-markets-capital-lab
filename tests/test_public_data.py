"""Generated fixtures verify parsing and governance; no fixture is source data."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
import unittest

from pmcapital.public_data import (make_snapshot, parse_amount,
    parse_fund_summary_html, public_research_summary, save_snapshot, validate_record)


def row(name="GENERATED TEST FUND", nav=45000):
    return {"fund_name": name, "vintage": 2019, "commitment_cents": 100000,
            "contributions_cents": 50000, "distributions_cents": 30000,
            "nav_cents": nav, "reported_multiple": 1.5, "reported_irr": 0.1,
            "source_row": "Generated test fixture; not an official observation"}


def snapshot(records=None, retrieved_at="2026-10-03T03:00:00Z"):
    return make_snapshot(source_id="calstrs_fye2025", asof_date="2025-06-30",
        retrieved_at=retrieved_at, capture_method="GENERATED_TEST_FIXTURE",
        records=records or [row()], coverage="GENERATED TEST ONLY")


FIXTURE = """<h1>GENERATED TEST FIXTURE - NOT OFFICIAL DATA</h1>
<p>As of June 30, 2025</p><table><thead><tr><th>Description</th><th>VY</th>
<th>Capital Committed</th><th>Capital Contributed</th><th>Capital Distributed</th>
<th>Market Value</th><th>Net Multiple</th><th>Net IRR</th></tr></thead>
<tbody><tr><td>GENERATED A &amp; B FUND</td><td>2019</td><td>1,000.00</td>
<td>500.00</td><td>300.00</td><td>450.00</td><td>1.5</td><td>(10.00)</td></tr>
<tr><td>GENERATED MISSING VALUE FUND</td><td>2020</td><td>1,000</td>
<td>500</td><td>200</td><td>-</td><td>N/M</td><td>N/M</td></tr></tbody></table>"""


class PublicDataTests(unittest.TestCase):
    def test_parser_exact_cents_missing_markers_and_reported_irr(self):
        parsed = parse_fund_summary_html(FIXTURE)
        self.assertEqual(parsed["asof_date"], "2025-06-30")
        first, missing = parsed["records"]
        self.assertEqual(first["fund_name"], "GENERATED A & B FUND")
        self.assertEqual(first["contributions_cents"], 50000)
        self.assertAlmostEqual(first["tvpi"], 1.5)
        self.assertAlmostEqual(first["reported_irr"], -0.1)
        self.assertEqual(first["multiple_comparison"], "WITHIN_0_05")
        self.assertIsNone(first["independent_xirr"])
        self.assertIsNone(missing["nav_cents"])
        self.assertIsNone(missing["tvpi"])
        self.assertAlmostEqual(missing["dpi"], 0.4)

    def test_parser_requires_explicit_asof_and_recognized_columns(self):
        with self.assertRaises(ValueError):
            parse_fund_summary_html(FIXTURE.replace("As of June 30, 2025", "No date"))
        with self.assertRaises(ValueError):
            parse_fund_summary_html(FIXTURE.replace("Market Value", "Unknown Value"))
        with self.assertRaises(ValueError):
            parse_fund_summary_html(FIXTURE.replace("<td>2019</td>", "<td>2019</td><td>extra</td>"))

    def test_units_are_explicit_and_nonfinite_or_fractional_cents_rejected(self):
        self.assertEqual(parse_amount("1.234", scale=1000000), 123400000)
        self.assertIsNone(parse_amount("—"))
        for text in ("NaN", "Infinity", "-10", "0.001"):
            with self.assertRaises(ValueError):
                parse_amount(text)
        with self.assertRaises(ValueError):
            validate_record({**row(), "contributions_cents": True})

    def test_immutable_snapshot_content_hash_and_no_cashflow_reconstruction(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current = snapshot([row(), row("GENERATED MISSING", None)])
            path = save_snapshot(root, current)
            original = path.read_bytes()
            self.assertEqual(save_snapshot(root, current), path)
            self.assertEqual(path.read_bytes(), original)
            result = public_research_summary(root)
            self.assertEqual(result["status"], "AVAILABLE_PARTIAL")
            self.assertEqual(len(result["records"]), 2)
            self.assertIsNone(result["provenance"][0]["raw_source_sha256"])
            self.assertEqual(result["provenance"][0]["file"], path.relative_to(root).as_posix())
            cohort = next(item for item in result["cohort_metrics"] if item["vintage"] == "ALL_CAPTURED")
            self.assertEqual(cohort["complete_multiple_row_count"], 1)
            self.assertAlmostEqual(cohort["tvpi"], 1.5)
            self.assertIsNone(result["records"][0]["independent_xirr"])
            changed = json.loads(original)
            changed["coverage"] = "ALTERED METADATA"
            path.write_text(json.dumps(changed), encoding="utf-8")
            with self.assertRaises(ValueError):
                public_research_summary(root)

    def test_timezone_selection_uses_actual_instant_not_lexical_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            # 02:00Z is later than 02:30+01:00 (=01:30Z).
            earlier = snapshot([row("GENERATED EARLIER")], "2026-10-03T02:30:00+01:00")
            later = snapshot([row("GENERATED LATER")], "2026-10-03T02:00:00Z")
            save_snapshot(root, earlier)
            save_snapshot(root, later)
            result = public_research_summary(root)
            self.assertEqual(result["records"][0]["fund_name"], "GENERATED LATER")
            self.assertEqual(sum(item["selected"] for item in result["snapshots"]), 1)
            self.assertEqual(len(result["provenance"]), 2)

    def test_empty_sources_return_unavailable_without_fake_records(self):
        with tempfile.TemporaryDirectory() as directory:
            result = public_research_summary(Path(directory))
            self.assertEqual(result["status"], "UNAVAILABLE")
            self.assertEqual(result["records"], [])


if __name__ == "__main__":
    unittest.main()
