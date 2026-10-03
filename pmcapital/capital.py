"""Exact-cent economic capital accounts for a fictional private partnership.

This is an economic book ledger, not a tax capital-account or legal LPA engine.
The separate comparison-fund analytics do not supply this ledger's balances.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date
import hashlib
import json
from pathlib import Path


CASE_DIR = Path(__file__).resolve().parents[1] / "data" / "advanced"
CASE_FILES = {
    "base": "northstar_base.json",
    "delayed_distribution": "northstar_delayed_distribution.json",
    "cash_shortfall": "northstar_cash_shortfall.json",
    "recallable": "northstar_recallable.json",
}
KINDS = {
    "CALL", "INVEST", "REALIZATION", "REVALUE", "DISTRIBUTION",
    "RECALLABLE_DISTRIBUTION", "FEE", "FACILITY_DRAW", "FACILITY_REPAY",
    "INTEREST", "INTEREST_PAYMENT", "CARRY_ALLOCATION",
}
ACCOUNT_FIELDS = (
    "capital_cents", "paid_in_cents", "distributed_cents", "recallable_cents",
    "fee_cents", "interest_cents", "gain_cents", "realized_gain_cents",
    "unrealized_gain_cents", "carry_net_cents", "carry_received_cents",
)


def _integer(value, label: str, *, signed: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or (not signed and value < 0):
        raise ValueError(f"{label} must be {'a signed' if signed else 'a nonnegative'} integer")
    if abs(value) > 2**63 - 1:
        raise ValueError(f"{label} exceeds the signed 64-bit range")
    return value


def _day(value, label: str) -> date:
    if type(value) is date:
        return value
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{label} must use YYYY-MM-DD")
    return parsed


def _round_half_up(numerator: int, denominator: int) -> int:
    quotient, remainder = divmod(numerator, denominator)
    return quotient + int(2 * remainder >= denominator)


def management_fee(commitment_cents: int, annual_bps: int, start: date, end: date) -> int:
    """Committed-capital fee for [start,end), ACT/365, rounded HALF_UP once."""
    commitment_cents = _integer(commitment_cents, "commitment_cents")
    annual_bps = _integer(annual_bps, "annual_bps")
    if type(start) is not date or type(end) is not date or end < start:
        raise ValueError("Fee dates must be dates with end on/after start")
    return _round_half_up(commitment_cents * annual_bps * (end - start).days, 10_000 * 365)


def allocate_cents(amount: int, weights: dict[str, int]) -> dict[str, int]:
    """Largest-remainder allocation; ties use investor ID, losses are symmetric.

    Zero weights receive no money. Input order does not affect the result.
    """
    amount = _integer(amount, "allocation amount", signed=True)
    if not isinstance(weights, dict) or not weights:
        raise ValueError("Allocation weights must be a nonempty mapping")
    for key, weight in weights.items():
        if not isinstance(key, str) or not key:
            raise ValueError("Allocation identifiers must be nonempty strings")
        _integer(weight, f"Weight for {key}")
    denominator = sum(weights.values())
    if denominator <= 0:
        raise ValueError("At least one allocation weight must be positive")
    sign = -1 if amount < 0 else 1
    absolute = abs(amount)
    parts = {key: divmod(absolute * weight, denominator) for key, weight in weights.items()}
    residual = absolute - sum(part[0] for part in parts.values())
    ranked = sorted(parts, key=lambda key: (-parts[key][1], key))
    winners = set(ranked[:residual])
    return {key: sign * (parts[key][0] + int(key in winners)) for key in sorted(parts)}


def load_capital_case(name: str = "base") -> dict:
    if name not in CASE_FILES:
        raise ValueError(f"Unknown capital case: {name}")
    return json.loads((CASE_DIR / CASE_FILES[name]).read_text(encoding="utf-8"))


class _EconomicGate(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _validate(case: dict) -> tuple[dict[str, dict], list[dict], dict[str, int]]:
    if not isinstance(case, dict) or not isinstance(case.get("case_id"), str) or not case["case_id"]:
        raise ValueError("Case requires a nonempty case_id")
    if not isinstance(case.get("name"), str) or not case["name"]:
        raise ValueError("Case requires a name")
    for key in ("facility_limit_cents", "facility_rate_bps", "management_fee_bps"):
        _integer(case.get(key, 0), key)
    rows = case.get("investors")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Case requires investors")
    investors, weights = {}, {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each investor must be an object")
        investor_id = row.get("investor_id")
        if not isinstance(investor_id, str) or not investor_id or investor_id in investors:
            raise ValueError("Investor IDs must be nonempty and unique")
        if not isinstance(row.get("role"), str) or row["role"] not in {"LP", "GP"} or not isinstance(row.get("name"), str) or not row["name"]:
            raise ValueError(f"{investor_id}: investor needs a name and LP/GP role")
        commitment = _integer(row.get("commitment_cents"), f"{investor_id} commitment")
        if commitment <= 0:
            raise ValueError("Every modeled investor commitment must be positive")
        investors[investor_id] = {
            "investor_id": investor_id, "name": row["name"], "role": row["role"],
            "commitment_cents": commitment, **{field: 0 for field in ACCOUNT_FIELDS},
        }
        weights[investor_id] = commitment
    events = case.get("events")
    if not isinstance(events, list):
        raise ValueError("Case requires an events array")
    event_ids, parsed = set(), []
    for index, source in enumerate(events):
        if not isinstance(source, dict):
            raise ValueError("Each event must be an object")
        event = deepcopy(source)
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not event_id or event_id in event_ids:
            raise ValueError("Event IDs must be nonempty and unique; replay is rejected")
        if event_id.startswith("ACCRUAL:"):
            raise ValueError("ACCRUAL: event IDs are reserved for generated journal entries")
        event_ids.add(event_id)
        kind = event.get("kind")
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError(f"{event_id}: unsupported kind {kind!r}")
        event["amount_cents"] = _integer(event.get("amount_cents"), f"{event_id} amount_cents")
        event["_effective"] = _day(event.get("effective_date"), f"{event_id} effective_date")
        event["_recorded"] = _day(event.get("recorded_date"), f"{event_id} recorded_date")
        event["effective_date"] = event["_effective"].isoformat()
        event["recorded_date"] = event["_recorded"].isoformat()
        if event["_recorded"] < event["_effective"]:
            raise ValueError(f"{event_id}: recorded date precedes effective date")
        if kind == "REALIZATION":
            _integer(event.get("cost_cents"), f"{event_id} cost_cents")
            if "historical_cost_cents" in event:
                _integer(event["historical_cost_cents"], f"{event_id} historical_cost_cents")
        if kind == "REVALUE":
            _integer(event.get("delta_cents"), f"{event_id} delta_cents", signed=True)
            if event["amount_cents"] != 0:
                raise ValueError(f"{event_id}: REVALUE amount_cents must be zero; use delta_cents")
        if kind == "FEE":
            period_keys = [key in event for key in ("period_start", "period_end")]
            if any(period_keys) and not all(period_keys):
                raise ValueError(f"{event_id}: fee period requires both dates")
            if all(period_keys):
                start = _day(event["period_start"], f"{event_id} period_start")
                end = _day(event["period_end"], f"{event_id} period_end")
                event["period_start"], event["period_end"] = start.isoformat(), end.isoformat()
                bps = _integer(event.get("annual_bps", case.get("management_fee_bps", 0)), f"{event_id} annual_bps")
                computed = management_fee(sum(weights.values()), bps, start, end)
                if end > event["_effective"] or computed != event["amount_cents"]:
                    raise ValueError(f"{event_id}: fee period or exact rate-derived amount is inconsistent")
                event["_fee_bps"] = bps
        if kind == "CARRY_ALLOCATION":
            recipient = event.get("recipient_id")
            if not isinstance(recipient, str) or recipient not in investors or investors[recipient]["role"] != "GP":
                raise ValueError(f"{event_id}: carry recipient must be a GP investor")
        if "investor_allocations" in event:
            if kind not in {"CALL", "DISTRIBUTION", "RECALLABLE_DISTRIBUTION"}:
                raise ValueError(f"{event_id}: explicit cash allocations unsupported for {kind}")
            explicit = event["investor_allocations"]
            if not isinstance(explicit, dict) or set(explicit) - set(investors):
                raise ValueError(f"{event_id}: allocation contains unknown investors")
            for investor_id, value in explicit.items():
                _integer(value, f"{event_id}/{investor_id} allocation")
            if sum(explicit.values()) != event["amount_cents"]:
                raise ValueError(f"{event_id}: explicit allocations must equal the cash amount exactly")
        event["_input_order"] = index
        parsed.append(event)
    return investors, sorted(parsed, key=lambda row: (row["_effective"], row["_input_order"])), weights


def _snapshot(balances: dict, investors: dict) -> dict:
    nav = balances["cash_cents"] + balances["investments_cents"] - balances["debt_cents"] - balances["accrued_interest_cents"]
    capital = sum(row["capital_cents"] for row in investors.values())
    return {**balances, "net_asset_value_cents": nav, "equity_cents": nav, "investor_capital_cents": capital,
            "reconciliation_difference_cents": nav - capital}


def _check(balances: dict, investors: dict, facility_limit: int):
    codes = {"cash_cents": "CASH_SHORTFALL", "investments_cents": "NEGATIVE_INVESTMENT_BOOK",
             "investment_cost_cents": "NEGATIVE_INVESTMENT_COST",
             "debt_cents": "DEBT_OVERPAYMENT", "accrued_interest_cents": "INTEREST_OVERPAYMENT"}
    for field, code in codes.items():
        if balances[field] < 0:
            raise _EconomicGate(code, f"{field} would be negative by {-balances[field]} cents")
    if balances["debt_cents"] > facility_limit:
        raise _EconomicGate("FACILITY_LIMIT", "Outstanding debt would exceed the fixed facility limit")
    for investor_id, row in investors.items():
        if row["paid_in_cents"] > row["commitment_cents"] + row["recallable_cents"]:
            raise _EconomicGate("OVER_COMMITMENT", f"{investor_id}: call exceeds original commitment plus recallable distributions")
        expected = row["paid_in_cents"] + row["gain_cents"] - row["fee_cents"] - row["interest_cents"] - row["distributed_cents"] + row["carry_net_cents"]
        if row["capital_cents"] != expected:
            raise AssertionError(f"{investor_id}: capital account bridge does not reconcile")
        if row["gain_cents"] != row["realized_gain_cents"] + row["unrealized_gain_cents"]:
            raise AssertionError(f"{investor_id}: realized/unrealized classification does not reconcile")
    if sum(row["unrealized_gain_cents"] for row in investors.values()) != balances["investments_cents"] - balances["investment_cost_cents"]:
        raise AssertionError("Remaining unrealized gains do not reconcile to investment book less historical cost")
    if _snapshot(balances, investors)["reconciliation_difference_cents"]:
        raise AssertionError("Economic assets less liabilities do not reconcile to investor capital")


def _cash_allocations(event: dict, weights: dict) -> dict:
    if "investor_allocations" in event:
        return {key: event["investor_allocations"].get(key, 0) for key in sorted(weights)}
    return allocate_cents(event["amount_cents"], weights)


def _apply(balances: dict, investors: dict, event: dict, weights: dict) -> dict:
    kind, amount = event["kind"], event["amount_cents"]
    deltas = {key: {field: 0 for field in ACCOUNT_FIELDS} for key in investors}

    def allocate(field: str, value: int, capital_sign: int = 0):
        parts = allocate_cents(value, weights)
        for key, allocated in parts.items():
            investors[key][field] += allocated
            deltas[key][field] += allocated
            if capital_sign:
                change = capital_sign * allocated
                investors[key]["capital_cents"] += change
                deltas[key]["capital_cents"] += change

    if kind == "CALL":
        balances["cash_cents"] += amount
        for key, value in _cash_allocations(event, weights).items():
            for field in ("capital_cents", "paid_in_cents"):
                investors[key][field] += value
                deltas[key][field] += value
    elif kind == "INVEST":
        balances["cash_cents"] -= amount
        balances["investments_cents"] += amount
        balances["investment_cost_cents"] += amount
    elif kind == "REALIZATION":
        cost, gain = event["cost_cents"], amount - event["cost_cents"]
        if "historical_cost_cents" not in event and balances["investments_cents"] != balances["investment_cost_cents"]:
            raise _EconomicGate("MISSING_HISTORICAL_COST", "Marked investments require the disposed historical_cost_cents for realized/unrealized classification")
        historical_cost = event.get("historical_cost_cents", cost)
        balances["cash_cents"] += amount
        balances["investments_cents"] -= cost
        balances["investment_cost_cents"] -= historical_cost
        allocate("gain_cents", gain, 1)
        # Reclassification never changes total gain or NAV. Full pool disposal
        # unwinds the actual accumulated investor marks, including penny ties.
        full_exit = balances["investments_cents"] == 0 and balances["investment_cost_cents"] == 0
        reversal = ({key: -row["unrealized_gain_cents"] for key, row in investors.items()}
                    if full_exit else allocate_cents(historical_cost - cost, weights))
        for key, unrealized_change in reversal.items():
            realized_change = deltas[key]["gain_cents"] - unrealized_change
            investors[key]["unrealized_gain_cents"] += unrealized_change
            investors[key]["realized_gain_cents"] += realized_change
            deltas[key]["unrealized_gain_cents"] += unrealized_change
            deltas[key]["realized_gain_cents"] += realized_change
    elif kind == "REVALUE":
        delta = event["delta_cents"]
        balances["investments_cents"] += delta
        allocate("gain_cents", delta, 1)
        allocate("unrealized_gain_cents", delta)
    elif kind in {"DISTRIBUTION", "RECALLABLE_DISTRIBUTION"}:
        balances["cash_cents"] -= amount
        for key, value in _cash_allocations(event, weights).items():
            investors[key]["capital_cents"] -= value
            investors[key]["distributed_cents"] += value
            deltas[key]["capital_cents"] -= value
            deltas[key]["distributed_cents"] += value
            if kind == "RECALLABLE_DISTRIBUTION":
                investors[key]["recallable_cents"] += value
                deltas[key]["recallable_cents"] += value
    elif kind in {"FEE", "INTEREST", "INTEREST_ACCRUAL"}:
        field = "fee_cents" if kind == "FEE" else "interest_cents"
        if kind == "INTEREST_ACCRUAL":
            balances["accrued_interest_cents"] += amount
        else:
            balances["cash_cents"] -= amount
        allocate(field, amount, -1)
    elif kind == "FACILITY_DRAW":
        balances["cash_cents"] += amount
        balances["debt_cents"] += amount
    elif kind == "FACILITY_REPAY":
        balances["cash_cents"] -= amount
        balances["debt_cents"] -= amount
    elif kind == "INTEREST_PAYMENT":
        balances["cash_cents"] -= amount
        balances["accrued_interest_cents"] -= amount
    elif kind == "CARRY_ALLOCATION":
        allocate("carry_net_cents", -amount, 1)
        key = event["recipient_id"]
        investors[key]["capital_cents"] += amount
        investors[key]["carry_net_cents"] += amount
        investors[key]["carry_received_cents"] += amount
        deltas[key]["capital_cents"] += amount
        deltas[key]["carry_net_cents"] += amount
        deltas[key]["carry_received_cents"] += amount
    else:
        raise AssertionError(f"Unhandled economic kind {kind}")
    return deltas


def run_capital_case(case: dict | None = None, asof: date | None = None, known_at: date | None = None) -> dict:
    """Replay only eligible events, preserving a failed economic attempt as evidence.

    Malformed source contracts raise ValueError. Economic gate failures return
    FAILED with last-valid balances, a failed_event and an unreleased journal.
    Same-day source events retain their input order. Each accrual interval is
    rounded once, before the next event and at the final measurement date.
    """
    case = load_capital_case() if case is None else deepcopy(case)
    investors, events, weights = _validate(case)
    asof = _day(case.get("asof", "2026-06-30"), "asof") if asof is None else asof
    known_at = _day(case.get("known_at", "2026-08-15"), "known_at") if known_at is None else known_at
    if type(asof) is not date or type(known_at) is not date:
        raise ValueError("Reporting cutoffs must be date objects")
    selected = [event for event in events if event["_effective"] <= asof and event["_recorded"] <= known_at]
    excluded = [{"event_id": event["event_id"], "effective_date": event["_effective"].isoformat(),
                 "recorded_date": event["_recorded"].isoformat(),
                 "reason": "AFTER_ASOF" if event["_effective"] > asof else "NOT_KNOWN_AT"}
                for event in events if event not in selected]
    balances = {key: 0 for key in ("cash_cents", "investments_cents", "investment_cost_cents", "debt_cents", "accrued_interest_cents")}
    journal, controls = [], []
    rate, limit = case.get("facility_rate_bps", 0), case.get("facility_limit_cents", 0)
    previous = selected[0]["_effective"] if selected else asof
    status, failed_event, effective_through = "READY", None, None

    def post(event: dict):
        nonlocal balances, investors, effective_through
        before = _snapshot(balances, investors)
        candidate_balances, candidate_investors = deepcopy(balances), deepcopy(investors)
        allocations = _apply(candidate_balances, candidate_investors, event, weights)
        _check(candidate_balances, candidate_investors, limit)
        balances, investors = candidate_balances, candidate_investors
        effective_through = event["_effective"].isoformat()
        metadata = {key: event[key] for key in ("cost_cents", "historical_cost_cents", "delta_cents", "period_start", "period_end", "annual_bps", "recipient_id", "accrual_days", "rate_bps") if key in event}
        journal.append({
            "journal_index": len(journal) + 1, "event_id": event["event_id"],
            "source_event_id": event.get("source_event_id", event["event_id"]),
            "effective_date": event["_effective"].isoformat(), "recorded_date": event["_recorded"].isoformat(),
            "kind": event["kind"], "amount_cents": event["amount_cents"], "metadata": metadata,
            "balances_before": before, "balances_after": _snapshot(balances, investors),
            "investor_allocations": allocations,
            "investor_capital_after": {key: row["capital_cents"] for key, row in sorted(investors.items())},
        })

    def accrue(until: date, source_event_id: str):
        nonlocal previous
        days = (until - previous).days
        if days < 0:
            raise AssertionError("Selected events are not chronological")
        amount = _round_half_up(balances["debt_cents"] * rate * days, 10_000 * 365)
        if amount:
            event = {"event_id": f"ACCRUAL:{source_event_id}", "source_event_id": source_event_id,
                     "_effective": until, "_recorded": known_at, "kind": "INTEREST_ACCRUAL",
                     "amount_cents": amount, "period_start": previous.isoformat(), "period_end": until.isoformat(),
                     "accrual_days": days, "rate_bps": rate}
            post(event)
        previous = until

    for event in selected:
        try:
            accrue(event["_effective"], event["event_id"])
            post(event)
        except _EconomicGate as exc:
            status = "FAILED"
            failed_event = {"event_id": event["event_id"], "effective_date": event["_effective"].isoformat(),
                            "kind": event["kind"], "amount_cents": event["amount_cents"],
                            "code": exc.code, "message": str(exc)}
            controls.append({"severity": "HIGH", "code": exc.code, "event_id": event["event_id"], "message": str(exc)})
            break
    if status != "FAILED":
        accrue(asof, "ASOF")
        effective_through = asof.isoformat()
        if any(row["capital_cents"] < 0 for row in investors.values()):
            status = "REVIEW_REQUIRED"
            controls.append({"severity": "MEDIUM", "code": "SIGNED_CAPITAL_DEFICIT",
                             "message": "At least one economic capital account is negative; no balance was clipped or hidden."})
    if excluded:
        controls.append({"severity": "INFO", "code": "EVENTS_OUTSIDE_CUTOFF",
                         "message": f"{len(excluded)} source events withheld by economic or knowledge cutoff."})
    _check(balances, investors, limit)
    totals = {field: sum(row[field] for row in investors.values()) for field in ACCOUNT_FIELDS}
    investor_output = []
    for key, row in sorted(investors.items()):
        investor_output.append({**row, "unfunded_cents": row["commitment_cents"] + row["recallable_cents"] - row["paid_in_cents"]})
    nav = _snapshot(balances, investors)
    bridge = {
        "opening_nav_cents": 0, "capital_contributed_cents": totals["paid_in_cents"],
        "realized_gain_cents": totals["realized_gain_cents"], "unrealized_gain_cents": totals["unrealized_gain_cents"],
        "fees_cents": totals["fee_cents"], "interest_expense_cents": totals["interest_cents"],
        "distributions_cents": totals["distributed_cents"], "closing_nav_cents": nav["net_asset_value_cents"],
        "carry_net_cents": totals["carry_net_cents"], "reconciliation_difference_cents": nav["reconciliation_difference_cents"],
    }
    source_hash = hashlib.sha256(json.dumps(case, sort_keys=True, separators=(",", ":"), default=lambda item: item.isoformat()).encode("utf-8")).hexdigest()
    return {
        "case_id": case["case_id"], "name": case["name"], "data_kind": "SYNTHETIC", "status": status,
        "asof": asof.isoformat(), "known_at": known_at.isoformat(), "effective_through": effective_through,
        "input_sha256": source_hash, "facility_rate_bps": rate, "facility_limit_cents": limit,
        "commitment_cents": sum(weights.values()), "investors": investor_output, "balances": nav,
        "totals": totals, "nav_bridge": bridge, "event_journal": journal, "controls": controls,
        "failed_event": failed_event, "excluded_events": excluded,
        "unposted_source_event_ids": [event["event_id"] for event in selected
                                      if event["event_id"] not in {row["source_event_id"] for row in journal
                                                                 if row["kind"] != "INTEREST_ACCRUAL"}],
        "selected_source_event_count": len(selected), "posted_source_event_count": sum(row["kind"] != "INTEREST_ACCRUAL" for row in journal),
        "methodology": "Economic book capital; fixed commitment weights; interval-rounded fixed-rate ACT/365; zero opening balances.",
    }
