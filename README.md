# Private Markets Performance & Capital Lab

A local reporting and economic-accounting system for explaining private-fund cash flows, investor capital, reporting cutoffs and carried interest. The report traces financial results to dated records and preserves unavailable metrics and failed accounting attempts.

The demo contains **four fictional comparison funds and a separate fictional Northstar partnership**. Their financial records and comparison index are synthetic. Public research observations have their own source records and dates; they do not supply the fictional cash flows or calibrate the scenarios.

## Run locally

Use Python 3.11 or later from the repository root. The synthetic demo uses the Python standard library; package installation, credentials and data downloads are unnecessary.

```powershell
python scripts/run_demo.py
python -m unittest discover -s tests -v
```

Open `output/report.html`. The default measurement date is June 30, 2026, with information known by August 15. The report includes fund detail, investor accounts, carry scenarios, return diagnostics, public-source review and reporting controls.

Each completed build creates an evidence pack under `output/runs/` with JSON, CSV, SQLite, a saved report and artifact hashes. `output/run_status.json` identifies the current attempt. A failed build replaces the current report with failure evidence; earlier packs retain their historical status.

Package the saved report, evidence, source code and local inputs for offline review:

```powershell
python scripts/build_release.py
python scripts/verify_release.py
python scripts/verify_portability.py
```

Extract `output/private_markets_capital_lab.zip` and open `START_HERE.html`. Viewing the saved report requires no Python installation. Source rebuild instructions travel with the package.

## What the lab demonstrates

| Workflow | Evidence |
| --- | --- |
| Fund performance | DPI, RVPI, TVPI, dated XIRR, synthetic-index KS-PME and benchmark-adjusted dated-return diagnostics |
| Information cutoffs | Effective versus recorded cash-flow dates; measurement versus publication dates for NAV revisions |
| Partnership accounts | Cash, investment carrying book and historical cost, debt, accrued interest, investor capital, fees and recallable commitment capacity |
| Distribution economics | Fictional European whole-fund preferred return, GP catch-up, residual carry and prior-carry true-up |
| Operational review | Exact-cent accounting, deterministic investor allocations, preserved failed payments, source fingerprints and Python/SQL reconciliation |
| Reporting handoff | Offline HTML, investor statements, event and metric exports, SQLite tables and documented Power BI import measures |

The DELTA comparison fund deliberately alternates calls and distributions. Its conservative XIRR remains `NON_CONVENTIONAL`; a bounded scan displays candidate roots for review without selecting a definitive rate. This makes `REVIEW_REQUIRED` an expected reporting outcome. A finite scan cannot prove that it found every mixed-flow root.

Northstar uses a facility to fund a $6m investment, calls **$6.5m on April 1**, then exits the investment for $9m. At June 30, before the modeled terminal distribution, its economic bridge is:

```text
+$6,500,000.00 contributed capital
+3,000,000.00 realized investment gain
−   98,630.14 management fees
−   95,095.89 facility interest
=9,306,273.97 cash and investor equity
```

The linked terminal case applies an **8% SIMPLE Actual/365 preferred return, 20% carry and 100% GP catch-up**. Contributors share ordinary investment proceeds at fixed commitment weights. The GP's 2% co-investment proceeds and its separate carry allocation remain distinguishable. The closing distribution uses exact post-carry investor balances to avoid creating penny deficits.

Separate cases expose a failed interest payment, restored capacity from recallable distributions and a delayed closing distribution. Four standalone waterfall sensitivities show profitable, low-profit, loss and clawback outcomes.

## Inspect a reporting revision

Keep the original measurement date and include information known by September 15:

```powershell
python scripts/run_demo.py --known-at 2026-09-15 --output-dir output/restated
```

Compare the original report with `output/restated/report.html`. ALPHA gains a $250,000 late-recorded call and a $400,000 downward NAV revision. These planted events illustrate how new information changes a report without changing its economic measurement date.

The NAV haircut slider changes the selected fund's NAV, RVPI and TVPI only. It is a sensitivity calculation; its displayed baseline XIRR and PME are not recomputed.

## Methods and practical limits

All modeled money is USD integer cents. Preferred return and fee calculations use documented half-up rounding; investor allocations use deterministic largest remainders. XIRR uses Actual/365 and a bounded conventional-flow solver. Terminal NAV is a valuation estimate represented as a positive terminal flow for performance calculations.

KS-PME is a terminal-value ratio against a total-return index. Benchmark-adjusted return is the dated return of benchmark-transformed cash flows, with explicit rounding and solver status. Neither the synthetic benchmark nor the public disclosure study establishes investment alpha or forecast accuracy.

Northstar is an economic book model under fixed fictional terms. It excludes tax allocations, changing ownership, a contractual borrowing base, variable-rate debt and stateful interim-distribution preferred accrual. The whole-fund waterfall is a terminal/lifetime cumulative calculation. Prior GP carry is included in lifetime proceeds, and its true-up is shown before tax or collection adjustments.

Public snapshot amounts and reported returns remain source observations. Cumulative public totals cannot reconstruct an independently calculated dated fund IRR. Unavailable public sources stay visible; optional acquisition and source limitations are described in [Public data](docs/PUBLIC_DATA.md).

The project does not claim production readiness, model calibration, GIPS certification or ILPA compliance. The Power BI handoff consists of CSV/SQL structure and documented measures; it does not include a native PBIX file.

## Review the work

| File or guide | Purpose |
| --- | --- |
| [Interview walkthrough](docs/INTERVIEW_WALKTHROUGH.md) | A 5–8 minute demonstration and questions to prepare |
| [Scope](docs/SCOPE.md) | Implemented analytical populations and acceptance boundaries |
| [Reporting model](docs/REPORTING_MODEL.md) | SQLite grains, reconciliation queries and Power BI handoff |
| [Performance methodology](docs/PERFORMANCE_METHODOLOGY.md) | Dated returns, total-return benchmarking, cutoffs and solver limits |
| [Capital methodology](docs/CAPITAL_METHODOLOGY.md) | Economic event ledger, fees, facility, classifications and commitments |
| [Waterfall methodology](docs/WATERFALL_METHODOLOGY.md) | Fictional terms, exact tier equations and true-up contract |
| [Sources](docs/SOURCES.md), [Public data](docs/PUBLIC_DATA.md) | Primary references, source capture and public-observation limits |
| [Validation](docs/VALIDATION.md) | Current numerical, workflow and interface evidence |
| `pmcapital/`, `tests/`, `sql/` | Calculations, controls, tests and reporting queries |

This is an independent portfolio project built with OpenAI Codex assistance in research, implementation, documentation and verification. Present the decisions and calculations you can explain and reproduce. Synthetic results are not employment experience, client work or evidence of employer impact.
