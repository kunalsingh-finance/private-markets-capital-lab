-- Queries for one immutable evidence pack. Cents remain integer source amounts.
-- Portfolio multiples must divide SUM(dollars), not average fund ratios.
SELECT
  SUM(paid_in_cents) AS paid_in_cents,
  SUM(distributed_cents) AS distributed_cents,
  CASE WHEN COUNT(nav_cents) = COUNT(*) THEN SUM(nav_cents) END AS complete_nav_cents,
  CASE WHEN SUM(paid_in_cents)>0 THEN 1.0*SUM(distributed_cents)/SUM(paid_in_cents) END AS dpi,
  CASE WHEN COUNT(nav_cents)=COUNT(*) AND SUM(paid_in_cents)>0
    THEN 1.0*(SUM(distributed_cents)+SUM(nav_cents))/SUM(paid_in_cents) END AS tvpi
FROM performance_metrics;

SELECT i.name, i.role, s.capital_cents, s.paid_in_cents, s.distributed_cents,
       s.gain_cents, s.fee_cents, s.interest_cents, s.carry_net_cents,
       s.paid_in_cents+s.gain_cents-s.fee_cents-s.interest_cents
       +s.carry_net_cents-s.distributed_cents AS independently_bridged_capital_cents
FROM dim_investor i JOIN fact_capital_statement s USING(investor_id);

SELECT scenario_id, SUM(lp_cents) AS contributor_proceeds_cents,
       SUM(gp_cents) AS gp_carry_cents, SUM(total_cents) AS cumulative_proceeds_cents,
       SUM(total_cents)-SUM(lp_cents)-SUM(gp_cents) AS difference_cents
FROM fact_waterfall_tier GROUP BY scenario_id;

SELECT event_id, kind, effective_date,
       cash_cents+investments_cents-debt_cents-accrued_interest_cents-equity_cents AS account_difference_cents
FROM fact_accounting_event;
