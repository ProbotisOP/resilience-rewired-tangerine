-- Optional ordinary SQL view example.
-- This is NOT a Snowflake Cortex Semantic View and is not queried by the app.
USE DATABASE RESILIENCE_REWIRED;
USE SCHEMA SEMANTIC;

CREATE OR REPLACE VIEW FINANCIAL_RESILIENCE_METRICS AS
SELECT
    account_id AS "Account ID",
    branch_district_id AS "Branch District",
    statement_frequency AS "Statement Frequency",
    has_authorized_user AS "Has Authorized User",
    card_type AS "Card Type",
    typical_money_in_i AS "Typical Monthly Money-In",
    typical_fixed_costs_f AS "Typical Fixed Costs",
    typical_spending_s AS "Typical Monthly Spending",
    buffer_b AS "Savings Buffer",
    typical_household_bills_h AS "Typical Household Bills",
    active_loan_payment_p AS "Active Loan Payment",
    baseline_gap AS "Monthly Cash-Flow Gap",
    baseline_runway_months AS "Baseline Runway (Months)",
    CASE
        WHEN buffer_b <= 0 THEN 0.0
        WHEN typical_spending_s - 0.55 * typical_money_in_i <= 0 THEN 120.0
        ELSE ROUND(
            LEAST(
                buffer_b / (typical_spending_s - 0.55 * typical_money_in_i),
                120.0
            ),
            1
        )
    END AS "Simulated Runway Under 55% Money-In"
FROM MART.ACCOUNT_BASELINE
COMMENT = 'Optional reporting view; scenario result is simulated and not a forecast';
