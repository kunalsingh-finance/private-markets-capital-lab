# Primary sources and evidence limits

Research accessed October 2, 2026. These sources informed project selection and methodology notes. The four comparison funds, the Northstar partnership and their benchmark inputs are synthetic. Official public-pension observations form a separately governed research population; their capture and use are documented in [PUBLIC_DATA.md](PUBLIC_DATA.md). Employer descriptions are evidence of requested work, not claims of a currently available job or this candidate's eligibility.

## ILPA Performance Template

[Institutional Limited Partners Association — Performance Template](https://ilpa.org/industry-guidance/templates-standards-model-documents/ilpa-templates-hub/ilpa-performance-template/)

The official page describes a framework for standardizing private-equity performance calculations and reporting corresponding contributions and distributions. It distinguishes granular and gross-up methodologies. It states that the template should be used prospectively for funds beginning operations on or after January 1, 2026. The page was retrieved directly.

Project implication: use explicit metric definitions and cash-flow mapping, and describe the prototype's narrower scope. This is a reporting reference, not a claim that the prototype reproduces the workbook or satisfies ILPA reporting standards.

## CalPERS private-equity disclosure

[CalPERS — Private Equity Program (PEP) Fund Performance Review](https://www.calpers.ca.gov/investments/about-investment-office/investment-organization/pep-fund-performance?source=post_page---------------------------)

The official employer-independent public-pension page describes a quarterly table of active partnership investments. It defines fund/vintage and commitment/contribution fields, and explains that general partners have 120 days to provide financial data, creating a typical reporting delay. It emphasizes considering both IRR and investment multiples. The official page was observed through indexed search content; direct retrieval of the canonical URL failed in the research tool.

Project implication: distinguish measurement dates from information-availability dates and show realized and remaining value separately. No fund-level CalPERS values were copied into the calculation dataset. Public summary amounts do not substitute for complete dated cash flows and cannot establish an independently recalculated IRR.

## Microsoft XIRR

[Microsoft Support — XIRR function](https://support.microsoft.com/en-us/excel/functions/xirr-function)

Microsoft documents XIRR for irregularly dated cash flows, a 365-day basis, the requirement for both positive and negative values, and the connection to a zero of XNPV. Its iterative calculation can fail to find a result. The official reference includes a worked example useful for numerical validation.

Project implication: use dated cash flows and return a solver status and residual. Matching a documented example is a targeted numerical check, not proof of identical behavior to Excel for every input, root or starting guess.

## Neuberger private-markets data role

[Neuberger Berman — Private Markets Data Analyst/Senior Associate, R0012091](https://nb.wd1.myworkdayjobs.com/en-US/NBCareers/job/New-York-NY/Private-Markets-Data-Analyst-Senior-Associate_R0012091)

The official ATS description identifies New York, NY and displayed a relative posting age of over 30 days; an exact publication date was not verified. It requests end-to-end investment/portfolio data oversight, acquisition and ingestion, quality control, aggregation and analytical reporting. It describes performance KPIs, governance rules and lineage, with SQL/database and Python experience strongly preferred. It also mentions Excel, visualization tools and ETL workflows. Indexed official content supplied the description; direct retrieval returned a JavaScript page without extractable text.

Project implication: demonstrate ingestion, quality controls, financial KPIs, provenance and communication together. Do not label this role newly posted or available based on the indexed description. The description includes work-authorization and experience conditions; this research did not evaluate candidate eligibility.

## Kaplan–Schoar public-market equivalent

[Kaplan and Schoar — Private Equity Performance: Returns, Persistence and Capital Flows, NBER Working Paper 9807](https://www.nber.org/papers/w9807), [MIT publication record](https://dspace.mit.edu/entities/publication/61c18b55-ac0b-4a13-b7a0-db709cd723c5)

The primary research is the reference for the Kaplan–Schoar public-market-equivalent comparison. The prototype's basic implementation grows each eligible contribution and distribution to the same terminal date using a supplied synthetic index; it compares terminalized distributions plus selected NAV against terminalized contributions. This is a multiple, not an annualized rate or a complete risk adjustment. The MIT publication record was retrieved directly and NBER's indexed record confirmed the authors, working-paper number and June 2003 issue date; direct NBER page retrieval returned an access restriction.

Project implication: expose the comparator and distinguish synthetic-index PME from actual benchmark analysis. The project also implements a benchmark-adjusted dated-return diagnostic. Calibrated investable benchmark results and other PME variants remain outside the current scope.

## BlackRock client-platform reporting role: historical evidence

[BlackRock — Analyst/Associate, Client Platform Analytics & Reporting, R252975](https://careers.blackrock.com/job/atlanta/analyst-associate-client-platform-analytics-and-reporting-atlanta-seattle/45831/80725959520)

The official indexed description lists Atlanta, Georgia with Seattle as an additional location and a June 10, 2025 posting date. It asks for quarterly reporting packages, validation and aggregation of data, performance/exposure/flow analysis, track-record updates, and automation of recurring client-service activities. VBA or Python is a plus.

Project implication: make an investor-facing report with clear metrics and data-quality evidence. This posting is explicitly historical market evidence; the project does not assert vacancy freshness, active hiring or candidate eligibility.

## Research-to-implementation boundary

The recommendation combines employer descriptions with reporting-methodology references. That synthesis is the project's design judgment. Sources do not promise employment outcomes, endorse this code, validate synthetic assumptions or establish full accounting/compliance coverage. Implemented economic accounting, waterfalls, return diagnostics and public-source controls are described in their methodology guides. Real private-fund calibration remains unavailable.

## Benchmark-adjusted return reference

[Gredil, Griffiths and Stucke — Direct Alpha Method author repository](https://github.com/orgredil/Direct-Alpha-Method/blob/main/README.md), [Journal of Corporate Finance paper](https://doi.org/10.1016/j.jcorpfin.2023.102360)

The authors describe an IRR-based public-market adjustment and reference implementations. This lab uses the discrete dated IRR of benchmark-transformed cash flows rounded to cents. It labels that result a benchmark-adjusted dated return, distinguishes it from the reported conventional fund IRR and does not claim risk-adjusted investment alpha or exact equivalence to every published implementation.

## Accounting and reporting references

See [CAPITAL_METHODOLOGY.md](CAPITAL_METHODOLOGY.md) and [WATERFALL_METHODOLOGY.md](WATERFALL_METHODOLOGY.md) for the fictional agreement, allocation rules and reference boundaries. See [REPORTING_MODEL.md](REPORTING_MODEL.md) for the Microsoft star-schema reference and the unexecuted Power BI handoff. Source guidance informs structure; it does not certify the lab.
