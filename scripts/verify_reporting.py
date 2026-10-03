"""Independently reconcile persisted investor bridges and waterfall tiers."""
from contextlib import closing
import json
from pathlib import Path
import sqlite3

ROOT = Path(__file__).resolve().parents[1]


def main():
    status = json.loads((ROOT / "output" / "run_status.json").read_text())
    if status["status"] == "FAILED":
        raise ValueError("Current failed attempt has no accepted reporting warehouse")
    pack = ROOT / "output" / status["pack"]
    payload = json.loads((pack / "analytics.json").read_text())
    capital = payload["advanced"]["capital"]
    with closing(sqlite3.connect(pack / "warehouse.sqlite")) as conn:
        fields = ["investor_id", "capital_cents", "paid_in_cents", "distributed_cents", "unfunded_cents", "recallable_cents", "fee_cents", "interest_cents", "gain_cents", "carry_net_cents", "realized_gain_cents", "unrealized_gain_cents"]
        saved_investors = sorted(conn.execute("SELECT " + ",".join(fields) + " FROM fact_capital_statement"))
        expected_investors = sorted(tuple(row[key] for key in fields) for row in capital["investors"])
        if saved_investors != expected_investors:
            raise ValueError("Persisted investor records differ from report evidence")
        event_fields = ["cash_cents", "investments_cents", "debt_cents", "accrued_interest_cents", "equity_cents"]
        saved_events = sorted(conn.execute("SELECT event_id,effective_date,kind," + ",".join(event_fields) + " FROM fact_accounting_event"))
        expected_events = sorted((row["event_id"], row["effective_date"], row["kind"], *(row["balances_after"][key] for key in event_fields)) for row in capital["event_journal"])
        if saved_events != expected_events:
            raise ValueError("Persisted accounting events differ from report evidence")
        saved_tiers = sorted(conn.execute("SELECT scenario_id,tier_order,tier,lp_cents,gp_cents,total_cents FROM fact_waterfall_tier"))
        expected_tiers = sorted((scenario["scenario_id"], order, tier["name"], tier["lp_cents"], tier["gp_cents"], tier["total_cents"]) for scenario in payload["advanced"]["waterfall_demo"]["scenarios"] for order, tier in enumerate(scenario["result"]["tiers"], 1))
        if saved_tiers != expected_tiers:
            raise ValueError("Persisted waterfall tiers differ from report evidence")
        investor = list(conn.execute("SELECT investor_id, capital_cents, paid_in_cents+gain_cents-fee_cents-interest_cents+carry_net_cents-distributed_cents FROM fact_capital_statement"))
        if any(capital != bridge for _, capital, bridge in investor):
            raise ValueError("Investor capital bridges differ")
        events = list(conn.execute("SELECT event_id,cash_cents+investments_cents-debt_cents-accrued_interest_cents-equity_cents FROM fact_accounting_event"))
        if any(difference != 0 for _, difference in events):
            raise ValueError("Event-level balance identity differs")
        tiers = list(conn.execute("SELECT scenario_id,SUM(total_cents)-SUM(lp_cents)-SUM(gp_cents) FROM fact_waterfall_tier GROUP BY scenario_id"))
        if any(difference != 0 for _, difference in tiers):
            raise ValueError("Waterfall cash conservation differs")
        combined = conn.execute("SELECT SUM(distributed_cents),SUM(capital_cents) FROM fact_capital_statement").fetchone()
    if combined != (capital["totals"]["distributed_cents"], capital["balances"]["equity_cents"]):
        raise ValueError("Persisted investor amounts do not reconcile to the report")
    print(f"Verified {len(investor)} investor bridges, {len(events)} event identities and {len(tiers)} waterfall scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
