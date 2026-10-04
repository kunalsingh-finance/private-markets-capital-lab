# Primary sources and evidence limits

Research accessed October 2, 2026. These sources inform the methodology notes. The four comparison funds, the Northstar partnership and their benchmark inputs are synthetic. Official public-pension observations form a separately governed research population; their capture and use are documented in [PUBLIC_DATA.md](PUBLIC_DATA.md).

## ILPA Performance Template

[Institutional Limited Partners Association — Performance Template](https://ilpa.org/industry-guidance/templates-standards-model-documents/ilpa-templates-hub/ilpa-performance-template/)

The official page describes a framework for standardizing private-equity performance calculations and reporting corresponding contributions and distributions. It distinguishes granular and gross-up methodologies. It states that the template should be used prospectively for funds beginning operations on or after January 1, 2026. The page was retrieved directly.

Project implication: use explicit metric definitions and cash-flow mapping, and describe the prototype's narrower scope. This is a reporting reference, not a claim that the prototype reproduces the workbook or satisfies ILPA reporting standards.

## CalPERS private-equity disclosure

[CalPERS — Private Equity Program (PEP) Fund Performance Review](https://www.calpers.ca.gov/investments/about-investment-office/investment-organization/pep-fund-performance?source=post_page---------------------------)

The official public-pension page describes a quarterly table of active partnership investments. It defines fund/vintage and commitment/contribution fields, and explains that general partners have 120 days to provide financial data, creating a typical reporting delay. It emphasizes considering both IRR and investment multiples. The official page was observed through indexed search content; direct retrieval of the canonical URL failed in the research tool.

Project implication: distinguish measurement dates from information-availability dates and show realized and remaining value separately. No fund-level CalPERS values were copied into the calculation dataset. Public summary amounts do not substitute for complete dated cash flows and cannot establish an independently recalculated IRR.

## Microsoft XIRR

[Microsoft Support — XIRR function](https://support.microsoft.com/en-us/excel/functions/xirr-function)

Microsoft documents XIRR for irregularly dated cash flows, a 365-day basis, the requirement for both positive and negative values, and the connection to a zero of XNPV. Its iterative calculation can fail to find a result. The official reference includes a worked example useful for numerical validation.

Project implication: use dated cash flows and return a solver status and residual. Matching a documented example is a targeted numerical check, not proof of identical behavior to Excel for every input, root or starting guess.


## Kaplan–Schoar public-market equivalent

[Kaplan and Schoar — Private Equity Performance: Returns, Persistence and Capital Flows, NBER Working Paper 9807](https://www.nber.org/papers/w9807), [MIT publication record](https://dspace.mit.edu/entities/publication/61c18b55-ac0b-4a13-b7a0-db709cd723c5)

The primary research is the reference for the Kaplan–Schoar public-market-equivalent comparison. The prototype's basic implementation grows each eligible contribution and distribution to the same terminal date using a supplied synthetic index; it compares terminalized distributions plus selected NAV against terminalized contributions. This is a multiple, not an annualized rate or a complete risk adjustment. The MIT publication record was retrieved directly and NBER's indexed record confirmed the authors, working-paper number and June 2003 issue date; direct NBER page retrieval returned an access restriction.

Project implication: expose the comparator and distinguish synthetic-index PME from actual benchmark analysis. The project also implements a benchmark-adjusted dated-return diagnostic. Calibrated investable benchmark results and other PME variants remain outside the current scope.


## Research-to-implementation boundary

The design applies reporting-methodology references within the stated research scope. Sources do not endorse this code, validate synthetic assumptions or establish full accounting/compliance coverage. Implemented economic accounting, waterfalls, return diagnostics and public-source controls are described in their methodology guides. Real private-fund calibration remains unavailable.

## Benchmark-adjusted return reference

[Gredil, Griffiths and Stucke — Direct Alpha Method author repository](https://github.com/orgredil/Direct-Alpha-Method/blob/main/README.md), [Journal of Corporate Finance paper](https://doi.org/10.1016/j.jcorpfin.2023.102360)

The authors describe an IRR-based public-market adjustment and reference implementations. This lab uses the discrete dated IRR of benchmark-transformed cash flows rounded to cents. It labels that result a benchmark-adjusted dated return, distinguishes it from the reported conventional fund IRR and does not claim risk-adjusted investment alpha or exact equivalence to every published implementation.

## Accounting and reporting references

See [CAPITAL_METHODOLOGY.md](CAPITAL_METHODOLOGY.md) and [WATERFALL_METHODOLOGY.md](WATERFALL_METHODOLOGY.md) for the fictional agreement, allocation rules and reference boundaries. See [REPORTING_MODEL.md](REPORTING_MODEL.md) for the Microsoft star-schema reference and the unexecuted Power BI handoff. Source guidance informs structure; it does not certify the lab.
