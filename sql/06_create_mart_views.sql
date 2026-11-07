-- 06_create_mart_views.sql
USE DATABASE RESILIENCE_REWIRED;
USE SCHEMA MART;

-- Official Account Baseline Curated Mart
CREATE OR REPLACE VIEW ACCOUNT_BASELINE AS
WITH MonthlyAggs AS (
    SELECT 
        account_id,
        MEDIAN(money_in) AS typical_money_in_i,
        MEDIAN(fixed_costs_row) AS typical_fixed_costs_f,
        MEDIAN(money_out) AS typical_spending_s,
        MEDIAN(household_bills) AS typical_household_bills_h,
        COUNT(month) AS total_history_months
    FROM CORE.FACT_ACCOUNT_MONTH
    GROUP BY account_id
),
BufferCalc AS (
    SELECT 
        account_id,
        AVG(avg_daily_balance) AS buffer_b
    FROM (
        SELECT 
            account_id,
            avg_daily_balance,
            ROW_NUMBER() OVER (PARTITION BY account_id ORDER BY month DESC) AS rn
        FROM CORE.FACT_ACCOUNT_MONTH
    )
    WHERE rn <= 6
    GROUP BY account_id
),
ActiveLoans AS (
    SELECT 
        account_id,
        monthly_payment AS active_loan_payment_p
    FROM CORE.FACT_LOAN
    WHERE is_running_end_2025 = TRUE
)
SELECT 
    a.account_id,
    a.owner_client_id,
    a.branch_district_id,
    a.statement_frequency,
    a.is_joint,
    a.card_type,
    m.typical_money_in_i,
    m.typical_fixed_costs_f,
    m.typical_spending_s,
    b.buffer_b,
    m.typical_household_bills_h,
    COALESCE(l.active_loan_payment_p, 0.0) AS active_loan_payment_p,
    (m.typical_spending_s - m.typical_money_in_i) AS baseline_gap,
    -- Official Judge Runway
    CASE 
        WHEN b.buffer_b <= 0 THEN 0.0
        WHEN (m.typical_spending_s - m.typical_money_in_i) <= 0 THEN 120.0
        ELSE ROUND(LEAST(b.buffer_b / (m.typical_spending_s - m.typical_money_in_i), 120.0), 1)
    END AS baseline_runway_months
FROM CORE.DIM_ACCOUNT a
JOIN MonthlyAggs m ON a.account_id = m.account_id
JOIN BufferCalc b ON a.account_id = b.account_id
LEFT JOIN ActiveLoans l ON a.account_id = l.account_id;
