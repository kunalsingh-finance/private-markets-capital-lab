"""Finite-domain root diagnostics; do not infer global uniqueness from a scan."""

from bisect import bisect_right
from collections import defaultdict
from datetime import date
import math
from .analytics import xirr


def root_diagnostics(flows: list[tuple[date, int]], grid_size: int = 4096) -> dict:
    """Observe sign-changing XNPV roots in log(1+r), preserving review status.

    Same-date amounts are aggregated. Conventional flows use the validated
    unique-root solver. Other patterns are sampled over the same bounded domain;
    tangent roots and roots between closely spaced crossings may be missed.
    A finite scan can never certify absence or uniqueness for mixed signs.
    """
    if isinstance(grid_size, bool) or not isinstance(grid_size, int) or not 128 <= grid_size <= 65536:
        raise ValueError("Grid size must be an integer from 128 through 65536")
    primary = xirr(flows)
    if primary["status"] == "OK":
        return {"status": "CONVENTIONAL_UNIQUE", "candidate_rates": [primary["value"]], "certified_by_sign_pattern": True,
                "grid_size": 0, "minimum_rate": -0.9999, "maximum_rate": 100.0, "limitation": None}
    grouped = defaultdict(int)
    for when, amount in flows:
        grouped[when] += amount
    ordered = [(when, amount) for when, amount in sorted(grouped.items()) if amount]
    result = {"status": primary["status"], "candidate_rates": [], "certified_by_sign_pattern": False,
              "grid_size": grid_size, "minimum_rate": -0.9999, "maximum_rate": 100.0,
              "limitation": "Finite scan detects sampled sign crossings, not every possible root; candidates require review."}
    if len(ordered) < 2 or not any(v < 0 for _, v in ordered) or not any(v > 0 for _, v in ordered):
        return result
    origin, scale = ordered[0][0], max(abs(v) for _, v in ordered)
    terms = [((when - origin).days / 365, amount / scale) for when, amount in ordered]

    def normalized_npv(log_rate):
        powers = [-years * log_rate for years, _ in terms]
        shift = max(powers)
        return math.fsum(amount * math.exp(power - shift) for power, (_, amount) in zip(powers, terms))

    lower, upper = math.log(0.0001), math.log(101)
    points = sorted(set([0.0] + [lower + (upper - lower) * step / grid_size for step in range(grid_size + 1)]))
    logs = []
    for a, b in zip(points, points[1:]):
        fa, fb = normalized_npv(a), normalized_npv(b)
        if fa == 0:
            logs.append(a)
        if fa * fb < 0:
            left, right = a, b
            for _ in range(90):
                mid = (left + right) / 2
                fm = normalized_npv(mid)
                if fa * fm <= 0:
                    right = mid
                else:
                    left, fa = mid, fm
            logs.append((left + right) / 2)
    if normalized_npv(points[-1]) == 0:
        logs.append(points[-1])
    unique = []
    for log_rate in sorted(logs):
        if not unique or abs(log_rate - unique[-1]) > 1e-9:
            unique.append(log_rate)
    result["candidate_rates"] = [math.expm1(v) for v in unique]
    result["status"] = "MIXED_FLOW_CANDIDATES_REVIEW" if unique else "NO_CROSSING_OBSERVED_REVIEW"
    return result


def benchmark_adjusted_return(flows: list[dict], nav: int, asof: date, benchmark: list[tuple[date, float]], max_lag_days: int = 7) -> dict:
    """Dated IRR of benchmark-terminalized LP flows (direct-alpha style).

    This diagnostic uses integer-cent rounded transformed flows and a supplied
    total-return index. It is annualized but not a risk-adjusted alpha estimate.
    """
    from .analytics import ks_pme
    pme = ks_pme(flows, nav, asof, benchmark, max_lag_days)
    if not any(flow["kind"] == "CALL" and flow["amount_cents"] > 0 for flow in flows):
        return {"status": "UNDEFINED_NO_CONTRIBUTIONS", "value": None, "candidate_rates": []}
    if pme is None:
        return {"status": "BENCHMARK_UNAVAILABLE", "value": None, "candidate_rates": []}
    levels = dict(benchmark)
    dates = sorted(levels)

    def latest(when):
        return levels[dates[bisect_right(dates, when) - 1]]

    from decimal import Decimal, ROUND_HALF_UP, localcontext
    transformed = []
    with localcontext() as context:
        context.prec = 48
        for flow in flows:
            amount = Decimal(flow["amount_cents"]) * Decimal(str(latest(asof))) / Decimal(str(latest(flow["date"])))
            cents = int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))
            transformed.append((flow["date"], -cents if flow["kind"] == "CALL" else cents))
    transformed.append((asof, nav))
    primary = xirr(transformed)
    diagnostics = root_diagnostics(transformed)
    return {**primary, "candidate_rates": diagnostics["candidate_rates"], "root_status": diagnostics["status"],
            "rounding": "Benchmark-terminalized amounts rounded to integer cents, half up", "not_risk_adjusted": True}
