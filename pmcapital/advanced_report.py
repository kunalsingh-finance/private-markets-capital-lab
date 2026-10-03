"""Investor/accounting panels embedded in the portable LP research report."""

from html import escape


def _text(value):
    return escape(str(value if value is not None else "—"), quote=True)


def _money(value):
    return "—" if value is None else ("-" if value < 0 else "") + f"${abs(value) / 100:,.2f}"


def _multiple(value):
    return "—" if value is None else f"{value:.2f}x"


def _table(headers, rows):
    return '<div class="tablewrap"><table><thead><tr>' + "".join("<th>" + _text(header) + "</th>" for header in headers) + '</tr></thead><tbody>' + "".join('<tr>' + "".join('<td>' + _text(value) + '</td>' for value in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def render_advanced_report(payload: dict) -> str:
    advanced = payload.get("advanced")
    if not advanced:
        return ""
    capital = advanced["capital"]
    before = advanced["capital_before_distribution"]
    linked = advanced["linked_exit"]
    fragments = ['<section class="panel review" id="partnership"><div class="sectionhead"><div><h2>Partnership accounting & investor statements</h2><p class="sub">Fictional partnership case · separate from the four comparison funds above</p></div><span class="badge synthetic">SYNTHETIC</span></div><div class="panelbody">']
    fragments.append('<p>' + _text(capital.get("name", "Northstar Partnership")) + ' · accounting status <strong>' + _text(capital["status"]) + '</strong> · terminal distribution <strong>' + _text(linked["status"]) + '</strong></p>')
    fragments.append('<div class="cards">' + "".join('<div class="card"><div class="label">' + _text(label) + '</div><div class="value" style="font-size:22px">' + _money(value) + '</div></div>' for label, value in [
        ("Cash available before waterfall", before["balances"]["cash_cents"]), ("Fund equity before distribution", before["balances"]["equity_cents"]),
        ("Remaining facility debt", capital["balances"]["debt_cents"]), ("Final account difference", capital["balances"]["reconciliation_difference_cents"])]) + '</div>')
    fragments.append(_table(["Investor", "Role", "Committed", "Paid-in", "Distributed", "Final capital", "Realized gain", "Unrealized gain", "Fees", "Interest", "Carry transfer", "TVPI", "Dated IRR", "IRR status"], [[
        row["name"], row["role"], _money(row["commitment_cents"]), _money(row["paid_in_cents"]), _money(row["distributed_cents"]),
        _money(row["capital_cents"]), _money(row["realized_gain_cents"]), _money(row["unrealized_gain_cents"]), _money(row["fee_cents"]), _money(row["interest_cents"]), _money(row["carry_net_cents"]), _multiple(row.get("tvpi")), 'Unavailable' if (row.get("xirr") or {}).get("value") is None else f'{row["xirr"]["value"] * 100:.2f}%', (row.get("xirr") or {}).get("status", "UNAVAILABLE")
    ] for row in capital["investors"]]))
    fragments.append('<p class="note">The fixed ownership case allocates economic gains, management fees and interest by commitment. The GP receives co-investment proceeds and a separate carry transfer. Fund equity must equal the sum of investor capital after each event. Signed temporary capital before the first call is preserved. Short holding periods can produce very large annualized rates; OUT_OF_RANGE withholds rates outside the solver domain of -99.99% through 10,000%.</p>')
    if linked.get("waterfall"):
        wf = linked["waterfall"]
        tier_labels = {"Return LP capital": "Return contributed capital", "LP preferred return": "Contributor preferred return"}
        fragments.append('<h3 style="margin-top:24px">Integrated exit waterfall</h3>' + _table(["Tier", "Contributor proceeds", "GP carry", "Total"], [[tier_labels.get(row["name"], row["name"]), _money(row["lp_cents"]), _money(row["gp_cents"]), _money(row["total_cents"])] for row in wf["tiers"]]))
        fragments.append('<p class="note">' + _text(linked["note"]) + '</p>')
    fragments.append('<details style="margin-top:24px"><summary>Trace the accounting journal</summary>' + _table(["Event", "Date", "Kind", "Cash", "Investments", "Debt", "Accrued interest", "Fund equity"], [[row["event_id"], row["effective_date"], row["kind"], *[_money(row["balances_after"][key]) for key in ("cash_cents", "investments_cents", "debt_cents", "accrued_interest_cents", "equity_cents")]] for row in capital["event_journal"]]) + '</details>')
    for scenario in advanced.get("capital_scenarios", []):
        case = scenario["result"]
        fragments.append('<details style="margin-top:18px"><summary>' + _text(scenario["name"].replace("_", " ").title()) + ' accounting scenario · ' + _text(case["status"]) + '</summary>')
        fragments.append('<p class="note">Separate fixed scenario · measured ' + _text(case["asof"]) + ' · information known by ' + _text(case["known_at"]) + '.</p>')
        fragments.append(_table(["Investor", "Paid-in", "Recallable distributions", "Remaining commitment", "Capital"], [[row["name"], _money(row["paid_in_cents"]), _money(row["recallable_cents"]), _money(row["unfunded_cents"]), _money(row["capital_cents"])] for row in case["investors"]]))
        for control in case.get("controls", []):
            fragments.append('<p class="note"><strong>' + _text(control.get("code", "CONTROL")) + '</strong> ' + _text(control.get("message", control)) + '</p>')
        fragments.append('</details>')
    fragments.append('</div></section>')
    demo = advanced["waterfall_demo"]
    fragments.append('<section class="panel review" id="waterfalls"><div class="sectionhead"><div><h2>Preferred return, carry & clawback</h2><p class="sub">Separate cumulative terminal examples · simple Actual/365 preferred return</p></div><select class="select" id="advancedScenarioSelect" aria-label="Waterfall scenario">')
    for scenario in demo["scenarios"]:
        fragments.append('<option value="' + _text(scenario["scenario_id"]) + '">' + _text(scenario["name"]) + '</option>')
    fragments.append('</select></div><div class="panelbody">')
    for index, scenario in enumerate(demo["scenarios"]):
        wf = scenario["result"]
        fragments.append('<div data-waterfall-scenario="' + _text(scenario["scenario_id"]) + '"' + (' hidden' if index else '') + '><p>' + _text(scenario["description"]) + '</p><div class="cards">')
        for label, key in [("Lifetime proceeds", "total_proceeds_cents"), ("GP carry entitlement", "gp_total_cents"), ("Preferred still unpaid", "preferred_unpaid_cents"), ("GP clawback due", "clawback_due_cents")]:
            fragments.append('<div class="card"><div class="label">' + _text(label) + '</div><div class="value" style="font-size:22px">' + _money(wf[key]) + '</div></div>')
        fragments.append('</div>' + _table(["Tier", "LP proceeds", "GP carry", "Cash conserved"], [[row["name"], _money(row["lp_cents"]), _money(row["gp_cents"]), _money(row["total_cents"])] for row in wf["tiers"]]) + '</div>')
    fragments.append('<p class="note">Lifetime proceeds include any previously paid GP carry. Clawback is the excess of prior carry over the revised cumulative entitlement. This is a fictional agreement with one terminal allocation; it does not model contractual interim distributions or establish a legal claim.</p></div></section>')
    fragments.append('<section class="panel review" id="return-diagnostics"><div class="sectionhead"><div><h2>Return diagnostics & benchmark comparison</h2><p class="sub">Baseline synthetic flows · candidate roots never replace the controlled reporting rate</p></div></div>')
    diagnostic_rows = []
    for fund in payload["funds"]:
        diag, adjusted = fund.get("return_diagnostics") or {}, fund.get("benchmark_adjusted_return") or {}
        roots = ', '.join(f'{value * 100:.3f}%' for value in diag.get("candidate_rates", [])) or 'Unavailable'
        alpha = adjusted.get("value")
        diagnostic_rows.append([fund["fund_id"], roots, diag.get("status", "UNAVAILABLE"), _multiple(fund["ks_pme"]), 'Unavailable' if alpha is None else f'{alpha * 100:.3f}%', adjusted.get("status", "UNAVAILABLE")])
    fragments.append(_table(["Fund", "Observed IRR roots", "Root interpretation", "KS-PME", "Benchmark-adjusted rate", "Adjusted rate status"], diagnostic_rows))
    fragments.append('<div class="panelbody"><p class="note">Mixed-sign flows use a bounded finite scan; tangent roots and closely spaced crossings can be missed. One observed root does not establish uniqueness. Benchmark-adjusted rates use terminalized total-return index cash flows rounded to cents; they are comparator diagnostics, not risk-adjusted investment alpha. The four-fund index remains synthetic.</p></div></section>')
    public = advanced["public_research"]
    fragments.append('<section class="panel review" id="public-research"><div class="sectionhead"><div><h2>Public-pension disclosure research</h2><p class="sub">Official-source observations · separate from every synthetic calculation above</p></div><span class="badge">' + _text(public.get("status", "RESEARCH")) + '</span></div><div class="panelbody">')
    records = public.get("records", [])
    fragments.append('<p class="note">' + _text(advanced.get("public_research_context")) + '</p>')
    if records:
        fragments.append(_table(["Fund", "Vintage", "Contributed", "Distributed", "Remaining value", "Recomputed multiple", "Reported multiple", "Reported IRR"], [[row.get("fund_name", row.get("name", "—")), row.get("vintage"), _money(row.get("contributions_cents")), _money(row.get("distributions_cents")), _money(row.get("nav_cents")), _multiple(row.get("tvpi")), _multiple(row.get("reported_multiple")), "—" if row.get("reported_irr") is None else f'{row["reported_irr"] * 100:.2f}%'] for row in records[:30]]))
    else:
        fragments.append('<p>No verified source rows are available in the saved research package.</p>')
    for limit in public.get("limitations", []):
        fragments.append('<p class="note">' + _text(limit) + '</p>')
    for source in public.get("provenance", []):
        fragments.append('<div class="note"><strong>' + _text(source.get("source_name", source.get("title", "Official research evidence"))) + '</strong><br>Measured ' + _text(source.get("asof_date")) + ' · captured ' + _text(source.get("retrieved_at")) + '<br>' + _text(source.get("coverage")) + '<br>Capture: ' + _text(source.get("capture_method")) + '<br>Derived snapshot SHA-256: <span style="overflow-wrap:anywhere">' + _text(source.get("sha256")) + '</span></div>')
        # Render evidence links only when the imported provenance is a public URL.
        url = source.get("url", source.get("source_url", ""))
        if isinstance(url, str) and url.startswith("https://"):
            fragments.append('<p class="note"><a href="' + _text(url) + '" target="_blank" rel="noopener noreferrer">' + _text(source.get("source_name", source.get("title", "Official research evidence"))) + '</a></p>')
    fragments.append('</div></section><script>document.getElementById("advancedScenarioSelect").addEventListener("change",function(){const chosen=this.value;document.querySelectorAll("[data-waterfall-scenario]").forEach(node=>{node.hidden=node.dataset.waterfallScenario!==chosen;});});</script>')
    return "".join(fragments)
