# Northstar economic capital ledger

Northstar Partnership (Synthetic) is a separate fictional partnership. Its investors, fees, facility, investment transactions and capital accounts do not come from the four comparison funds in `data/sample/`. All opening balances are zero, all amounts are USD integer cents, and the supplied agreements and rates are hypothetical.

The ledger models economic book equity. It does not calculate tax basis, tax capital, legally enforceable allocation provisions or a lender's borrowing base. The IRS capital-account instructions distinguish contributed capital, allocated income/loss and distributions, and explain that ending capital can be negative; those concepts inform the bridge, but this project is not a tax-accounting implementation. [IRS Form 1065 instructions, Item L](https://www.irs.gov/instructions/i1065).

## Run and inspect

```python
from datetime import date
from pmcapital.capital import load_capital_case, run_capital_case

base = run_capital_case()
restated = run_capital_case(
    load_capital_case("recallable"),
    asof=date(2026, 6, 30),
    known_at=date(2026, 9, 15),
)
```

`run_capital_case(case=None, asof=None, known_at=None)` returns a JSON-ready dictionary. An omitted case loads `data/advanced/northstar_base.json`. Omitted cutoffs use the case's `asof` and `known_at` dates. Explicit cutoff arguments must be `datetime.date`, rather than strings or datetimes.

The result includes `investors`, `balances`, `totals`, `nav_bridge`, `event_journal`, `controls`, `failed_event`, `excluded_events` and an input hash. `effective_through` identifies the date reached by the ledger. A failed ledger retains the requested reporting date but explicitly identifies the earlier last-valid balance date; those balances are not a completed reporting-date NAV.

## Input contract

Each case has `case_id`, `name`, `asof`, `known_at`, `facility_limit_cents`, `facility_rate_bps`, `management_fee_bps`, an `investors` array and an `events` array. Investor records require a unique `investor_id`, a `name`, an `LP` or `GP` role and positive `commitment_cents`. The base investor commitments are 60%, 38% and 2%; the GP contributes capital on the same terms as the LPs before any separate carried-interest allocation.

Each event requires a unique `event_id`, `effective_date`, `recorded_date`, `kind` and nonnegative integer `amount_cents`. Source dates use `YYYY-MM-DD`. The recorded date cannot precede the effective date. Source IDs beginning `ACCRUAL:` are reserved for generated interest journal entries. IDs represent distinct events, not revised versions: corrected source events require an explicit, documented source-case revision, rather than replaying an ID twice.

| Kind | Balance effect and required additional fields |
| --- | --- |
| `CALL` | Increase cash and investor contributed capital. Optional `investor_allocations` gives exact contributions per investor. |
| `INVEST` | Reduce cash; increase investment carrying book and historical cost by the same amount. |
| `REALIZATION` | Increase cash by proceeds; reduce carrying book by `cost_cents`. `historical_cost_cents` specifies the disposed original cost and is required when the investment pool has a valuation mark. |
| `REVALUE` | `amount_cents` must be zero. Signed `delta_cents` changes carrying book and investor unrealized gains; historical cost is unchanged. |
| `DISTRIBUTION` | Reduce cash and investor capital. Optional exact `investor_allocations`; otherwise commitment-weighted. |
| `RECALLABLE_DISTRIBUTION` | Same cash/capital effect, plus explicit investor recallable commitment capacity. |
| `FEE` | Reduce cash and capital as an expense. Optional `period_start`, `period_end` and `annual_bps` verify a committed-capital ACT/365 fee; absent `annual_bps` uses the case rate. |
| `FACILITY_DRAW` | Increase cash and facility principal. |
| `FACILITY_REPAY` | Reduce cash and principal; does not recognize another expense. |
| `INTEREST_PAYMENT` | Reduce cash and the already accrued interest liability; does not expense interest twice. |
| `INTEREST` | Direct cash expense for a separate, previously unaccrued interest charge. It is not a substitute for `INTEREST_PAYMENT` on the modeled accruing facility. |
| `CARRY_ALLOCATION` | `recipient_id` must identify a GP. Transfer capital from all capital contributors by commitment weight to that GP; total capital and cash are unchanged. |

Only calls and the two distribution kinds accept explicit cash allocations. Every allocation value must be a nonnegative integer cent amount, every ID must be known, and the allocation sum must equal the event's cash amount exactly. Omitted known investors receive zero in an explicit allocation. Earnings, fees and interest use fixed commitment weights, rather than the explicit cash-allocation map.

## Exact accounts and event controls

Every posted source event and every generated interest accrual must satisfy:

```text
cash + investment carrying book - facility principal - accrued interest
    = sum of investor economic capital

investor capital
    = paid-in + realized gain + remaining unrealized gain
      - fees - interest expense - distributions + net carry allocation

remaining unrealized gain
    = investment carrying book - remaining historical cost

unfunded capacity
    = original commitment + cumulative recallable distributions - cumulative calls
```

`balances` and each journal row's `balances_before` / `balances_after` include `cash_cents`, `investments_cents`, `investment_cost_cents`, `debt_cents`, `accrued_interest_cents`, `equity_cents`, `net_asset_value_cents`, `investor_capital_cents` and `reconciliation_difference_cents`. `equity_cents` and `net_asset_value_cents` are identical. Historical cost is a supporting book amount, not another asset added to NAV.

Each investor reports contributed capital, distributions, recallable amounts, remaining capacity, fees, interest, total gain, realized gain, remaining unrealized gain and net carry transfers. `carry_received_cents` separately records gross carry credited to a GP. `event_journal` retains the source ID, economic date, recorded date, exact investor deltas, before/after balances and capital after posting.

Cash, investment book, historical cost, principal and accrued interest cannot become negative. Principal cannot exceed the fixed facility limit. Each investor's cumulative calls cannot exceed its own commitment plus its own recallable distributions. A regular distribution does not replenish commitments. The model neither clips failed balances nor uses another investor's unused capacity to hide an overcall.

Investor capital itself is signed. Interest on a bridge before the first investor contribution can create a temporary deficit; the liability and equal reduction of equity are shown. A deficit remaining at the reporting date produces `REVIEW_REQUIRED`. This is an economic disclosure, not a conclusion about an investor's legal liability.

## Realized and unrealized gains

The investment ledger is one aggregate economic pool with explicit disposed book and historical-cost amounts. It does not infer lot selection or allocate a realized sale's historical cost from its proceeds. A marked pool requires `historical_cost_cents` on a realization. Without a mark, omitted historical cost defaults to the disposed carrying amount.

For a sale, the NAV-changing gain is proceeds less disposed carrying book. The previously recognized mark on the disposed investment is reclassified from unrealized to realized. Fund realized gain is therefore proceeds less disposed historical cost. Reclassification adds no second gain and changes no NAV. A partial sale leaves the undisposed book, historical cost and unrealized mark in the ledger; a full pool exit clears each investor's remaining unrealized balance exactly, including earlier penny allocations.

The base buys an investment for $6 million, marks it to $6.6 million, then realizes $9 million. Total gain is $3 million. At the mark, $600,000 is unrealized; after the complete exit, the entire $3 million is realized and unrealized gain is zero.

## Fees, facility accrual and rounding

`management_fee(commitment_cents, annual_bps, start, end)` computes:

```text
round_HALF_UP(commitment_cents * annual_bps * actual_days / (10,000 * 365))
```

Intervals use `[start, end)`, with actual calendar days and a fixed 365-day denominator, including leap years. A period-backed fee must equal this exact result and its period must end by the payment's effective date. There is no automatic management-fee payment: the source case includes explicit fee events. The base pays a January 1–April 1 fee and an April 1–June 30 reporting stub at a fictional 200 basis-point annual rate on committed capital. It does not model fee offsets, negotiated exemptions or a post-investment-period fee-basis change.

The modeled facility has a fictional fixed 650 basis-point rate and $6.5 million limit. Before each selected event, interest accrues on the outstanding principal over the preceding interval. A final interval accrues through `asof`. Each interval is rounded HALF_UP to whole cents once, charged to investor capital and credited to an accrued-interest liability. No interest accrues on accrued interest. Debt drawn on a day starts accruing after that date; debt repaid on a day accrues through the preceding interval. Same-day transactions accrue zero additional days.

In the base, $6 million is outstanding from January 2 through April 1: 89 days and $95,095.89 of interest. The April call funds principal repayment, interest payment and management fees. Repayment before the interest-payment event does not erase the accrued liability. Interval rounding can change a result by a cent when extra source events split an interval; the journal exposes every interval and its rate.

Investor allocations use integer largest remainders. Fractional cent remainders are ranked from largest to smallest; equal remainders use lexicographic investor ID. Loss allocations are the sign-reversed positive allocation. Ownership weights remain fixed at original commitments. Separate event rounding can differ by a cent from allocating a cumulative ending balance once. A closing distribution therefore uses exact existing capital balances when complete account closure is intended.

ILPA recommends disclosing facility terms, costs, usage and the methodology used to assess performance with and without a line. This project exposes those economic effects but does not claim that its fictional fixed-rate facility reconstructs an actual fund's credit agreement. [ILPA subscription-line disclosure guidance](https://ilpa.org/wp-content/uploads/2020/06/ILPA-Guidance-on-Disclosures-Related-to-Subscription-Lines-of-Credit_2020_FINAL.pdf).

## Knowledge cutoffs and failed attempts

Only events whose effective date is on/before `asof` and recorded date is on/before `known_at` are replayed. All source records are schema-validated before selection. Selected events sort by effective date; events on the same day keep their input order. An appended terminal carry allocation and distribution therefore follow the original same-day realization and fees.

Withheld events appear in `excluded_events` with their dates and a reason. The engine does not insert an excluded call or draw to make the cash ledger work. If an eligible investment depends on a late-recorded, unavailable draw, the selected ledger fails visibly.

Malformed contracts raise `ValueError`. Economic gates return `FAILED` with the failed source event, a high-severity control, unposted source IDs and the last valid journal. An interest accrual legitimately posted before a failing cash payment remains recognized. The failing source event never partially changes accounts. Root reporting must treat `FAILED` as an unreleased result.

## Bundled scenarios

| Case helper name | Dates and purpose |
| --- | --- |
| `base` | June 30 / August 15. Fully exits the investment, pays debt and expenses, and retains $9,306,273.97 for the separate whole-fund waterfall. No distribution is baked into the input. |
| `delayed_distribution` | August 31 / September 15. Retains the same June net cash until July 31, then explicitly closes every investor capital account. The fixed prior fees and interest are unchanged. |
| `cash_shortfall` | June 30 / August 15. Reduces the April call to $6 million. Principal can be repaid, but cash cannot cover accrued interest; the payment fails with preserved partial evidence. |
| `recallable` | June 30 / August 15. $3 million of recallable distributions permit cumulative calls of $13 million on $10 million of original commitments. A $1,000 fee recorded September 1 is withheld until the knowledge date includes it. |

Carry is supplied by the separate hypothetical waterfall, rather than inferred by this engine. `CARRY_ALLOCATION` reallocates the resulting economic equity, then an explicit terminal distribution of the post-carry capital balances can close every account exactly. This does not implement tax allocations, multiple share classes, changing ownership, deal-specific investment lots, a contractual borrowing base, variable rates or legal waterfall interpretation.

## Verification

```powershell
python -m unittest discover -s tests -p test_capital.py -v
```

Checks cover analytical fee and interest amounts, every journal's accounting identity, realized/unrealized classifications after marked and partial exits, exact penny allocations, full closing distributions, carry transfers, commitment recycling, investor-specific capacity, source replay, chronological order, late information, and failed-payment/limit/overpayment controls.
