-- 03_create_raw_tables.sql
USE DATABASE RESILIENCE_REWIRED;
USE SCHEMA RAW;

-- 1. Accounts Raw
CREATE OR REPLACE TABLE ACCOUNTS_RAW (
    account_id INT PRIMARY KEY,
    district_id INT,
    frequency VARCHAR(100),
    account_opened DATE
);

-- 2. Clients Raw
CREATE OR REPLACE TABLE CLIENTS_RAW (
    client_id INT PRIMARY KEY,
    gender VARCHAR(10),
    birth_date DATE,
    district_id INT
);

-- 3. Dispositions Raw
CREATE OR REPLACE TABLE DISPOSITIONS_RAW (
    disposition_id INT PRIMARY KEY,
    client_id INT,
    account_id INT,
    type VARCHAR(50)
);

-- 4. Cards Raw
CREATE OR REPLACE TABLE CARDS_RAW (
    card_id INT PRIMARY KEY,
    disposition_id INT,
    card_type VARCHAR(50),
    issued DATE
);

-- 5. Districts Raw
CREATE OR REPLACE TABLE DISTRICTS_RAW (
    district_id INT PRIMARY KEY,
    district_name VARCHAR(100),
    region VARCHAR(100),
    inhabitants INT,
    municipalities_under_500 INT,
    municipalities_500_1999 INT,
    municipalities_2000_9999 INT,
    municipalities_over_10000 INT,
    num_cities INT,
    urban_ratio_pct FLOAT,
    average_salary FLOAT,
    unemployment_rate_2022 FLOAT,
    unemployment_rate_2023 FLOAT,
    entrepreneurs_per_1000 INT,
    crimes_2022 FLOAT,
    crimes_2023 INT
);

-- 6. Loans Raw
CREATE OR REPLACE TABLE LOANS_RAW (
    loan_id INT PRIMARY KEY,
    account_id INT,
    loan_start DATE,
    amount FLOAT,
    duration_months INT,
    monthly_payment FLOAT,
    status VARCHAR(10),
    status_meaning VARCHAR(100),
    defaulted INT
);

-- 7. Standing Orders Raw
CREATE OR REPLACE TABLE STANDING_ORDERS_RAW (
    order_id INT PRIMARY KEY,
    account_id INT,
    to_bank VARCHAR(10),
    to_account VARCHAR(50),
    amount FLOAT,
    purpose VARCHAR(100)
);

-- 8. Monthly Summary Raw
CREATE OR REPLACE TABLE MONTHLY_SUMMARY_RAW (
    account_id INT,
    month VARCHAR(7),
    money_in FLOAT,
    money_out FLOAT,
    cash_deposits FLOAT,
    transfers_in FLOAT,
    pension_in FLOAT,
    interest_in FLOAT,
    household_bills FLOAT,
    insurance FLOAT,
    loan_payments FLOAT,
    bank_fees FLOAT,
    cash_withdrawals_genuine FLOAT,
    card_withdrawals FLOAT,
    transfers_out_other FLOAT,
    month_end_balance FLOAT,
    min_balance FLOAT,
    avg_daily_balance FLOAT,
    days_below_zero FLOAT,
    PRIMARY KEY (account_id, month)
);

-- 9. Transactions Raw
CREATE OR REPLACE TABLE TRANSACTIONS_RAW (
    transaction_id INT PRIMARY KEY,
    account_id INT,
    date DATE,
    direction VARCHAR(50),
    operation VARCHAR(100),
    purpose VARCHAR(100),
    amount FLOAT,
    signed_amount FLOAT,
    balance FLOAT,
    partner_bank VARCHAR(10),
    partner_account VARCHAR(50)
);
