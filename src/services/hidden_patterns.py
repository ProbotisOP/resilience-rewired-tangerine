"""
Data for the Hidden patterns page: one cached Snowflake query per story.

Every query is fixed SQL with no user input. Results are cached for the session; the Snowflake ML
outputs (drivers, metrics, calibration, scores, anomalies, backtest) are reused from the repository.
"""

from typing import Any, Dict

import pandas as pd
import streamlit as st

# One row per supplied loan with the account traits used by the default-fingerprint and warning-sign stories.
# pre_penalty = penalty interest charged on the account BEFORE the loan started (no post-loan leakage).
LOAN_TRAITS_SQL = """
WITH pen AS (
    SELECT l.loan_id,
           MAX(IFF(t.purpose = 'penalty interest (negative balance)' AND t.transaction_date < l.loan_start, 1, 0)) AS pre_penalty
    FROM CURATED.FACT_LOAN l
    LEFT JOIN CURATED.FACT_TRANSACTION t ON t.account_id = l.account_id
    GROUP BY l.loan_id
)
SELECT l.loan_id, l.account_id, l.defaulted::INT AS defaulted, l.loan_status,
       r.has_authorized_user AS authorized_user, r.has_card AS has_card, r.statement_frequency,
       r.cash_inflow_ratio AS cash_share,
       NTILE(4) OVER (ORDER BY r.cash_inflow_ratio, l.loan_id) AS cash_quartile,
       p.pre_penalty
FROM CURATED.FACT_LOAN l
JOIN MART.ACCOUNT_RESILIENCE_360 r ON r.account_id = l.account_id
JOIN pen p ON p.loan_id = l.loan_id
"""

PAYDAY_SQL = """
SELECT DAY(transaction_date) AS day_of_month,
       SUM(IFF(direction LIKE 'credit%', amount, 0)) AS money_in,
       SUM(IFF(direction LIKE 'debit%', amount, 0)) AS money_out,
       SUM(IFF(operation = 'cash withdrawal', amount, 0)) AS cash_out
FROM CURATED.FACT_TRANSACTION
GROUP BY 1
ORDER BY 1
"""

SPEND_MIX_SQL = """
SELECT SUM(household_bills) AS household_bills, SUM(insurance) AS insurance, SUM(loan_payments) AS loan_payments,
       SUM(bank_fees) AS bank_fees, SUM(cash_withdrawals_genuine) AS cash_withdrawals_genuine,
       SUM(card_withdrawals) AS card_withdrawals, SUM(transfers_out_other) AS transfers_out_other,
       SUM(money_out) AS money_out
FROM CURATED.FACT_ACCOUNT_MONTH
"""

# Standing orders labelled "loan payment" on accounts with no loan in the bank's own loan table.
OFF_BOOK_SQL = """
SELECT s.account_id, SUM(s.order_amount) AS monthly_amount, COUNT(*) AS orders
FROM CURATED.FACT_STANDING_ORDER s
WHERE s.order_purpose = 'loan payment'
  AND s.account_id NOT IN (SELECT account_id FROM CURATED.FACT_LOAN)
GROUP BY s.account_id
ORDER BY monthly_amount DESC
"""

STANDING_ORDER_PURPOSE_SQL = """
SELECT COALESCE(order_purpose, 'unlabelled') AS purpose, COUNT(DISTINCT account_id) AS accounts
FROM CURATED.FACT_STANDING_ORDER
GROUP BY 1
"""

# For every scored account-month: was there a negative-balance day in the next three months?
ANOMALY_FOLLOW_UP_SQL = """
WITH a AS (
    SELECT account_id, month, measure, story IS NOT NULL AS flagged FROM ML.ACCOUNT_MONTH_ANOMALIES
), nxt AS (
    SELECT a.measure, a.flagged, a.account_id, a.month, MAX(IFF(m.had_negative_balance_day, 1, 0)) AS neg_next3
    FROM a
    JOIN CURATED.FACT_ACCOUNT_MONTH m
      ON m.account_id = a.account_id
     AND m.month_date > TO_DATE(a.month || '-01')
     AND m.month_date <= DATEADD(month, 3, TO_DATE(a.month || '-01'))
    GROUP BY 1, 2, 3, 4
)
SELECT measure, flagged, COUNT(*) AS months, SUM(neg_next3) AS followed_by_negative
FROM nxt
GROUP BY 1, 2
"""

# Top-earner accounts spending 90-100% of money in: the TOP_INSIGHTS "hidden risk" segment.
HIDDEN_RISK_SQL = """
SELECT account_id, typical_money_in, typical_spending, savings_buffer,
       baseline_runway_months, runway_under_ei_55, ml_risk_tier
FROM MART.ACCOUNT_RESILIENCE_360
WHERE income_decile = 10
  AND typical_spending / NULLIF(typical_money_in, 0) BETWEEN 0.9 AND 1.0
  AND baseline_runway_months >= 6
ORDER BY runway_under_ei_55
"""


@st.cache_data(show_spinner="Reading hidden patterns from Snowflake…", ttl=3600)
def load_pattern_data(_repo: Any) -> Dict[str, pd.DataFrame]:
    """Run the page's fixed queries once per session. `_repo` is not hashed (leading underscore)."""
    return {
        "loans": _repo.query(LOAN_TRAITS_SQL),
        "payday": _repo.query(PAYDAY_SQL),
        "spend": _repo.query(SPEND_MIX_SQL),
        "off_book": _repo.query(OFF_BOOK_SQL),
        "so_purpose": _repo.query(STANDING_ORDER_PURPOSE_SQL),
        "anomaly_follow_up": _repo.query(ANOMALY_FOLLOW_UP_SQL),
        "hidden_risk": _repo.query(HIDDEN_RISK_SQL),
    }


def default_rate_table(loans: pd.DataFrame, group: pd.Series, order=None) -> pd.DataFrame:
    """Loans, defaults and default rate (%) per group value."""
    t = loans.groupby(group, observed=False)["defaulted"].agg(loans="size", defaults="sum").reset_index()
    t.columns = ["group", "loans", "defaults"]
    t["rate"] = (t["defaults"] / t["loans"].where(t["loans"] > 0) * 100).round(1).fillna(0)
    if order is not None:
        t = t.set_index("group").reindex(order).reset_index()
    return t
