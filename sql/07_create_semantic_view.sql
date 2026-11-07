-- 07_create_semantic_view.sql
USE DATABASE RESILIENCE_REWIRED;
USE SCHEMA SEMANTIC;

-- Semantic View for Snowflake Cortex Analyst / Cortex Agents
CREATE OR REPLACE VIEW FINANCIAL_RESILIENCE_SEMANTIC_VIEW AS
SELECT 
    account_id AS "Account ID",
    branch_district_id AS "Branch District",
    statement_frequency AS "Statement Frequency",
    is_joint AS "Is Joint Account",
    card_type AS "Card Type",
    typical_money_in_i AS "Typical Monthly Money-In",
    typical_fixed_costs_f AS "Typical Fixed Costs",
    typical_spending_s AS "Typical Monthly Spending",
    buffer_b AS "Savings Buffer",
    typical_household_bills_h AS "Typical Household Bills",
    active_loan_payment_p AS "Active Loan Payment",
    baseline_gap AS "Monthly Cash-Flow Gap",
    baseline_runway_months AS "Baseline Runway (Months)",
    
    -- Pre-calculated Shock Runways
    ROUND(LEAST(GREATEST(0.0, buffer_b) / GREATEST(0.01, (typical_spending_s - 0.55 * typical_money_in_i)), 120.0), 1) AS "Runway Under EI 55%",
    ROUND(LEAST(GREATEST(0.0, buffer_b) / GREATEST(0.01, (typical_spending_s + 0.15 * typical_household_bills_h - 0.55 * typical_money_in_i)), 120.0), 1) AS "Runway Under Combined Shock"
FROM MART.ACCOUNT_BASELINE
COMMENT = 'Governed semantic view providing certified customer resilience metrics for Cortex Agent business Q&A';
