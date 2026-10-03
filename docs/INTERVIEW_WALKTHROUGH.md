# Interview walkthrough

Use this as a 5–8 minute demonstration of financial reasoning and reporting controls. Have `output/report.html` open, a recent local test result available, and the evidence pack named by `output/run_status.json`. Prepare `output/restated/report.html` before the interview rather than spending demonstration time rebuilding files.

```powershell
python scripts/run_demo.py
python -m unittest discover -s tests -v
python scripts/run_demo.py --known-at 2026-09-15 --output-dir output/restated
```

## 1. Frame the reporting problem — 45 seconds

“I built this to follow a private-fund report from dated source records through performance measures, partnership accounting and a terminal allocation. A financial total can reconcile while still depending on a delayed valuation or an ambiguous return calculation, so I wanted those review decisions to remain visible.”

Identify the three populations immediately: four fictional comparison funds, a separate fictional Northstar partnership, and independently sourced public research observations. The synthetic comparison index is fictional too. Do not describe Northstar's ledger as the accounting system behind ALPHA, BETA, GAMMA or DELTA.

## 2. Show what was known — 60 seconds

The original report measures June 30, 2026 using information known by August 15. Open ALPHA's valuation record and the withheld-record count. Compare with the September 15 knowledge-cutoff report: the $250,000 call and $400,000 NAV reduction are now available, while the measurement date stays June 30.

“Effective dates answer when a transaction belongs economically. Recorded and publication dates answer when this reporting process could use it. I apply both cutoffs and retain the version identifiers and source hashes.”

Both events are planted examples. Explain that hashes establish input identity; they do not prove that a valuation is economically correct. Show one input reference in the report or JSON evidence.

## 3. Read cash, value and returns together — 75 seconds

Select a comparison fund and distinguish distributions from remaining NAV. Explain DPI, RVPI and TVPI using the same paid-in denominator. Move the NAV haircut slider and point out that only the displayed scenario NAV and multiples change.

Open DELTA's return diagnostics. Its alternating flows keep the primary XIRR unavailable. Candidate roots from a finite log-rate scan are review aids; tangent roots and closely spaced crossings can be missed. Finding a candidate does not authorize choosing it as the fund's reported return.

“XIRR describes dated investor cash flows. PME compares terminalized value against the supplied total-return index. The benchmark-adjusted dated return is a separate annualized diagnostic, not ordinary fund IRR minus benchmark IRR and not a demonstrated risk-adjusted alpha.”

Mention the bounded XIRR domain and seven-calendar-day benchmark lookback. Unavailable NAV or benchmark data remain unavailable. A portfolio multiple comes from summed dollars; an average of fund IRRs is not a portfolio IRR.

## 4. Reconstruct Northstar's economic accounts — 90 seconds

Move to Investor accounts. The facility funds $6m on January 2. A $6.5m contribution on April 1 funds principal repayment, accrued interest and fees. The investment is marked from $6m to $6.6m, then sold for $9m.

Explain the pre-distribution bridge:

```text
Contributions $6,500,000.00 + realized gain $3,000,000.00
− fees $98,630.14 − interest $95,095.89
= cash and investor equity $9,306,273.97
```

Trace the interest accrual and subsequent payment in the event journal. Paying accrued interest reduces cash and the liability; it does not recognize the expense again. The marked investment's gain moves from unrealized to realized on sale, without booking a second gain.

State the identity: cash plus carrying book, less debt and accrued interest, equals total investor capital. Historical investment cost supports the gain classification and is not an additional NAV asset.

## 5. Follow carry into the closing distribution — 60 seconds

Show the linked terminal waterfall: 8% SIMPLE Actual/365 preferred return, 20% carry and a 100% GP catch-up. These are the fictional project's terms. Preferred accrues from the contributed-capital dates; no earlier investor distribution path is modeled in this terminal calculation.

“The GP contributes 2% alongside the other investors. That co-investment receives ordinary investment proceeds. Carry is a separate transfer of economic equity to the GP, and the report distinguishes the two.”

Follow the returned capital, preferred, catch-up and residual tiers into the investor allocation. The closing distribution uses each actual post-carry balance rather than freshly rounding a percentage of fund cash. Check the released evidence for zero closing capital accounts and zero fund equity.

Then show the standalone clawback scenario: its lifetime proceeds already include prior GP carry paid. Comparing that amount with the newly calculated lifetime entitlement produces a true-up; prior carry is not subtracted twice from available proceeds.

## 6. Preserve a failed case and source limits — 60 seconds

Inspect the cash-shortfall scenario. Reducing the contribution to $6m funds principal repayment but leaves no cash for accrued interest. The attempted interest payment fails, the last valid accounts remain inspectable, and the failed result identifies its effective-through date. Those balances cannot be presented as a completed June 30 report.

Briefly contrast the recallable case: a $3m recallable distribution restores capacity, permitting $13m of cumulative calls against $10m original commitments. The recallable counter is cumulative; remaining capacity accounts for calls already made. A regular distribution does not replenish commitments.

Finish on Public research or the warehouse evidence. Identify a public record's measurement date, capture/source version and reported fields, or the visible unavailable-source status. Public cumulative figures cannot reveal the missing dated cash-flow history needed to recalculate a fund's IRR. Open a SQL reconciliation query or investor statement to show how a reviewer can inspect the result outside the dashboard.

## Questions worth preparing

| Question | Explain and demonstrate |
| --- | --- |
| Why can IRR rise while investor wealth falls? | Delaying the capital call shortens the measured holding period. The fixed line illustration includes financing cost and keeps exit cash unchanged. Compare cash profit as well as annualized return. |
| Why withhold DELTA's rate if the scan finds a root? | Mixed signs can create multiple roots. The finite scan does not prove completeness or identify an economically appropriate reporting choice. |
| Why is preferred return not an 8% IRR hurdle? | This fictional contract uses simple dated interest. An IRR hurdle or compounded preferred return would require a different equation and, for interim payouts, a stateful accrual path. |
| Why does the sale not double count the $600,000 mark? | Total gain changes only by proceeds less carrying value; the existing mark is reclassified using disposed historical cost. At full exit, unrealized gain is zero. |
| What happens if an event fails? | Candidate posting occurs on copied balances. Failed cash or capacity checks retain the previous valid journal and identify unposted source events. |
| How do you allocate pennies? | Half-up rounding applies to documented monetary calculations. Largest remainders allocate exact cents deterministically; explicit ending balances close the accounts. |
| What does KS-PME above one establish? | More terminal value relative to that supplied comparison under the calculation assumptions. Benchmark choice, synthetic data and valuation uncertainty limit interpretation. |
| What would you need for a real fund? | Actual agreements, authenticated transaction and valuation histories, validated fee/ownership rules, benchmark vintages, operating controls and reviewer access. Avoid inferring those requirements from public cumulative totals. |

## Know the implementation before presenting it

Be ready to open and explain these code areas:

- `pmcapital/analytics.py`: exact-cent parsing, same-day cash-flow aggregation, the bounded conventional XIRR solver and PME observation selection.
- `pmcapital/return_diagnostics.py`: logarithmic rate grid, crossing refinement, benchmark transformation and review statuses.
- `pmcapital/capital.py`: candidate event posting, ledger identities, accrual intervals, largest-remainder allocation, historical-cost reclassification and commitment capacity.
- `pmcapital/waterfall.py`: simple preferred accrual, the catch-up equation, cash-conserving tier rounding and cumulative GP true-up.
- `pmcapital/pipeline.py` and `pmcapital/advanced.py`: information cutoffs, linked terminal allocation, exports, SQL reconciliation and current-attempt status.
- The public-source module and [Public data](PUBLIC_DATA.md): source versions, unavailable inputs and limits on recalculating reported public returns.

The numerical and workflow checks are documented in [Validation](VALIDATION.md). Use its current evidence rather than memorizing a test count. [Scope](SCOPE.md), [Reporting model](REPORTING_MODEL.md), [Capital methodology](CAPITAL_METHODOLOGY.md), [Waterfall methodology](WATERFALL_METHODOLOGY.md) and [Sources](SOURCES.md) contain the detailed contracts.

## Describe your contribution accurately

“This is my independent portfolio project, built with OpenAI Codex assistance in research, implementation, documentation and verification. I can explain the reporting choices, trace the calculations and reproduce the checks I'm presenting.”

Use that wording only for work you understand and can defend. Identify your actual decisions separately from generated implementation. Do not turn synthetic results into claims of client experience, investment alpha, cost savings or employer impact. The project includes a CSV/SQL reporting handoff and proposed DAX measures; it does not establish a native Power BI deployment, institutional certification or a calibrated investment model.
