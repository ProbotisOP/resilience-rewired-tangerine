-- 05_create_core_views.sql
USE DATABASE RESILIENCE_REWIRED;
USE SCHEMA CORE;

-- Conformed Dimensions
CREATE OR REPLACE VIEW DIM_DISTRICT AS
SELECT 
    district_id,
    district_name,
    region,
    inhabitants,
    urban_ratio_pct,
    average_salary,
    unemployment_rate_2022,
    unemployment_rate_2023,
    (unemployment_rate_2023 - unemployment_rate_2022) AS unemployment_spike,
    entrepreneurs_per_1000,
    crimes_2023
FROM RAW.DISTRICTS_RAW;

CREATE OR REPLACE VIEW DIM_CLIENT AS
SELECT 
    client_id,
    gender,
    birth_date,
    district_id AS home_district_id,
    DATEDIFF('year', birth_date, '2025-12-31') AS age_2025
FROM RAW.CLIENTS_RAW;

CREATE OR REPLACE VIEW DIM_ACCOUNT AS
SELECT 
    a.account_id,
    a.district_id AS branch_district_id,
    a.frequency AS statement_frequency,
    a.account_opened,
    d.client_id AS owner_client_id,
    c.card_type,
    IFF(j.account_id IS NOT NULL, TRUE, FALSE) AS is_joint
FROM RAW.ACCOUNTS_RAW a
LEFT JOIN RAW.DISPOSITIONS_RAW d 
    ON a.account_id = d.account_id AND d.type = 'owner'
LEFT JOIN RAW.CARDS_RAW c 
    ON d.disposition_id = c.disposition_id
LEFT JOIN (
    SELECT DISTINCT account_id FROM RAW.DISPOSITIONS_RAW WHERE type = 'authorized user'
) j ON a.account_id = j.account_id;

-- Fact Views
CREATE OR REPLACE VIEW FACT_ACCOUNT_MONTH AS
SELECT 
    account_id,
    month,
    money_in,
    money_out,
    (household_bills + insurance + loan_payments) AS fixed_costs_row,
    household_bills,
    insurance,
    loan_payments,
    cash_withdrawals_genuine,
    card_withdrawals,
    transfers_out_other,
    month_end_balance,
    avg_daily_balance,
    days_below_zero,
    IFF(days_below_zero > 0, 1, 0) AS is_negative_balance_month
FROM RAW.MONTHLY_SUMMARY_RAW;

CREATE OR REPLACE VIEW FACT_LOAN AS
SELECT 
    loan_id,
    account_id,
    loan_start,
    amount,
    duration_months,
    monthly_payment,
    status,
    status_meaning,
    defaulted,
    IFF(status IN ('C', 'D'), TRUE, FALSE) AS is_running_end_2025
FROM RAW.LOANS_RAW;
