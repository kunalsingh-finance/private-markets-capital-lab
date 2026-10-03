"""Bounded LP cash-flow mathematics, with explicit unsupported cases."""

from bisect import bisect_right
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
import math


def money(text: str) -> int:
    """Parse nonnegative USD into integer cents without silent rounding."""
    try:
        amount = Decimal(str(text))
    except InvalidOperation as exc:
        raise ValueError(f"Invalid money: {text!r}") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError(f"Money must be finite, nonnegative and whole cents: {text!r}")
    # Decimal arithmetic can silently round long coefficients under its context.
    # Extract the coefficient/exponent instead and respect SQLite's integer range.
    _, digits, exponent = amount.as_tuple()
    if not any(digits):
        return 0
    shift = exponent + 2
    if len(digits) + shift > 19:
        raise ValueError("Money exceeds the signed 64-bit cents range")
    coefficient = int("".join(str(digit) for digit in digits))
    if shift < 0:
        if -shift >= len(digits):
            raise ValueError("Money must contain whole cents")
        cents, remainder = divmod(coefficient, 10 ** (-shift))
        if remainder:
            raise ValueError("Money must contain whole cents")
    else:
        cents = coefficient * 10 ** shift
    if cents > 2**63 - 1:
        raise ValueError("Money exceeds the signed 64-bit cents range")
    return cents


def metrics(paid_in: int, distributed: int, nav: int) -> dict:
    if any(not isinstance(v, int) or isinstance(v, bool) or v < 0 for v in (paid_in, distributed, nav)):
        raise ValueError("Metric amounts must be nonnegative integer cents")
    if paid_in == 0:
        return {"dpi": None, "rvpi": None, "tvpi": None}
    return {"dpi": distributed / paid_in, "rvpi": nav / paid_in, "tvpi": (distributed + nav) / paid_in}


def xirr(flows: list[tuple[date, int]]) -> dict:
    """Actual/365 IRR for a conventional negative-then-positive dated series.

    Aggregate same-date amounts before testing signs. Alternating series are
    returned for review rather than picking one potentially ambiguous root.
    The numerical domain is bounded to -99.99% through 10,000% annual return.
    """
    by_date = defaultdict(int)
    for when, amount in flows:
        if type(when) is not date or not isinstance(amount, int) or isinstance(amount, bool):
            raise ValueError("XIRR expects date objects and signed integer cents")
        by_date[when] += amount
    ordered = [(when, amount) for when, amount in sorted(by_date.items()) if amount]
    empty = {"value": None, "status": "UNDEFINED", "residual_cents": None}
    if len(ordered) < 2 or not any(v < 0 for _, v in ordered) or not any(v > 0 for _, v in ordered):
        return empty
    signs = [1 if amount > 0 else -1 for _, amount in ordered]
    changes = sum(a != b for a, b in zip(signs, signs[1:]))
    if signs[0] != -1 or signs[-1] != 1 or changes != 1:
        return {**empty, "status": "NON_CONVENTIONAL"}
    origin = ordered[0][0]
    scale = max(abs(amount) for _, amount in ordered)
    terms = [((when - origin).days / 365.0, amount / scale) for when, amount in ordered]

    def npv(log_growth):
        # Positive rescaling keeps the root/sign while avoiding overflow near -1.
        powers = [-years * log_growth for years, _ in terms]
        shift = max(powers)
        return math.fsum(amount * math.exp(power - shift) for power, (_, amount) in zip(powers, terms))

    low, high = math.log(0.0001), math.log(101.0)
    f_low, f_high = npv(low), npv(high)
    if f_low * f_high > 0:
        return {**empty, "status": "OUT_OF_RANGE"}
    if npv(0.0) == 0:
        log_rate = 0.0
    else:
        for _ in range(160):
            middle = (low + high) / 2
            if npv(middle) > 0:
                low = middle
            else:
                high = middle
        log_rate = (low + high) / 2
    rate = math.expm1(log_rate)
    # Discount relative to the first cash flow; report actual cent residual.
    try:
        residual = math.fsum(amount * math.exp(-(when - origin).days / 365.0 * log_rate) for when, amount in ordered)
    except OverflowError:
        return {**empty, "status": "OUT_OF_RANGE"}
    return {"value": rate, "status": "OK", "residual_cents": residual}


def ks_pme(flows: list[dict], nav: int, asof: date, benchmark: list[tuple[date, float]], max_lag_days: int = 7) -> float | None:
    """Kaplan-Schoar-style ratio from total-return levels at flow and terminal dates.

    Forward-valued distributions plus terminal NAV / forward-valued calls.
    Only an observation on/before each event may be used; a stale observation
    beyond the configured calendar-day lag returns an unavailable result.
    """
    if type(asof) is not date or not isinstance(nav, int) or isinstance(nav, bool) or nav < 0:
        raise ValueError("Invalid PME terminal date or NAV")
    if not isinstance(max_lag_days, int) or isinstance(max_lag_days, bool) or max_lag_days < 0:
        raise ValueError("Invalid benchmark lag")
    levels = {}
    for when, level in benchmark:
        if type(when) is not date or not math.isfinite(level) or level <= 0 or when in levels:
            raise ValueError("Benchmark requires unique dates and finite positive total-return levels")
        levels[when] = level
    dates = sorted(levels)

    def level_at(when):
        index = bisect_right(dates, when) - 1
        if index < 0 or (when - dates[index]).days > max_lag_days:
            return None
        return levels[dates[index]]

    terminal_level = level_at(asof)
    calls, distributions = [], []
    for flow in flows:
        when, kind, amount = flow["date"], flow["kind"], flow["amount_cents"]
        if type(when) is not date or when > asof or kind not in {"CALL", "DISTRIBUTION"}:
            raise ValueError("Invalid PME flow date or kind")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 0:
            raise ValueError("Invalid PME flow amount")
        flow_level = level_at(when)
        if flow_level is None or terminal_level is None:
            # Validate all flow records even when one observation is unavailable.
            value = None
        else:
            value = amount * terminal_level / flow_level
        (calls if kind == "CALL" else distributions).append(value)
    if terminal_level is None or any(v is None for v in calls + distributions):
        return None
    denominator = math.fsum(calls)
    return (math.fsum(distributions) + nav) / denominator if denominator else None


def subscription_line_example() -> dict:
    """Fixed illustrative LP timing comparison; costs reduce terminal wealth."""
    immediate, delayed, end = date(2024, 1, 1), date(2024, 7, 1), date(2026, 6, 30)
    investment, cost, distribution = 10_000_000_00, 300_000_00, 15_000_000_00
    return {
        "immediate_rate": xirr([(immediate, -investment), (end, distribution)])["value"],
        "delayed_rate": xirr([(delayed, -(investment + cost)), (end, distribution)])["value"],
        "immediate_paid_in_cents": investment,
        "delayed_paid_in_cents": investment + cost,
        "distribution_cents": distribution,
        "delay_days": (delayed - immediate).days,
        "financing_cost_cents": cost,
    }
