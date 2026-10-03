# Governed public-pension observations

The project includes three observed rows from the official [CalSTRS Private Equity Portfolio Performance disclosure](https://www.calstrs.com/files/6765c6592/CalSTRSPrivateEquityPerformanceReportFYE2025.pdf). The first page explicitly states **June 30, 2025** as its measurement date. The research browser retrieved the official PDF text on **October 3, 2026 at 03:23:46 UTC**. This is a separate current research observation; it is not information available at the synthetic engine's earlier reporting cut-off.

The included normalized JSON is **DERIVED_OFFICIAL_OBSERVATIONS**: three hand-transcribed rows verified against the official PDF text extraction, with page/row evidence. It is not a saved copy of the original PDF bytes. The SHA-256 in the research summary identifies the exact normalized JSON file. The original PDF byte hash and the source publication date are explicitly unavailable. A retrieval timestamp is not a publication date.

## Captured scope

The sample contains ACON Equity Partners 3.5, ACON Equity Partners IV, and Advent Central & Eastern Europe IV. It is the first three data rows on page 1 of a nine-page document, selected to verify the workflow and missing-value treatment. It is not representative of the pension's full portfolio and is not a complete acquisition of that disclosure.

The source reports fund names, vintages, commitments, contributions, distributions, market values and since-inception IRRs. Amounts were transcribed in dollars and normalized to integer cents. Reported IRR percentages were normalized to decimal rates; parentheses indicate a negative reported rate. A printed dash in market value remains null rather than being assumed zero.

The CalSTRS table does not publish an investment multiple in these columns. The project can calculate DPI and, when contributions, distributions and market value are present, RVPI and TVPI from observed totals. It cannot compare those calculations with a source-reported multiple here, so `reported_multiple`, `multiple_difference` and that reconciliation remain unavailable. A schema and parser support such a comparison for a source that actually publishes the field, using an explicit prototype review band of 0.05x. That band does not infer source precision or certify identical methodologies.

The source's footnote also cautions that reported IRRs depend on accounting/timing treatment and interim valuations. The project keeps reported IRRs as observations. **It does not reconstruct capital-call dates, independently recalculate those IRRs, calculate PME from summary totals, or calibrate a dated return model to invented histories.**

## Reproducibility and schema

`public_research_summary(project_root)` reads `data/public_research/*.json`, validates the normalized rows and derived measures, checks the internal records digest, and verifies the content-addressed filename against the file's actual bytes. It returns:

| Key | Content |
| --- | --- |
| `status` | `AVAILABLE_PARTIAL` for installed observations; `UNAVAILABLE` when none are installed |
| `records` | Selected typed rows, source IDs, measurement dates and snapshot paths |
| `provenance` / `snapshots` | File path, exact derived-file SHA-256, URL, retrieval time, measurement date, capture method, coverage and selected-version flag |
| `cohort_metrics` | Vintage and all-captured totals and dollar-weighted TVPI using only rows with complete multiple inputs; explicit count of complete rows |
| `limitations` | Missing cash-flow histories, incomplete coverage, reported-only IRR, missing-value and information-cut-off boundaries |

Older snapshots are retained as immutable versions. Only the newest measurement date for each source enters the displayed research records; captures of that date are ordered by actual timezone-aware retrieval instant. Historical versions remain in provenance. Cohort ratios describe complete rows in the captured sample, not a pension return; missing NAV rows are excluded from the multiple's numerator **and denominator** and counted separately.

## Optional acquisition utility

The included observations came from the research browser. The optional standard-library downloader was **not executed** to create them. A sandboxed download attempt could not open a socket; its escalation was interrupted. An independent request also encountered a CalPERS access restriction. No blocked source was bypassed and no raw byte hash is claimed for the installed observation file.

Run one explicitly chosen source when network access and source terms permit:

```powershell
python scripts/acquire_public_data.py --source calstrs_fye2025
```

This captures bounded original PDF bytes and an acquisition manifest under `output/public_sources/`, with URL, actual retrieval time and raw-byte hash. It reports `RETRIEVED_RAW_ONLY`: the utility has no PDF-table extraction library and will not invent normalized rows from undecoded bytes. Keep raw source artifacts local and excluded from publication/packaging unless their redistribution is separately cleared.

A strict HTML-table parser is also available for the allowlisted CalPERS print source. It requires a single explicit as-of heading, known column names and an explicit amount scale; it fails on missing fields or layout changes. Its tests use generated HTML labeled as synthetic fixtures, never purported official observations. The actual CalPERS print layout and unit scale have not been successfully downloaded or validated in this task; the optional adapter is unverified against that live source and may reject it.

The allowlist controls acquisition targets. The utility makes one request without credentials, impersonation, private identity information, retries, or access-control workarounds. A successful raw download does not by itself establish successful normalization or complete source coverage.
