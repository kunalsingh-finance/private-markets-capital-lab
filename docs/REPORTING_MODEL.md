# Warehouse and Power BI handoff

Each successful run has an immutable local evidence pack. `warehouse.sqlite` records a single reporting/knowledge cutoff; `run_status.json` points to the currently valid pack. A failed attempt replaces current status and report with failure evidence. Earlier packs describe earlier successful attempts only.

## Tables and relationships

| Dimension / context | Fact | Key / grain |
| --- | --- | --- |
| `funds` | `cashflows` | Fund ID; one dated source cash-flow event |
| `funds` | `valuations` | Fund ID; valuation date and published version |
| `funds` | `performance_metrics` | Fund ID; one selected reporting result |
| `dim_investor` | `fact_capital_statement` | Investor ID; one terminal capital statement |
| Standalone partnership | `fact_accounting_event` | Event ID; one posted economic or accrual event |
| Waterfall scenario | `fact_waterfall_tier` | Scenario ID and tier order; one modeled allocation tier |
| Public source | `source_observation` | Separate public observation JSON; never a synthetic fund join |
| `reporting_context` | Entire pack | One measurement date, knowledge cutoff and run identity |

The four-fund comparison and partnership case are different analytical populations. Joining them on an invented common fund key would misstate the evidence. The public disclosure study is a third population with its own dates and source semantics.

Run the independent reconciliation examples in [reporting_queries.sql](../sql/reporting_queries.sql). The persisted SQL cash summary is checked against Python before report publication; investor accounts are checked against fund equity before the warehouse is accepted.

## Power BI import

Import the selected pack's fund, performance, investor and statement CSV files into Power BI Desktop. Use one-to-many, single-direction relationships from `funds[fund_id]` to `fund_metrics[fund_id]`, and from `dim_investor[investor_id]` to `investor_statements[investor_id]`. Avoid mixing multiple run folders without adding the run identity to the fact grain. Set cents columns to whole number and divide by 100 in currency measures. Keep explicit unavailable-metric flags; blank NAV is not zero NAV.

Suggested measures (the CSV column names below match the exported files):

```dax
Paid In USD = DIVIDE(SUM(fund_metrics[paid_in_cents]), 100)
Distributed USD = DIVIDE(SUM(fund_metrics[distributed_cents]), 100)
NAV USD =
    IF(COUNT(fund_metrics[nav_cents]) = COUNTROWS(fund_metrics),
       DIVIDE(SUM(fund_metrics[nav_cents]), 100), BLANK())
DPI = DIVIDE([Distributed USD], [Paid In USD])
TVPI = IF(NOT ISBLANK([NAV USD]),
          DIVIDE([Distributed USD] + [NAV USD], [Paid In USD]), BLANK())
Investor Capital USD = DIVIDE(SUM(investor_statements[capital_cents]), 100)
```

Display fund IRRs individually with their solver statuses. Do not average fund IRRs to invent a portfolio IRR; calculate a portfolio rate from aggregated dated cash flows if that population and method are explicitly defined. Public snapshot reported IRRs remain source figures and cannot be independently recomputed from cumulative totals.

The portable CSV/SQL semantic handoff is implemented. Native Power BI authoring, a PBIX binary, refresh service and access permissions are outside this local runtime. The DAX measures are a documented handoff and have not been executed in Power BI; the corresponding aggregate arithmetic is verified in Python and SQL.

Primary product reference: [Microsoft Power BI star-schema guidance](https://learn.microsoft.com/en-us/power-bi/guidance/star-schema). The relationship design is a project-specific application of that guidance.
