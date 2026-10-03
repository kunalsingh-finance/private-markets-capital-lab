"""CSV -> point-in-time LP analytics -> SQLite evidence and offline report."""

import csv
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from .analytics import ks_pme, metrics, money, subscription_line_example, xirr
from .report import render_report
from .return_diagnostics import root_diagnostics, benchmark_adjusted_return


CONTRACTS = {
    "funds.csv": {"fund_id", "name", "vintage", "strategy", "commitment_usd"},
    "cashflows.csv": {"flow_id", "fund_id", "effective_date", "recorded_date", "kind", "amount_usd"},
    "valuations.csv": {"valuation_id", "fund_id", "asof_date", "published_date", "nav_usd"},
    "benchmark.csv": {"date", "total_return_level"},
}


def load_inputs(data_dir: Path) -> tuple[dict, list]:
    tables, provenance = {}, []
    for name, expected in CONTRACTS.items():
        path = data_dir / name
        raw = path.read_bytes()
        reader = csv.DictReader(raw.decode("utf-8-sig").splitlines())
        if reader.fieldnames is None or len(reader.fieldnames) != len(set(reader.fieldnames)) or set(reader.fieldnames) != expected:
            raise ValueError(f"{name}: incorrect or duplicate headers")
        records = list(reader)
        if not records:
            raise ValueError(f"{name}: empty input")
        for line, row in enumerate(records, 2):
            if any(key is None or value is None or not str(value).strip() for key, value in row.items()):
                raise ValueError(f"{name}:{line}: missing field or extra column")
        tables[name] = records
        provenance.append({"file": name, "sha256": hashlib.sha256(raw).hexdigest(), "row_count": len(records)})
    return tables, provenance


def _unique(rows, key, label):
    values = [row[key] for row in rows]
    if len(values) != len(set(values)):
        raise ValueError(f"{label}: duplicate {key}")


def analyze(data_dir: Path, asof: date, known_at: date) -> tuple[dict, dict]:
    if type(asof) is not date or type(known_at) is not date:
        raise ValueError("Reporting cutoffs must be dates")
    tables, provenance = load_inputs(data_dir)
    funds, raw_flows, raw_nav, raw_benchmark = (tables[name] for name in CONTRACTS)
    _unique(funds, "fund_id", "funds")
    _unique(raw_flows, "flow_id", "cashflows")
    _unique(raw_nav, "valuation_id", "valuations")
    fund_ids = {row["fund_id"] for row in funds}
    for row in funds:
        row["commitment_cents"] = money(row["commitment_usd"])
        row["vintage"] = int(row["vintage"])
        if not 1900 <= row["vintage"] <= asof.year:
            raise ValueError(f"{row['fund_id']}: invalid vintage")
    for row in raw_flows:
        row["date"] = date.fromisoformat(row["effective_date"])
        row["recorded"] = date.fromisoformat(row["recorded_date"])
        row["amount_cents"] = money(row["amount_usd"])
        if row["fund_id"] not in fund_ids or row["kind"] not in {"CALL", "DISTRIBUTION"} or row["amount_cents"] <= 0:
            raise ValueError(f"{row['flow_id']}: invalid fund, kind or amount")
        if row["recorded"] < row["date"]:
            raise ValueError(f"{row['flow_id']}: recorded date precedes effective date")
    nav_keys = set()
    for row in raw_nav:
        row["date"] = date.fromisoformat(row["asof_date"])
        row["published"] = date.fromisoformat(row["published_date"])
        row["nav_cents"] = money(row["nav_usd"])
        key = (row["fund_id"], row["date"], row["published"])
        if row["fund_id"] not in fund_ids or key in nav_keys or row["published"] < row["date"]:
            raise ValueError(f"{row['valuation_id']}: invalid fund, ambiguous valuation version or publication date")
        nav_keys.add(key)
    benchmark = [(date.fromisoformat(row["date"]), float(row["total_return_level"])) for row in raw_benchmark]
    # Validate the benchmark contract even when no selected fund has cash flows.
    ks_pme([], 0, asof, benchmark)
    flows = [row for row in raw_flows if row["date"] <= asof and row["recorded"] <= known_at]
    valuations = [row for row in raw_nav if row["date"] <= asof and row["published"] <= known_at]
    results, controls = [], []
    for fund in funds:
        selected = [row for row in flows if row["fund_id"] == fund["fund_id"]]
        available = [row for row in valuations if row["fund_id"] == fund["fund_id"]]
        valuation = max(available, key=lambda row: (row["date"], row["published"])) if available else None
        local = []

        def flag(code, message, severity="MEDIUM"):
            local.append({"code": code, "message": message, "severity": severity, "fund_id": fund["fund_id"]})

        nav = valuation["nav_cents"] if valuation and valuation["date"] == asof else None
        if valuation is None:
            flag("NO_VALUATION", "No valuation was available at this knowledge cutoff; terminal performance withheld.", "HIGH")
        elif nav is None:
            flag("STALE_VALUATION", f"Latest available NAV is dated {valuation['asof_date']}; exact-asof performance withheld.", "HIGH")
        paid = sum(row["amount_cents"] for row in selected if row["kind"] == "CALL")
        distributed = sum(row["amount_cents"] for row in selected if row["kind"] == "DISTRIBUTION")
        remaining = fund["commitment_cents"] - paid
        if remaining < 0:
            flag("OVER_COMMITMENT", "Paid-in capital exceeds commitment under the demo's no-recycling convention.", "HIGH")
        signed = [(row["date"], -row["amount_cents"] if row["kind"] == "CALL" else row["amount_cents"]) for row in selected]
        if nav is not None:
            irr = xirr(signed + [(asof, nav)])
            ratios = metrics(paid, distributed, nav)
            pme = ks_pme(selected, nav, asof, benchmark)
            if irr["status"] != "OK":
                flag(f"XIRR_{irr['status']}", "Dated IRR is unavailable under the documented bounded conventional-flow solver.")
            if pme is None:
                flag("PME_UNAVAILABLE", "PME lacks sufficient timely benchmark observations or positive calls.")
        else:
            irr = {"value": None, "status": "UNAVAILABLE", "residual_cents": None}
            ratios = {"dpi": distributed / paid if paid else None, "rvpi": None, "tvpi": None}
            pme = None
        results.append({
            "fund_id": fund["fund_id"], "name": fund["name"], "vintage": fund["vintage"], "strategy": fund["strategy"],
            "commitment_cents": fund["commitment_cents"], "paid_in_cents": paid,
            "distributed_cents": distributed, "nav_cents": nav, "unfunded_cents": remaining,
            **ratios, "xirr": irr, "ks_pme": pme,
            "valuation": {key: valuation[key] for key in ("asof_date", "published_date", "valuation_id")} if valuation else None,
            "controls": local,
            "return_diagnostics": root_diagnostics(signed + [(asof, nav)]) if nav is not None else None,
            "benchmark_adjusted_return": benchmark_adjusted_return(selected, nav, asof, benchmark) if nav is not None else None,
        })
        controls.extend(local)
    payload = {
        "asof": asof.isoformat(), "known_at": known_at.isoformat(), "data_kind": "SYNTHETIC",
        "status": "REVIEW_REQUIRED" if controls else "READY", "funds": results, "controls": controls,
        "subscription_line": subscription_line_example(), "provenance": provenance,
        "excluded_records": {"cashflows": len(raw_flows) - len(flows), "valuations": len(raw_nav) - len(valuations)},
    }
    return payload, {"funds": funds, "cashflows": flows, "valuations": valuations}


SCHEMA = """
CREATE TABLE funds (fund_id TEXT PRIMARY KEY, name TEXT NOT NULL, vintage INTEGER NOT NULL, strategy TEXT NOT NULL, commitment_cents INTEGER NOT NULL);
CREATE TABLE cashflows (flow_id TEXT PRIMARY KEY, fund_id TEXT REFERENCES funds, effective_date TEXT NOT NULL, recorded_date TEXT NOT NULL, kind TEXT NOT NULL, amount_cents INTEGER NOT NULL);
CREATE TABLE valuations (valuation_id TEXT PRIMARY KEY, fund_id TEXT REFERENCES funds, asof_date TEXT NOT NULL, published_date TEXT NOT NULL, nav_cents INTEGER NOT NULL);
CREATE TABLE provenance (file TEXT PRIMARY KEY, sha256 TEXT NOT NULL, row_count INTEGER NOT NULL);
CREATE TABLE controls (fund_id TEXT, severity TEXT, code TEXT, message TEXT);
CREATE VIEW fund_cash_summary AS SELECT fund_id, SUM(CASE WHEN kind='CALL' THEN amount_cents ELSE 0 END) paid_in_cents, SUM(CASE WHEN kind='DISTRIBUTION' THEN amount_cents ELSE 0 END) distributed_cents FROM cashflows GROUP BY fund_id;
CREATE TABLE reporting_context (run_id TEXT PRIMARY KEY, asof_date TEXT NOT NULL, known_at TEXT NOT NULL, data_kind TEXT NOT NULL, status TEXT NOT NULL);
CREATE TABLE performance_metrics (fund_id TEXT PRIMARY KEY REFERENCES funds, paid_in_cents INTEGER, distributed_cents INTEGER, nav_cents INTEGER, unfunded_cents INTEGER, dpi REAL, rvpi REAL, tvpi REAL, xirr REAL, xirr_status TEXT, ks_pme REAL, benchmark_adjusted_return REAL);
CREATE TABLE dim_investor (investor_id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL, commitment_cents INTEGER NOT NULL);
CREATE TABLE fact_capital_statement (investor_id TEXT PRIMARY KEY REFERENCES dim_investor, capital_cents INTEGER NOT NULL, paid_in_cents INTEGER, distributed_cents INTEGER, unfunded_cents INTEGER, recallable_cents INTEGER, fee_cents INTEGER, interest_cents INTEGER, gain_cents INTEGER, carry_net_cents INTEGER, realized_gain_cents INTEGER, unrealized_gain_cents INTEGER);
CREATE TABLE fact_accounting_event (event_id TEXT PRIMARY KEY, effective_date TEXT, kind TEXT, cash_cents INTEGER, investments_cents INTEGER, debt_cents INTEGER, accrued_interest_cents INTEGER, equity_cents INTEGER, source_json TEXT NOT NULL);
CREATE TABLE fact_waterfall_tier (scenario_id TEXT, tier_order INTEGER, tier TEXT, lp_cents INTEGER, gp_cents INTEGER, total_cents INTEGER, PRIMARY KEY(scenario_id,tier_order));
CREATE TABLE source_observation (observation_id INTEGER PRIMARY KEY, source_json TEXT NOT NULL);
CREATE VIEW investor_statement AS SELECT i.investor_id,i.name,i.role,i.commitment_cents,s.* FROM dim_investor i JOIN fact_capital_statement s USING(investor_id);
CREATE VIEW reporting_performance AS SELECT f.name,f.vintage,f.strategy,p.* FROM funds f JOIN performance_metrics p USING(fund_id);
"""


def write_warehouse(path: Path, tables: dict, payload: dict):
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO funds VALUES (?,?,?,?,?)", [(row["fund_id"], row["name"], row["vintage"], row["strategy"], row["commitment_cents"]) for row in tables["funds"]])
        conn.executemany("INSERT INTO cashflows VALUES (?,?,?,?,?,?)", [(row["flow_id"], row["fund_id"], row["effective_date"], row["recorded_date"], row["kind"], row["amount_cents"]) for row in tables["cashflows"]])
        conn.executemany("INSERT INTO valuations VALUES (?,?,?,?,?)", [(row["valuation_id"], row["fund_id"], row["asof_date"], row["published_date"], row["nav_cents"]) for row in tables["valuations"]])
        conn.executemany("INSERT INTO provenance VALUES (?,?,?)", [(row["file"], row["sha256"], row["row_count"]) for row in payload["provenance"]])
        conn.executemany("INSERT INTO controls VALUES (?,?,?,?)", [(row["fund_id"], row["severity"], row["code"], row["message"]) for row in payload["controls"]])
        sql = {row[0]: row[1:] for row in conn.execute("SELECT * FROM fund_cash_summary")}
        for fund in payload["funds"]:
            if sql.get(fund["fund_id"], (0, 0)) != (fund["paid_in_cents"], fund["distributed_cents"]):
                raise ValueError("SQL cash totals do not reconcile to Python")
        conn.execute("INSERT INTO reporting_context VALUES (?,?,?,?,?)", (payload["run_id"], payload["asof"], payload["known_at"], payload["data_kind"], payload["status"]))
        conn.executemany("INSERT INTO performance_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", [(row["fund_id"],row["paid_in_cents"],row["distributed_cents"],row["nav_cents"],row["unfunded_cents"],row["dpi"],row["rvpi"],row["tvpi"],row["xirr"]["value"],row["xirr"]["status"],row["ks_pme"],(row.get("benchmark_adjusted_return") or {}).get("value")) for row in payload["funds"]])
        from .advanced import write_advanced_warehouse
        write_advanced_warehouse(conn, payload.get("advanced", {}))


def _atomic_text(path: Path, content: str):
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(path)


def build(data_dir: Path, output_dir: Path, asof: date, known_at: date) -> dict:
    """Each successful attempt gets a separate evidence pack; failures block current UI."""
    output_dir.mkdir(parents=True, exist_ok=True)
    attempted_at = datetime.now(timezone.utc).isoformat()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    try:
        payload, tables = analyze(data_dir, asof, known_at)
        payload["run_id"], payload["built_at"] = run_id, attempted_at
        from .advanced import assemble_advanced, export_advanced
        payload["advanced"] = assemble_advanced(Path(__file__).resolve().parents[1], asof, known_at)
        if payload["advanced"]["capital"]["status"] == "FAILED":
            failed = payload["advanced"]["capital"].get("failed_event") or {}
            raise ValueError("Primary partnership accounting failed: " + failed.get("message", "economic event rejected"))
        payload["controls"].extend(payload["advanced"].get("controls", []))
        if payload["controls"]:
            payload["status"] = "REVIEW_REQUIRED"
        pack = output_dir / "runs" / run_id
        pack.mkdir(parents=True)
        write_warehouse(pack / "warehouse.sqlite", tables, payload)
        export_advanced(pack, payload["advanced"])
        for name, records in (("funds.csv", tables["funds"]), ("cashflows.csv", tables["cashflows"]), ("valuations.csv", tables["valuations"])):
            with (pack / name).open("w", newline="", encoding="utf-8") as stream:
                fields = sorted(CONTRACTS[name])
                writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(records)
        serialized = json.dumps(payload, indent=2, allow_nan=False)
        (pack / "analytics.json").write_text(serialized, encoding="utf-8")
        with (pack / "fund_metrics.csv").open("w", newline="", encoding="utf-8") as stream:
            columns = ["fund_id", "name", "vintage", "strategy", "paid_in_cents", "distributed_cents", "nav_cents", "unfunded_cents", "dpi", "rvpi", "tvpi", "xirr_rate", "xirr_status", "ks_pme", "benchmark_adjusted_rate", "asof", "known_at", "run_id"]
            writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
            writer.writeheader()
            writer.writerows({**row, "xirr_rate": row["xirr"]["value"], "xirr_status": row["xirr"]["status"], "benchmark_adjusted_rate": (row.get("benchmark_adjusted_return") or {}).get("value"), "asof": payload["asof"], "known_at": payload["known_at"], "run_id": run_id} for row in payload["funds"])
        html = render_report(payload)
        (pack / "report.html").write_text(html, encoding="utf-8")
        manifest = {"status": payload["status"], "attempted_at": attempted_at, "run_id": run_id,
                    "pack": f"runs/{run_id}", "asof": payload["asof"], "known_at": payload["known_at"],
                    "source_hashes": {row["file"]: row["sha256"] for row in payload["provenance"]},
                    "code_hashes": {str(path.relative_to(Path(__file__).resolve().parents[1])).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(Path(__file__).resolve().parent.glob("*.py"))},
                    "artifacts": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(pack.iterdir())}}
        _atomic_text(output_dir / "report.html", html)
        _atomic_text(output_dir / "run_status.json", json.dumps(manifest, indent=2))
        return payload
    except Exception as exc:
        # Earlier packs remain historical evidence, never validation of this attempt.
        from html import escape
        _atomic_text(output_dir / "report.html", f"<!doctype html><meta charset='utf-8'><title>Build failed</title><h1>FAILED — current report blocked</h1><p>{escape(str(exc))}</p><p>Earlier evidence packs do not validate this attempt.</p>")
        _atomic_text(output_dir / "run_status.json", json.dumps({"status": "FAILED", "attempted_at": attempted_at, "run_id": run_id, "pack": None, "artifacts": {}, "error": str(exc)}, indent=2))
        raise
