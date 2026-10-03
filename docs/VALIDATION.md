# Validation — October 2, 2026 (America/New_York)

The complete local project passed **111 Python unittest tests**. The verified ZIP was extracted to a clean temporary folder, where the same 111 tests passed. Its source rebuilt the saved report with identical financial JSON evidence; only the new run identity and build timestamp differed. The portable check also reconciled three investor statements, twelve posted event identities and four waterfall scenarios against the rebuilt SQLite warehouse.

## Financial and workflow evidence

| Area | Checks |
| --- | --- |
| Performance | Analytical positive/negative/zero XIRR, Actual/365 leap days, same-date netting, sign-pattern rejection, bounded rates, exact-cent parsing and capital-weighted multiples |
| Benchmarking | Total-return scaling invariance, exact terminal-value PME, inclusive seven-day prior-only lookup, unavailable benchmark handling, known 10%/20% mixed roots and a benchmark-matched zero adjusted return |
| Accounting | Cash/investment/debt/interest identities, fee/accrual amounts, penny allocations, historical cost, marked/partial/full exits, realized/unrealized reclassification, carry transfers, exact closure and investor-specific recallable capacity |
| Economic failures | Cash shortfalls, borrowing limits, overpayments, excluded financing events and preserved last-valid evidence; a failed primary accounting result blocks the current reporting attempt |
| Waterfalls | Capital/preferred boundaries, full/partial/split catch-up, residual allocation, prior-carry true-up, half-cent rounding, contribution-splitting invariance, leap days and cash conservation |
| Public research | Strict generated HTML fixtures, exact typed amounts/nulls, immutable snapshot digest/path checks, dollar-weighted complete-row cohorts, timezone-aware capture ordering and no fabricated fallback |
| Reporting | Original/revised knowledge cutoffs, missing exact-asof NAV, Python/SQL reconciliation, missing event/tier rejection, current-report invalidation and historical-pack retention |
| Packaging | Changed inputs/code, tampered artifacts, unsafe paths, missing entrypoints, raw-source exclusions and preservation of an earlier verified ZIP after a failed packaging attempt |

An independent reviewer also checked the waterfall against 10,000 randomized boundary cases and reviewed the cross-module equations. These checks establish consistency within the documented fictional rules, rather than real-fund calibration or institutional compliance.

## Saved default result

The comparison population contains four synthetic funds, 18 of 19 source cash flows and five of six valuation versions eligible by August 15, 2026. Measurement remains June 30. Total commitments are $22m, paid-in $12.6m, distributions $6.65m, NAV $9.55m and simplified remaining commitment $9.4m.

`REVIEW_REQUIRED` is intentional: DELTA's alternating cash-flow signs keep its conventional XIRR unavailable. A finite diagnostic scan observes a candidate near 10.267%; it neither establishes uniqueness nor releases that candidate as the fund's canonical rate. Other calculable measures remain visible.

The independent Northstar partnership contributes $6.5m, realizes $3m of investment gain and expenses $98,630.14 of fees and $95,095.89 of interest. Its predistribution cash and investor equity are **$9,306,273.97**. Investment carrying value, historical cost, debt and accrued interest are zero. The linked carry allocation is a transfer within equity; the final cash distribution closes all three investor accounts exactly to zero. The GP's short-period carry-inclusive annualized return exceeds the bounded solver domain, so its dated IRR remains `OUT_OF_RANGE` and unavailable.

The separate recallable case has $13m cumulative calls supported by $10m original commitments plus $3m recallable distributions. The cash-shortfall scenario deliberately fails its interest payment and preserves last-valid balances. The separate delayed-distribution case closes every account under its own later dates. These scenario outcomes do not replace the main reporting cutoff.

A September 15 knowledge cutoff admits ALPHA's additional $250,000 call and selects its $400,000 downward NAV revision while retaining the June 30 measurement date. The restated output was rebuilt successfully.

## Source and interface evidence

The public population contains three actual first-page CalSTRS observations measured June 30, 2025 and captured October 3, 2026 at 03:23:46 UTC (October 2 in New York). An independent source review verified the headings and values. Two rows support calculated TVPI; Advent's printed market-value dash remains unavailable. Reported IRRs are source observations, and reported multiples/independently calculated XIRR/PME remain unavailable. The saved hash identifies the derived JSON, not original PDF bytes. Coverage and publication/raw-hash limits are explicit in [PUBLIC_DATA.md](PUBLIC_DATA.md).

Browser verification in Codex's in-app browser checked fund selection, a one-point DELTA NAV haircut ($900,000 to $891,000, displayed TVPI 1.25x to 1.24x), preserved IRR status, and the clawback selector showing $300,000 due with $780,876.71 preferred unpaid. The failed-payment disclosure, investor statements and public-source measurement/retrieval evidence rendered successfully. Dark mode was checked and returned to light mode. No console warnings or errors were observed during these interactions.

Desktop layout was checked at a 1280-pixel viewport and the investor report at 390 by 844 pixels. The page had no horizontal overflow at either checked width; wide financial tables scroll within their own containers. This is limited responsive verification, not an exhaustive browser/accessibility certification. A representative desktop screenshot is saved at `output/report_preview.jpg`.

The release contains thirteen hashed evidence artifacts and nine exact source inputs (four comparison CSVs, four partnership JSON cases and one derived public snapshot). It includes source, tests, methodologies, SQL queries and the interview walkthrough. Power BI measures remain a documented handoff; no native PBIX or DAX execution is claimed. The optional downloader was not used to produce the public observations.

## Reproduce

```powershell
python -m unittest discover -s tests -q
python scripts/run_demo.py
python scripts/verify_reporting.py
python scripts/build_release.py
python scripts/verify_release.py
python scripts/verify_portability.py
python scripts/run_demo.py --known-at 2026-09-15 --output-dir output/restated
```

The source rebuild uses only the Python standard library and included inputs. Test success does not establish actual investment performance, production operations, GIPS/ILPA compliance, employment experience or an interview outcome.
