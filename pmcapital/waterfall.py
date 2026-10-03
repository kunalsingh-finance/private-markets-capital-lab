"""Fictional whole-fund, single-terminal-distribution carry calculation.

All amounts are integer cents. Preferred return is SIMPLE Actual/365; no
interim LP distributions, recycling, tax adjustments or contractual LPA claims.
"""

from datetime import date
from fractions import Fraction


def _cents(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be nonnegative integer cents")
    return value


def _bps(value, name, upper=10000):
    if type(value) is not int or not 0 <= value <= upper:
        raise ValueError(f"{name} must be an integer between 0 and {upper}")
    return value


def _day(value, name):
    if type(value) is not date:
        raise ValueError(f"{name} must be a date without a time component")
    return value


def _half_up(value):
    """Round a nonnegative Fraction to integer cents, exactly, ties upward."""
    return (2 * value.numerator + value.denominator) // (2 * value.denominator)


def european_waterfall(
    contributions: list[tuple[date, int]],
    proceeds_cents: int,
    distribution_date: date,
    hurdle_bps: int = 800,
    carry_bps: int = 2000,
    catchup_bps: int = 10000,
    prior_gp_carry_cents: int = 0,
) -> dict:
    """Allocate cumulative lifetime proceeds and calculate an unnetted GP true-up.

    ``proceeds_cents`` INCLUDES any previously paid GP carry. The returned LP/GP
    allocations are full lifetime entitlements, not today's cash instructions.
    Prior carry affects only clawback/additional-due fields. Each contribution
    remains outstanding through one terminal distribution. See methodology.
    """
    terminal = _day(distribution_date, "distribution_date")
    proceeds = _cents(proceeds_cents, "proceeds_cents")
    prior = _cents(prior_gp_carry_cents, "prior_gp_carry_cents")
    hurdle = _bps(hurdle_bps, "hurdle_bps")
    carry = _bps(carry_bps, "carry_bps", upper=9999)
    catchup = _bps(catchup_bps, "catchup_bps")
    if carry and catchup <= carry:
        raise ValueError("catchup_bps must exceed carry_bps when carry is positive")
    if prior > proceeds:
        raise ValueError("lifetime proceeds must include all prior GP carry")
    if not isinstance(contributions, (list, tuple)):
        raise ValueError("contributions must be a sequence of (date, positive cents)")

    capital = 0
    preferred_exact = Fraction(0)
    normalized = []
    for entry in contributions:
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            raise ValueError("each contribution must contain a date and positive cents")
        contribution_date = _day(entry[0], "contribution date")
        amount = _cents(entry[1], "contribution amount")
        if amount == 0:
            raise ValueError("contribution amounts must be positive")
        if contribution_date > terminal:
            raise ValueError("contribution dates cannot follow the terminal distribution")
        days = (terminal - contribution_date).days
        capital += amount
        preferred_exact += Fraction(amount * hurdle * days, 365 * 10000)
        normalized.append({"date": contribution_date.isoformat(), "amount_cents": amount, "days": days})
    if not capital and proceeds:
        raise ValueError("positive lifetime proceeds require contributed capital")

    # Round the aggregate entitlement once: splitting a contribution cannot
    # change preferred return through repeated penny rounding.
    preferred_due = _half_up(preferred_exact)
    remaining = proceeds
    capital_return = min(remaining, capital)
    remaining -= capital_return
    preferred_paid = min(remaining, preferred_due)
    remaining -= preferred_paid

    # q*T = c*(preferred_paid + T), so T = c*preferred_paid/(q-c).
    # A rounded total tier is then split once; the LP gets the remaining cents.
    catchup_target = (
        _half_up(Fraction(carry * preferred_paid, catchup - carry)) if carry else 0
    )
    catchup_total = min(remaining, catchup_target)
    catchup_gp = _half_up(Fraction(catchup_total * catchup, 10000))
    catchup_lp = catchup_total - catchup_gp
    remaining -= catchup_total
    residual_gp = _half_up(Fraction(remaining * carry, 10000))
    residual_lp = remaining - residual_gp
    residual_total = remaining

    tiers = [
        {"name": "Return LP capital", "lp_cents": capital_return, "gp_cents": 0, "total_cents": capital_return},
        {"name": "LP preferred return", "lp_cents": preferred_paid, "gp_cents": 0, "total_cents": preferred_paid},
        {"name": "GP catch-up", "lp_cents": catchup_lp, "gp_cents": catchup_gp, "total_cents": catchup_total},
        {"name": "Residual profit split", "lp_cents": residual_lp, "gp_cents": residual_gp, "total_cents": residual_total},
    ]
    lp_total = capital_return + preferred_paid + catchup_lp + residual_lp
    gp_total = catchup_gp + residual_gp
    clawback = max(prior - gp_total, 0)
    additional = max(gp_total - prior, 0)
    caught_up = capital_return == capital and preferred_paid == preferred_due and catchup_total == catchup_target
    rounded_gp_profit_target = _half_up(Fraction(max(proceeds - capital, 0) * carry, 10000))
    rounding_difference = gp_total - rounded_gp_profit_target
    controls = {
        "cash_conserved": lp_total + gp_total == proceeds,
        "tiers_reconcile": all(row["lp_cents"] + row["gp_cents"] == row["total_cents"] for row in tiers),
        "nonnegative_allocations": all(row["lp_cents"] >= 0 and row["gp_cents"] >= 0 for row in tiers),
        "capital_priority_respected": capital_return == capital or preferred_paid + catchup_total + residual_total == 0,
        "preferred_priority_respected": preferred_paid == preferred_due or catchup_total + residual_total == 0,
        "prior_carry_included_in_total": prior <= proceeds,
        "gp_true_up_reconciles": prior + additional - clawback == gp_total,
        "carry_target_within_one_cent_when_caught_up": not caught_up or abs(rounding_difference) <= 1,
    }
    if not all(controls.values()):
        raise ArithmeticError("waterfall accounting controls failed")
    return {
        "model": "Fictional European terminal/lifetime cumulative true-up",
        "preferred_convention": "SIMPLE Actual/365; aggregate half-up cents",
        "distribution_date": terminal.isoformat(),
        "contributions": sorted(normalized, key=lambda row: row["date"]),
        "hurdle_bps": hurdle,
        "carry_bps": carry,
        "catchup_bps": catchup,
        "capital_cents": capital,
        "total_proceeds_cents": proceeds,
        "prior_gp_carry_cents": prior,
        "capital_return_cents": capital_return,
        "capital_shortfall_cents": capital - capital_return,
        "preferred_due_cents": preferred_due,
        "preferred_paid_cents": preferred_paid,
        "preferred_unpaid_cents": preferred_due - preferred_paid,
        "catchup_target_total_cents": catchup_target,
        "catchup_total_cents": catchup_total,
        "catchup_gp_cents": catchup_gp,
        "catchup_lp_cents": catchup_lp,
        "residual_lp_cents": residual_lp,
        "residual_gp_cents": residual_gp,
        "lp_total_cents": lp_total,
        "gp_total_cents": gp_total,
        "clawback_due_cents": clawback,
        "gp_additional_due_cents": additional,
        "catchup_completed": caught_up,
        "gp_carry_target_rounding_difference_cents": rounding_difference if caught_up else None,
        "tiers": tiers,
        "controls": controls,
    }


def run_waterfall_demo() -> dict:
    """Four fixed synthetic scenarios, independent of the fund-reporting tape."""
    contributions = [
        (date(2022, 6, 30), 200000000),
        (date(2023, 6, 30), 200000000),
        (date(2024, 6, 30), 100000000),
    ]
    terminal = date(2026, 6, 30)
    definitions = [
        ("BASE", "Base exit", "Profitable terminal exit completes preferred return and catch-up.", 800000000, 0),
        ("LOW_PROFIT", "Low profit", "Positive profit cannot fully pay the accrued simple preferred return.", 550000000, 0),
        ("LOSS", "Capital loss", "Lifetime proceeds are below contributed capital; no GP carry is earned.", 400000000, 0),
        ("CLAWBACK", "Prior carry true-up", "Low-profit lifetime proceeds include $300,000 already paid to the GP.", 550000000, 30000000),
    ]
    return {
        "data_mode": "SYNTHETIC",
        "title": "Fictional whole-fund terminal waterfall",
        "distribution_date": terminal.isoformat(),
        "contributions": [{"date": day.isoformat(), "amount_cents": amount} for day, amount in contributions],
        "assumptions": [
            "Three LP contributions total $5,000,000; one terminal LP distribution on June 30, 2026.",
            "8% SIMPLE Actual/365 preferred return, 20% carry, 100% GP catch-up.",
            "Lifetime proceeds include prior GP carry; clawback is an unnetted economic entitlement test.",
            "No prior LP distribution accrual path, fees, taxes, recycling, escrow or investor classes.",
            "Scenario proceeds are synthetic assumptions, not liquidation forecasts or reported NAV.",
        ],
        "scenarios": [
            {
                "scenario_id": key,
                "name": name,
                "description": description,
                "result": european_waterfall(contributions, proceeds, terminal, prior_gp_carry_cents=prior),
            }
            for key, name, description, proceeds, prior in definitions
        ],
    }
