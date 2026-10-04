# Private Markets Performance & Capital Lab

An independent research project that connects private-fund reporting, economic partnership accounts and distribution economics. A reviewer can follow a dated record through Python calculations, investor statements, a SQLite warehouse and an offline report, then inspect the assumptions and unresolved controls.

The workflow combines data ingestion, quality control, lineage, financial calculations and investor reporting. [Primary sources](SOURCES.md) document the reporting and performance references and their implementation limits.

## Delivered system

| Component | Reviewable behavior |
| --- | --- |
| Four-fund performance population | Dated calls/distributions, versioned NAV, separate economic and information cutoffs, DPI/RVPI/TVPI, conservative XIRR and synthetic total-return benchmark comparisons |
| Return diagnostics | Bounded mixed-flow root candidates, explicit unavailable rates, KS-PME and benchmark-adjusted dated returns with documented interpretation limits |
| Northstar partnership population | Event-level cash/investment/debt/interest identities, investor accounts, realized/unrealized classifications, fixed ownership allocations, fees and facility settlement |
| Commitment controls | Calls against available commitments, capacity restored by recallable distributions, and preserved failed economic events |
| Distribution economics | Whole-fund terminal preferred return, catch-up, carry and prior-carry clawback examples under fictional terms |
| Linked exit | Reconciled terminal cash feeds the waterfall; carry is an equity transfer, and exact investor distributions close all accounts |
| Public research population | Governed official-source observations and provenance kept separate from synthetic cash flows and report cutoffs |
| Reporting delivery | Offline HTML, investor statements, journal and metric CSVs, SQLite fact/dimension tables, SQL reconciliation and a documented Power BI import handoff |
| Evidence and reproduction | Input/code/artifact hashes, immutable local run packs, financial/workflow tests, source and methodology guides and portable release |

The four comparison funds, Northstar and public disclosure observations are independent populations. Public cumulative totals cannot reconstruct dated fund cash flows. Neither public observations nor synthetic scenarios establish forecast calibration.

## Analytical review

1. Explain the measurement date and the information cutoff. Admit a late-recorded call and a NAV revision by moving only the information cutoff.
2. Inspect the comparison funds and explain why DELTA's alternating flows retain an unavailable conventional XIRR despite diagnostic candidate roots.
3. Trace Northstar's $6.5m contribution, $3m realized investment gain, management fees and facility interest to $9,306,273.97 of terminal cash and investor equity.
4. Apply the fictional 8% simple Actual/365 preferred return, 20% carry and 100% catch-up. Show that carry transfers equity and the final distribution closes every account to zero cents.
5. Compare profitable, low-profit, loss and clawback waterfalls; inspect the recallable-capacity and failed-payment cases.
6. Reconcile the saved warehouse, inspect public-source dates and hashes, and open the portable evidence package.

OpenAI Codex assisted with research, implementation, documentation and verification. The methodology guides identify the assumptions and calculation boundaries.

## Boundaries and extensions

The complete acceptance scope is in [SCOPE.md](SCOPE.md). This is a local research and economic-accounting system under fixed fictional terms. It is not an institutional accounting certification or a legal interpretation of a partnership agreement. It does not claim ILPA/GIPS compliance, production access controls, calibrated investment forecasts or actual client results.

The deliverable includes a portable reporting model and documented Power BI measures. A native PBIX was not authored or validated in Power BI. Proprietary dated private-fund histories, institution-specific fee/waterfall terms, paid benchmark licensing and a production operating environment were unavailable. Those would support future calibration, changing ownership, tax/FX allocations, variable facility terms, interim distribution accrual and scheduled deployment.

Public-source availability and field-level evidence limits are documented in [PUBLIC_DATA.md](PUBLIC_DATA.md). Current validation evidence is in [VALIDATION.md](VALIDATION.md).
