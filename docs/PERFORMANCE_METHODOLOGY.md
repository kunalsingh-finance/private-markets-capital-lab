# Performance calculations and release limits

This guide describes `pmcapital/analytics.py`, `return_diagnostics.py` and the comparison-fund selection in `pipeline.py`. The four comparison funds and their total-return index are synthetic. Northstar's separate economic ledger is documented in [CAPITAL_METHODOLOGY.md](CAPITAL_METHODOLOGY.md); public observations have separate source controls in [PUBLIC_DATA.md](PUBLIC_DATA.md).

## Amounts and multiples

USD inputs are parsed as exact nonnegative integer cents. Fractional cents, nonfinite values, negatives and amounts above the signed 64-bit cents limit are rejected. Decimal coefficients and exponents are inspected directly, avoiding silent rounding under a Decimal arithmetic context. Cash totals remain integers; ratios, index-scaled amounts and numerical return solving use floating-point arithmetic. Display rounding does not change source amounts.

For selected calls `C`, distributions `D` and eligible terminal NAV `V`:

| Measure | Definition | Interpretation |
| --- | --- | --- |
| DPI | `D / C` | Cash returned per dollar contributed. |
| RVPI | `V / C` | Remaining reported value per dollar contributed. |
| TVPI | `(D + V) / C` | Total realized and remaining value per dollar contributed. |

Zero paid-in capital returns unavailable multiples, rather than infinity. NAV is an estimate, not a cash receipt. For a shared eligible portfolio population, aggregate multiples use summed amounts: portfolio TVPI is `sum(D + V) / sum(C)`. This equals a paid-in-capital-weighted fund multiple; an unweighted average can give small funds disproportionate influence. Missing NAV requires a coverage disclosure and cannot be silently treated as zero.

The comparison commitment model uses `commitment - cumulative calls`, with no recycling or recallable distributions. A negative remainder is retained and flagged. These simplified metrics do not reconstruct a complete fee/carry bridge or establish a reporting-standard certification. The [ILPA Performance Template](https://ilpa.org/industry-guidance/templates-standards-model-documents/ilpa-templates-hub/ilpa-performance-template/) informs the distinction between cash-flow mapping and performance reporting.

## Economic and information cutoffs

`asof` is the measurement date; `known_at` is the information cutoff. A cash flow is eligible only when its effective date is on/before `asof` and recorded date is on/before `known_at`. NAV records must similarly satisfy valuation date on/before `asof` and publication date on/before `known_at`.

Among eligible NAV records, the pipeline selects the latest valuation date, then its latest published version. Terminal performance requires that valuation date to equal `asof` exactly. A missing or stale NAV withholds RVPI, TVPI, XIRR, KS-PME and both return diagnostics. DPI can remain available from selected calls and distributions. The source valuation ID and dates remain visible even when a stale valuation is withheld from calculations.

Changing the knowledge cutoff can legitimately change a historical report when a late cash flow or NAV revision becomes available. Excluded records are counted, rather than silently backfilled. This reflects the reporting-delay distinction described by [CalPERS' private-equity disclosure](https://www.calpers.ca.gov/investments/about-investment-office/investment-organization/pep-fund-performance?source=post_page---------------------------); it does not reconstruct an actual fund's information history.

## Dated IRR and mixed-flow diagnostics

Calls are negative LP cash flows, distributions positive, and selected NAV a positive terminal value at `asof`. Same-date amounts are netted and zero amounts removed before sign analysis. The Actual/365 discrete annual rate `r` solves:

```text
sum(CF[t] / (1 + r) ** (actual_days_from_first_flow[t] / 365)) = 0
```

The primary solver accepts exactly one negative-to-positive sign change across at least two distinct nonzero dates. It brackets and bisects in `log(1 + r)` over annual rates from -99.99% through 10,000%. Its rate and cent-denominated NPV residual are reported together. The [Microsoft XIRR reference](https://support.microsoft.com/en-us/excel/functions/xirr-function) supports irregular dates and the 365-day basis; this implementation does not promise identical Excel results for every root or starting guess.

| Primary status | Meaning |
| --- | --- |
| `OK` | A supported conventional root was found in the bounded domain. |
| `UNDEFINED` | Insufficient distinct nonzero dates or no positive/negative pair. |
| `NON_CONVENTIONAL` | The netted sign pattern is outside the conservative primary solver. |
| `OUT_OF_RANGE` | No supported bracketed result is available in the numerical domain. |
| `UNAVAILABLE` | The pipeline withheld terminal performance because NAV was unavailable. |

Alternating calls and distributions can be economically valid. `root_diagnostics` preserves review status while scanning the same finite domain for sampled sign crossings and exact sampled zeros. Its default grid has 4,096 intervals plus an explicit zero-rate sample. A supported conventional result is certified by its sign pattern; mixed-flow candidates are never certified as globally unique. Tangent roots, closely spaced crossings and roots outside the domain can be missed. One observed candidate or no observed crossing is therefore a diagnostic observation, not proof that every possible root was found. Candidates do not replace the withheld primary fund IRR.

## KS-PME and benchmark-adjusted dated return

Let `M[t]` be a positive total-return index and `T` the terminal date. Each cash flow is valued to the terminal index level using `M[T] / M[t]`:

```text
KS-PME = (sum(distribution[t] * M[T] / M[t]) + NAV[T])
         / sum(call[t] * M[T] / M[t])
```

This is a multiple, not an annualized return. A value above one indicates greater terminal value than the supplied comparison, subject to the cash-flow, NAV and benchmark assumptions. The primary reference is [Kaplan and Schoar, NBER Working Paper 9807](https://www.nber.org/papers/w9807), with its [MIT publication record](https://dspace.mit.edu/entities/publication/61c18b55-ac0b-4a13-b7a0-db709cd723c5).

At every flow and terminal date, only the latest observation on/before that date may be used. The default maximum lag is seven calendar days, inclusive. Future observations, interpolation and older fills are not used. Missing timely levels or a zero contribution denominator make PME unavailable. Duplicate dates, nonfinite levels and nonpositive levels are invalid. KS-PME retains floating-point scaled amounts without per-flow cent rounding.

The benchmark-adjusted diagnostic transforms each call and distribution by the same terminal index ratio but retains its original cash-flow date. Each transformed amount is rounded HALF_UP to integer cents; unchanged terminal NAV is then appended. The primary dated-IRR solver and mixed-flow diagnostic operate on that transformed series. Its result is a discrete annual benchmark-adjusted dated return, not the difference between fund IRR and index return, a continuously compounded alpha, or a risk-adjusted estimate. Cent rounding can alter very small flows and resulting roots. No contributions and unavailable benchmarks have separate statuses.

The [Direct Alpha author repository](https://github.com/orgredil/Direct-Alpha-Method/blob/main/README.md) and [Journal of Corporate Finance paper](https://doi.org/10.1016/j.jcorpfin.2023.102360) inform the transformation. The lab's rounded discrete diagnostic is explicitly narrower than claiming equivalence to every published implementation.

## Evidence boundary

A price-only index is not a substitute for the modeled total-return series. The supplied index is fictional and has no separately modeled knowledge/version timestamps. Cash-flow and NAV information cutoffs therefore do not establish historical availability of an actual investable benchmark. Neither KS-PME nor the adjusted return demonstrates real investment outperformance, calibrated alpha or a validated forecast.

Release status reflects configured controls. `REVIEW_REQUIRED` can arise from a supported methodological limitation, including DELTA's alternating cash flows, rather than incorrect records. Builds retain source fingerprints, metric statuses and historical evidence packs. A failed build replaces the current report and manifest with a failure state; an earlier successful pack does not validate the failed attempt. Primary-source provenance and broader research limits are collected in [SOURCES.md](SOURCES.md).
