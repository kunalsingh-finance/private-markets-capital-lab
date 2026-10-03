"""Connect economic accounts, terminal distributions and public research."""

from copy import deepcopy
import csv
from datetime import date
import hashlib
import json
from pathlib import Path
from .analytics import metrics, xirr


def _investor_metrics(capital: dict):
    terminal = date.fromisoformat(capital["asof"])
    for investor in capital["investors"]:
        flows = []
        for row in capital["event_journal"]:
            delta = row["investor_allocations"][investor["investor_id"]]
            cash = delta.get("distributed_cents", 0) - delta.get("paid_in_cents", 0)
            if cash:
                flows.append((date.fromisoformat(row["effective_date"]), cash))
        nav = investor["capital_cents"]
        if nav >= 0 and capital["status"] != "FAILED":
            investor.update(metrics(investor["paid_in_cents"], investor["distributed_cents"], nav))
            investor["xirr"] = xirr(flows + [(terminal, nav)])
        else:
            investor.update({"dpi": None, "rvpi": None, "tvpi": None, "xirr": {"value": None, "status": "UNAVAILABLE", "residual_cents": None}})


def assemble_advanced(root: Path, asof: date, known_at: date) -> dict:
    from .capital import run_capital_case, load_capital_case
    from .waterfall import european_waterfall, run_waterfall_demo
    from .public_data import public_research_summary

    case = load_capital_case("base")
    opening = run_capital_case(case, asof=asof, known_at=known_at)
    result = {"capital_before_distribution": opening, "waterfall_demo": run_waterfall_demo(),
              "public_research": public_research_summary(root), "controls": [], "linked_exit": None}
    balances = opening["balances"]
    fully_exited = opening["status"] != "FAILED" and known_at >= asof and all(balances[key] == 0 for key in ("investments_cents", "investment_cost_cents", "debt_cents", "accrued_interest_cents"))
    if fully_exited and balances["cash_cents"] > 0:
        calls = [(date.fromisoformat(row["effective_date"]), row["amount_cents"]) for row in case["events"] if row["kind"] == "CALL" and date.fromisoformat(row["effective_date"]) <= asof and date.fromisoformat(row["recorded_date"]) <= known_at]
        if any(row["distributed_cents"] != 0 for row in opening["investors"]):
            raise ValueError("Linked terminal waterfall requires no prior investor distributions")
        terms = european_waterfall(calls, balances["cash_cents"], asof)
        gp = [row["investor_id"] for row in case["investors"] if row["role"] == "GP"]
        if len(gp) != 1:
            raise ValueError("Linked case requires exactly one carry recipient")
        promoted = deepcopy(case)
        if terms["gp_total_cents"]:
            promoted["events"].append({"event_id": "TERMINAL_CARRY", "effective_date": asof.isoformat(), "recorded_date": known_at.isoformat(), "kind": "CARRY_ALLOCATION", "amount_cents": terms["gp_total_cents"], "recipient_id": gp[0]})
        post_carry = run_capital_case(promoted, asof=asof, known_at=known_at)
        if post_carry["status"] == "FAILED":
            raise ValueError("Carry allocation failed in the linked case")
        distribution = {row["investor_id"]: row["capital_cents"] for row in post_carry["investors"]}
        if min(distribution.values()) < 0 or sum(distribution.values()) != balances["cash_cents"]:
            raise ValueError("Terminal allocation does not reconcile to available cash")
        promoted["events"].append({"event_id": "TERMINAL_DISTRIBUTION", "effective_date": asof.isoformat(), "recorded_date": known_at.isoformat(), "kind": "DISTRIBUTION", "amount_cents": balances["cash_cents"], "investor_allocations": distribution})
        closed = run_capital_case(promoted, asof=asof, known_at=known_at)
        if closed["status"] == "FAILED" or any(row["capital_cents"] != 0 for row in closed["investors"]):
            raise ValueError("Terminal distribution did not close every investor account")
        result["capital"] = closed
        result["linked_exit"] = {"status": "CLOSED", "waterfall": terms, "distribution_allocations": distribution,
                                 "carry_recipient": gp[0], "proceeds_cents": balances["cash_cents"],
                                 "note": "All contributors, including GP co-investment, share capital and preferred proceeds; GP additionally receives the modeled carry. Whole-fund terminal realization with no earlier distributions."}
    else:
        result["capital"] = opening
        result["linked_exit"] = {"status": "NOT_TERMINALLY_LIQUIDATED", "note": "Terminal distribution requires zero investment, debt and interest balances and a complete known event history. No sale or NAV cash receipt has been invented."}
    _investor_metrics(result["capital"])
    for item in result["capital"].get("controls", []):
        result["controls"].append({"fund_id": "PARTNERSHIP", "severity": item.get("severity", "HIGH"), "code": item.get("code", "CAPITAL_CONTROL"), "message": item.get("message", str(item))})
    result["capital_scenarios"] = []
    for name in ("recallable", "cash_shortfall", "delayed_distribution"):
        try:
            scenario = load_capital_case(name)
        except FileNotFoundError:
            continue
        result["capital_scenarios"].append({"name": name, "result": run_capital_case(scenario)})
    result["provenance"] = [{"file": str(path.relative_to(root)).replace("\\", "/"), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size} for path in sorted((root / "data" / "advanced").glob("*.json"))]
    result["public_research_context"] = "Separate current-source research population; public observations are not filtered or backdated to the synthetic report's knowledge cutoff. Consult each snapshot's measurement and retrieval dates."
    return result


def _csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def export_advanced(pack: Path, result: dict):
    capital = result["capital"]
    fields = ["investor_id", "name", "role", "commitment_cents", "paid_in_cents", "distributed_cents", "capital_cents", "unfunded_cents", "recallable_cents", "gain_cents", "realized_gain_cents", "unrealized_gain_cents", "fee_cents", "interest_cents", "carry_net_cents", "dpi", "rvpi", "tvpi", "xirr_rate", "xirr_status"]
    _csv(pack / "investor_statements.csv", [{**row, "xirr_rate": row["xirr"]["value"], "xirr_status": row["xirr"]["status"]} for row in capital["investors"]], fields)
    _csv(pack / "dim_investor.csv", capital["investors"], ["investor_id", "name", "role", "commitment_cents"])
    (pack / "partnership_accounting.json").write_text(json.dumps(capital, indent=2, allow_nan=False), encoding="utf-8")
    rows = []
    for journal in capital["event_journal"]:
        rows.append({"event_id": journal["event_id"], "effective_date": journal["effective_date"], "kind": journal["kind"], **journal["balances_after"]})
    _csv(pack / "accounting_journal.csv", rows, ["event_id", "effective_date", "kind", "cash_cents", "investments_cents", "debt_cents", "accrued_interest_cents", "equity_cents"])
    tiers = []
    for scenario in result["waterfall_demo"]["scenarios"]:
        for order, tier in enumerate(scenario["result"]["tiers"], 1):
            tiers.append({"scenario_id": scenario["scenario_id"], "tier_order": order, **tier})
    _csv(pack / "waterfall_scenarios.csv", tiers, ["scenario_id", "tier_order", "name", "lp_cents", "gp_cents", "total_cents"])
    (pack / "public_research.json").write_text(json.dumps(result["public_research"], indent=2, allow_nan=False), encoding="utf-8")


def write_advanced_warehouse(conn, result: dict):
    capital = result.get("capital")
    if not capital:
        return
    for row in capital["investors"]:
        conn.execute("INSERT INTO dim_investor VALUES (?,?,?,?)", (row["investor_id"], row["name"], row["role"], row["commitment_cents"]))
        keys = ["investor_id", "capital_cents", "paid_in_cents", "distributed_cents", "unfunded_cents", "recallable_cents", "fee_cents", "interest_cents", "gain_cents", "carry_net_cents", "realized_gain_cents", "unrealized_gain_cents"]
        conn.execute("INSERT INTO fact_capital_statement VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", tuple(row.get(key, 0) for key in keys))
    for row in capital["event_journal"]:
        balance = row["balances_after"]
        conn.execute("INSERT INTO fact_accounting_event VALUES (?,?,?,?,?,?,?,?,?)", (row["event_id"], row["effective_date"], row["kind"], balance["cash_cents"], balance["investments_cents"], balance["debt_cents"], balance["accrued_interest_cents"], balance["equity_cents"], json.dumps(row, allow_nan=False)))
    for scenario in result["waterfall_demo"]["scenarios"]:
        for order, tier in enumerate(scenario["result"]["tiers"], 1):
            conn.execute("INSERT INTO fact_waterfall_tier VALUES (?,?,?,?,?,?)", (scenario["scenario_id"], order, tier["name"], tier["lp_cents"], tier["gp_cents"], tier["total_cents"]))
    for row in result["public_research"].get("records", []):
        conn.execute("INSERT INTO source_observation(source_json) VALUES (?)", (json.dumps(row, allow_nan=False),))
    sql_equity = conn.execute("SELECT SUM(capital_cents) FROM fact_capital_statement").fetchone()[0]
    if sql_equity != capital["balances"]["equity_cents"]:
        raise ValueError("SQL investor accounts do not reconcile to fund equity")
