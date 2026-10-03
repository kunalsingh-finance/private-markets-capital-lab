# Fictional whole-fund terminal waterfall

This module allocates a fictional fund's lifetime distributable proceeds between LPs and a GP, then compares the GP's lifetime entitlement with prior carry paid. It is a separate terminal sensitivity case; it does not infer liquidation proceeds or carry terms from the portfolio-reporting fixtures.

The tier sequence follows the whole-fund illustration in ILPA's *Private Equity Accounting: Critical Points All Investors Should Consider*, appendix page 34: return contributions, pay preferred return, catch up the carry recipient, then split remaining profit. Its full-GP catch-up example makes a 20% carry catch-up one quarter of the preferred return. [ILPA accounting presentation](https://ilpa.org/wp-content/uploads/2017/03/ILPA-EUF-PE-Accounting_FINAL.pdf). ILPA also publishes distinct whole-fund and deal-by-deal model agreements. [ILPA Model LPA overview](https://ilpa.org/industry-guidance/templates-standards-model-documents/model-limited-partnership-agreement/). Sources were reviewed October 2, 2026.

The rules below are this project's explicit fictional agreement. In particular, **SIMPLE Actual/365 preferred return is a project assumption**. This is not an implementation of ILPA's complete model LPA or an interpretation of a real partnership agreement.

## Input contract and scope

`european_waterfall(contributions, proceeds_cents, distribution_date, hurdle_bps=800, carry_bps=2000, catchup_bps=10000, prior_gp_carry_cents=0)` accepts positive integer-cent LP contributions with dates, one terminal date, nonnegative integer-cent lifetime proceeds and prior GP carry. Dates contain no time component, and contributions cannot follow the terminal date. No contribution is returned before that terminal date.

Rates are integer basis points. Hurdle is 0–10,000 bps; carry is 0–9,999 bps; catch-up is 0–10,000 bps. A positive carry requires a catch-up allocation rate strictly above the carry rate. Zero carry permits zero catch-up and allocates all proceeds to LPs. An empty contribution tape is defined only for zero proceeds. These bounds describe supported fictional cases, not market limits.

**Lifetime proceeds include all prior GP carry paid.** Prior GP carry must not exceed those proceeds. The function does not subtract prior carry before applying the tiers. LP and GP totals describe cumulative entitlements; they are not today's net payment instructions. Previous LP cash distributions and their effect on outstanding capital or preferred accrual are unsupported. The API deliberately has no interim-distribution input.

## Exact arithmetic and tiers

Let `C` be total contributed cents, `P` lifetime proceeds, `h` hurdle bps, `c` carry bps and `q` catch-up bps. Each contribution `C_i` accrues for its actual calendar days `d_i` until the terminal date:

```text
preferred_due = half_up(sum(C_i * h * d_i / (365 * 10000)))
```

Preferred is simple interest; no interest accrues on unpaid preferred. Rational arithmetic retains fractional cents until the entire preferred entitlement is summed, then rounds once half up. Splitting a same-date contribution cannot increase preferred through separate rounding. Leap days count as actual days with the denominator fixed at 365.

| Tier | Allocation rule |
| --- | --- |
| 1 — Capital | LP receives `min(P, C)`. Any capital shortfall remains visible. |
| 2 — Preferred | LP receives available cash up to the accrued preferred entitlement. The result reports both accrued and unpaid preferred. |
| 3 — Catch-up | The tier shares cash `q/10000` to GP until the rounded catch-up target is reached, or available proceeds are exhausted. LP receives the rest. |
| 4 — Residual | Remaining proceeds share `c/10000` to GP; LP receives the rest. |

For preferred paid `H`, the unrounded total catch-up tier `T` solves:

```text
(q / 10000) * T = (c / 10000) * (H + T)
T = c * H / (q - c)
```

At a 100% GP catch-up and 20% carry, `T = H / 4`. A split catch-up has an LP allocation too: with 50% catch-up and 20% carry, `T = 2H/3`.

The target tier amount is rounded half up. Each GP tier allocation rounds half up once; the LP receives that tier's exact remaining cents. This avoids cash creation by independently rounding both recipients. At penny-sized thresholds, independently rounded catch-up and residual GP allocations can differ from the rounded lifetime carry target by one cent. The output reports that signed difference when catch-up completes and requires its absolute value to remain at most one cent. A partially completed catch-up intentionally leaves GP below its lifetime target.

## Unnetted GP true-up

```text
GP entitlement = catchup_GP + residual_GP
clawback_due = max(prior_GP_paid - GP_entitlement, 0)
GP_additional_due = max(GP_entitlement - prior_GP_paid, 0)
prior_GP_paid + GP_additional_due - clawback_due = GP_entitlement
```

These are economic true-up amounts before taxes, escrow, guarantees, collection uncertainty or contractual clawback caps. They do not change the lifetime cash allocated by the tiers. A prior payment exceeding current entitlement remains visible even when the fund made a profit.

## Fixed demo and verification

The demo contributes $2m on June 30, 2022, $2m on June 30, 2023 and $1m on June 30, 2024, with a June 30, 2026 terminal date. Its terms are 8% simple preferred, 20% carry and 100% GP catch-up. Preferred due is $1,280,876.71, including the leap day in each contribution's applicable interval.

| Synthetic scenario | Lifetime proceeds | Prior GP paid | Outcome |
| --- | ---: | ---: | --- |
| Base exit | $8m | $0 | Completes preferred and catch-up; GP entitlement $600,000. |
| Low profit | $5.5m | $0 | Preferred remains unpaid; no GP entitlement. |
| Capital loss | $4m | $0 | $1m capital shortfall; no GP entitlement. |
| Prior carry true-up | $5.5m | $300,000 | $300,000 economic clawback due. |

Run `python -m unittest discover -s tests -p test_waterfall.py -v` from the repository root. Analytical cases cover capital/preferred boundaries, partial/full/split catch-up, residual carry, prior-paid true-up, exact half-cent rounding, contribution-splitting invariance, leap-day accrual and invalid inputs. A penny-boundary grid checks cash conservation and allocation priorities across supported rates. The complete result must serialize with `json.dumps(..., allow_nan=False)`.

Each result requires LP plus GP to equal proceeds, each tier to reconcile, allocations to remain nonnegative, capital and preferred priorities to hold, and the GP true-up to reconcile. Passing checks establish consistency under the fictional rules. They do not validate real fund terms or forecast cash availability.

Fees, taxes, fee offsets, recycled proceeds, GP invested capital, escrow interest, multiple investor classes, equalization, interim distributions, contingent proceeds and stateful preferred-accrual balances are outside this terminal case.
