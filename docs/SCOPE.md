# Full project acceptance scope

The deliverable is a local, reproducible research and investor-reporting system, with an integrated fictional partnership case and separately governed public observations.

| Module | Completion evidence |
| --- | --- |
| Dated performance | DPI/RVPI/TVPI, conservative XIRR, bounded mixed-flow root diagnostics, total-return PME and benchmark-adjusted dated-return diagnostics with explicit limitations |
| Partnership accounting | Dated event ledger, cash/investment/debt/interest balance identities, investor capital accounts, deterministic cent allocations, fees, facility use and settlement, commitments and recallable distributions |
| Distribution economics | Documented fictional European cumulative waterfall, preferred return, catch-up, carried interest, prior-carry true-up/clawback and cash conservation |
| Integrated exit case | Reconciled partnership balances feed a terminal waterfall and investor allocation; resulting investor accounts reconcile to fund equity |
| Public research | Official public-pension snapshot observations, source/version provenance, summary metrics and explicit limits on deriving dated returns; source acquisition utilities where supported |
| Reporting and warehouse | Offline investor report, controlled case comparisons, investor statements, event/metric CSVs, SQLite fact/dimension tables, source provenance, semantic reporting queries and documented Power BI import measures |
| Review and reproduction | Financial tests, independent cross-module review, browser interaction checks, clean local rebuild, source/methodology documentation |

The synthetic partnership is distinct from the four-fund comparison fixture. Public research records do not enter synthetic cash flows or masquerade as calibrated forecasts. The repository includes the completed source and data fixtures. Website deployment, production account setup, institution-specific legal conclusions and investment transactions remain outside the scope.

Scheduling, production access control, institutional certification, paid market data and proprietary private-fund cash-flow calibration require a different operating environment or unavailable data. Their absence must be documented rather than represented as implemented. A portable warehouse/reporting model is included; a native Power BI binary is conditional on an available supported authoring environment.
