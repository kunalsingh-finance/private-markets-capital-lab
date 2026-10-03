"""Governed public fund-summary observations, separate from cash-flow models.

Only allowlisted public sources are supported. A published fund summary cannot
reconstruct dated LP cash flows or independently validate a reported IRR/PME.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any

SOURCES = {
    "calstrs_fye2025": {
        "url": "https://www.calstrs.com/files/6765c6592/CalSTRSPrivateEquityPerformanceReportFYE2025.pdf",
        "format": "pdf", "name": "CalSTRS Private Equity Portfolio Performance",
    },
    "calpers_pep_print": {
        "url": "https://www.calpers.ca.gov/investments/about-investment-office/investment-organization/pep-fund-performance-print",
        "format": "html", "name": "CalPERS PEP Fund Performance Review",
    },
}
AMOUNT_FIELDS = ("commitment_cents", "contributions_cents", "distributions_cents", "nav_cents")
LIMITATIONS = [
    "Public fund summaries do not contain complete dated cash flows; independently calculated XIRR and PME are unavailable.",
    "These observations are a separate public research context, acquired after the synthetic report cut-off; they are not backdated into that report.",
    "Coverage is the captured subset, not the pension's total portfolio or a representative investment sample.",
    "A printed dash is unavailable, not assumed zero. Computed multiples are unavailable when contributions or NAV/distributions are unavailable.",
    "Reported IRR is a source observation, not a return recalculated or verified by this project.",
    "Summary contributions need not equal remaining commitment; recycling, recallable distributions and fee accounting cannot be inferred from these fields.",
]


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _number(value: Any, *, allow_negative: bool = False) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("A reported numeric measure must be numeric or null")
    decimal = Decimal(str(value))
    if not decimal.is_finite() or (decimal < 0 and not allow_negative):
        raise ValueError("Invalid reported measure")
    return float(value)


def validate_record(record: dict) -> dict:
    """Type-check a summary row; derive only ratios supported by observed totals."""
    name = record.get("fund_name")
    vintage = record.get("vintage")
    if not isinstance(name, str) or not name.strip() or len(name) > 500:
        raise ValueError("Fund name is required")
    if isinstance(vintage, bool) or not isinstance(vintage, int) or not 1900 <= vintage <= 2100:
        raise ValueError("Vintage must be a plausible integer year")
    result = {"fund_name": name.strip(), "vintage": vintage}
    for field in AMOUNT_FIELDS:
        value = record.get(field)
        if value is not None and (isinstance(value, bool) or not isinstance(value, int) or value < 0):
            raise ValueError(f"{field} must be nonnegative integer cents or null")
        result[field] = value
    result["reported_multiple"] = _number(record.get("reported_multiple"))
    result["reported_irr"] = _number(record.get("reported_irr"), allow_negative=True)
    source_row = record.get("source_row")
    if source_row is not None and (not isinstance(source_row, str) or len(source_row) > 500):
        raise ValueError("Source row evidence must be text or null")
    result["source_row"] = source_row
    paid, distributed, nav = (result[key] for key in ("contributions_cents", "distributions_cents", "nav_cents"))
    denominator_ok = paid is not None and paid > 0
    result["dpi"] = distributed / paid if denominator_ok and distributed is not None else None
    result["rvpi"] = nav / paid if denominator_ok and nav is not None else None
    result["tvpi"] = (distributed + nav) / paid if denominator_ok and distributed is not None and nav is not None else None
    reported = result["reported_multiple"]
    result["multiple_difference"] = result["tvpi"] - reported if result["tvpi"] is not None and reported is not None else None
    # Explicit comparison band for prototype review; this does not infer the
    # source's precision or certify that it uses the same methodology.
    result["multiple_comparison"] = "UNAVAILABLE" if result["multiple_difference"] is None else ("WITHIN_0_05" if abs(result["multiple_difference"]) <= 0.05000001 else "REVIEW")
    result["independent_xirr"] = None
    result["ks_pme"] = None
    return result


def make_snapshot(*, source_id: str, asof_date: str, retrieved_at: str,
                  capture_method: str, records: list[dict],
                  raw_source_sha256: str | None = None, source_publication_date: str | None = None,
                  asof_basis: str = "Explicit source heading", coverage: str = "Captured subset") -> dict:
    if source_id not in SOURCES:
        raise ValueError("Source is not allowlisted")
    date.fromisoformat(asof_date)
    parsed_time = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00"))
    if parsed_time.tzinfo is None:
        raise ValueError("Retrieval timestamp must include a timezone")
    if source_publication_date is not None:
        date.fromisoformat(source_publication_date)
    if raw_source_sha256 is not None and not re.fullmatch(r"[0-9a-f]{64}", raw_source_sha256):
        raise ValueError("Invalid raw-source digest")
    if not capture_method or not records:
        raise ValueError("A capture method and observed records are required")
    validated = [validate_record(row) for row in records]
    identities = [(row["fund_name"], row["vintage"]) for row in validated]
    if len(set(identities)) != len(identities):
        raise ValueError("Duplicate fund/vintage within a snapshot")
    return {
        "schema_version": 1, "kind": "DERIVED_OFFICIAL_OBSERVATIONS",
        "source_id": source_id, "source_name": SOURCES[source_id]["name"],
        "source_url": SOURCES[source_id]["url"], "asof_date": asof_date,
        "asof_basis": asof_basis, "retrieved_at": retrieved_at,
        "source_publication_date": source_publication_date,
        "capture_method": capture_method, "raw_source_sha256": raw_source_sha256,
        "coverage": coverage, "row_count": len(validated),
        "records_sha256": _digest(validated), "records": validated,
    }


def save_snapshot(root: Path, snapshot: dict) -> Path:
    """Write a content-addressed immutable normalized snapshot under the root."""
    validated = _validate_snapshot(snapshot)
    content = _canonical(validated)
    digest = hashlib.sha256(content).hexdigest()
    directory = Path(root) / "data" / "public_research"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{validated['source_id']}_{validated['asof_date']}_{digest[:12]}.json"
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError("An immutable snapshot path already has different bytes")
        return path
    with path.open("xb") as stream:
        stream.write(content)
    return path


def _validate_snapshot(snapshot: dict) -> dict:
    if snapshot.get("schema_version") != 1 or snapshot.get("kind") != "DERIVED_OFFICIAL_OBSERVATIONS":
        raise ValueError("Unsupported public snapshot schema")
    rebuilt = make_snapshot(
        source_id=snapshot["source_id"], asof_date=snapshot["asof_date"],
        retrieved_at=snapshot["retrieved_at"], capture_method=snapshot["capture_method"],
        records=snapshot["records"], raw_source_sha256=snapshot.get("raw_source_sha256"),
        source_publication_date=snapshot.get("source_publication_date"),
        asof_basis=snapshot.get("asof_basis", "Explicit source heading"),
        coverage=snapshot.get("coverage", "Captured subset"),
    )
    if rebuilt != snapshot:
        raise ValueError("Public snapshot fields, derived ratios, or record digest do not match")
    return rebuilt


def public_research_summary(root: Path) -> dict:
    """Return JSON-renderable observations, provenance and vintage cohort ratios.

    Select the newest as-of snapshot for each source, then the newest capture
    of that as-of date. Historical snapshots remain in provenance, not totals.
    No synthetic records are used as fallback for an unavailable public source.
    """
    root = Path(root)
    paths = sorted((root / "data" / "public_research").glob("*.json"))
    if not paths:
        return {"status": "UNAVAILABLE", "records": [], "snapshots": [], "provenance": [], "cohort_metrics": [], "limitations": LIMITATIONS + ["No captured official public observations are installed."]}
    loaded = []
    for path in paths:
        content = path.read_bytes()
        snapshot = _validate_snapshot(json.loads(content))
        digest = hashlib.sha256(content).hexdigest()
        if not path.stem.endswith("_" + digest[:12]):
            raise ValueError(f"Public snapshot content-address mismatch: {path.name}")
        metadata = {key: snapshot[key] for key in ("source_id", "source_name", "source_url", "asof_date", "retrieved_at", "source_publication_date", "capture_method", "raw_source_sha256", "coverage", "row_count", "asof_basis")}
        metadata.update(file=path.relative_to(root).as_posix(), snapshot_file=path.relative_to(root).as_posix(), sha256=digest, kind=snapshot["kind"])
        loaded.append((snapshot, metadata))
    chosen = {}
    for snapshot, metadata in loaded:
        rank = (date.fromisoformat(snapshot["asof_date"]),
                datetime.fromisoformat(snapshot["retrieved_at"].replace("Z", "+00:00")),
                metadata["sha256"])
        previous = chosen.get(snapshot["source_id"])
        if previous is None or rank > previous[0]:
            chosen[snapshot["source_id"]] = (rank, snapshot, metadata)
    selected_files = {item[2]["file"] for item in chosen.values()}
    records, provenance, cohorts = [], [], []
    for snapshot, metadata in loaded:
        metadata["selected"] = metadata["file"] in selected_files
        provenance.append(metadata)
        if not metadata["selected"]:
            continue
        for row in snapshot["records"]:
            records.append({**row, "source_id": snapshot["source_id"], "asof_date": snapshot["asof_date"], "source_url": snapshot["source_url"], "snapshot_file": metadata["file"]})
        grouped = defaultdict(list)
        for row in snapshot["records"]:
            grouped[row["vintage"]].append(row)
        grouped["ALL_CAPTURED"] = snapshot["records"]
        for vintage, rows in grouped.items():
            complete = [row for row in rows if row["tvpi"] is not None]
            paid = sum(row["contributions_cents"] for row in complete)
            distributions = sum(row["distributions_cents"] for row in complete)
            nav = sum(row["nav_cents"] for row in complete)
            cohorts.append({"source_id": snapshot["source_id"], "asof_date": snapshot["asof_date"], "vintage": vintage,
                "row_count": len(rows), "complete_multiple_row_count": len(complete),
                "contributions_cents": paid, "distributions_cents": distributions, "nav_cents": nav,
                "tvpi": (distributions + nav) / paid if paid else None,
                "scope": "Complete rows in captured subset; dollar-weighted, not pension portfolio return"})
    return {"status": "AVAILABLE_PARTIAL", "records": records, "snapshots": provenance,
            "provenance": provenance, "cohort_metrics": cohorts, "limitations": list(LIMITATIONS)}


def parse_amount(text: str, *, scale: int = 1) -> int | None:
    """Convert observed decimal dollars to exact cents; preserve missing markers."""
    cleaned = text.strip().replace("\xa0", " ")
    if cleaned.upper() in {"", "-", "—", "N/A", "N/M", "NA"}:
        return None
    cleaned = cleaned.replace("$", "").replace(",", "").strip()
    try:
        amount = Decimal(cleaned) * Decimal(scale) * 100
    except InvalidOperation as exc:
        raise ValueError(f"Invalid amount: {text!r}") from exc
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value() or scale <= 0:
        raise ValueError(f"Invalid exact nonnegative cents: {text!r}")
    return int(amount)


class _FundTableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.rows, self.row, self.cell, self.text = [], None, None, None, []
    def handle_starttag(self, tag, attrs):
        if tag == "table":
            if self.rows is not None:
                raise ValueError("Nested source tables are not supported")
            self.rows = []
        elif tag == "tr" and self.rows is not None:
            self.row = []
        elif tag in {"th", "td"} and self.row is not None:
            self.cell = []
    def handle_data(self, data):
        self.text.append(data)
        if self.cell is not None:
            self.cell.append(data)
    def handle_endtag(self, tag):
        if tag in {"th", "td"} and self.cell is not None:
            self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        elif tag == "table" and self.rows is not None:
            self.tables.append(self.rows)
            self.rows = None


def parse_fund_summary_html(html: str, *, amount_scale: int = 1) -> dict:
    """Parse recognized fund-summary headings; fail closed on layout changes.

    Scale must be selected from the documented source unit by the caller; it
    is never inferred from the magnitudes of the numbers.
    """
    parser = _FundTableParser()
    parser.feed(html)
    dates = set(re.findall(r"As\s+of\s+([A-Za-z]+\s+\d{1,2},\s+\d{4})", " ".join(parser.text), re.I))
    if len(dates) != 1:
        raise ValueError("A single explicit as-of heading is required")
    asof_date = datetime.strptime(next(iter(dates)), "%B %d, %Y").date().isoformat()
    aliases = {
        "fund": "fund_name", "fundname": "fund_name", "description": "fund_name",
        "vy": "vintage", "vintage": "vintage", "vintageyear": "vintage",
        "capitalcommitted": "commitment_cents", "commitment": "commitment_cents",
        "capitalcontributed": "contributions_cents", "cashin": "contributions_cents",
        "capitaldistributed": "distributions_cents", "cashout": "distributions_cents",
        "marketvalue": "nav_cents", "remainingvalue": "nav_cents", "nav": "nav_cents",
        "netmultiple": "reported_multiple", "investmentmultiple": "reported_multiple",
        "netirr": "reported_irr", "calstrssinceinceptionirr": "reported_irr",
    }
    candidates = []
    for table in parser.tables:
        if not table:
            continue
        headings = [aliases.get(re.sub(r"[^a-z]", "", value.lower())) for value in table[0]]
        if {"fund_name", "vintage", *AMOUNT_FIELDS}.issubset(set(headings)):
            candidates.append((table, headings))
    if len(candidates) != 1:
        raise ValueError("Exactly one recognized fund summary table is required")
    table, headings = candidates[0]
    if any(item is None for item in headings):
        raise ValueError("Unrecognized column in fund-summary table")
    if len(set(item for item in headings if item is not None)) != len([item for item in headings if item is not None]):
        raise ValueError("Duplicate recognized column")
    records = []
    for row_index, cells in enumerate(table[1:], start=2):
        if len(cells) != len(headings):
            raise ValueError("Fund summary row has changed column count")
        record = {"source_row": f"HTML table row {row_index}"}
        for key, text in zip(headings, cells):
            if key is None:
                continue
            if key == "fund_name":
                record[key] = text
            elif key == "vintage":
                try:
                    record[key] = int(text)
                except ValueError as exc:
                    raise ValueError("Invalid vintage") from exc
            elif key in AMOUNT_FIELDS:
                record[key] = parse_amount(text, scale=amount_scale)
            else:
                stripped = text.strip().replace("%", "")
                if stripped.upper() in {"", "-", "—", "N/A", "N/M"}:
                    record[key] = None
                else:
                    if stripped.startswith("(") and stripped.endswith(")"):
                        stripped = "-" + stripped[1:-1]
                    value = float(Decimal(stripped))
                    record[key] = value / 100 if key == "reported_irr" else value
        records.append(validate_record(record))
    if not records:
        raise ValueError("No fund observations in recognized table")
    return {"asof_date": asof_date, "records": records}
