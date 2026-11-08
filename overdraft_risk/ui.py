"""
Screen: 6-month overdraft-risk estimate for one account
"""

import pandas as pd
import streamlit as st

from src.data.local_repository import LocalDataRepository
from overdraft_risk.service import MIN_HISTORY, get_overdraft_risk, load_model

FEATURE_LABELS = {
    "log_buffer6": "ln(1 + average daily balance, last 6 months)",
    "buffer_months": "Buffer ÷ average monthly money out",
    "min_bal_to_out": "Lowest balance (6 months) ÷ average monthly money out",
    "log_mean_in": "ln(1 + average monthly money in)",
    "cash_wd_share": "Cash withdrawals ÷ money out",
    "outflow_months_share": "Share of months with money out > money in",
    "spend_trend": "Spending change: last 3 vs previous 3 months (log)",
    "loanpay_to_in": "Loan payments ÷ money in",
    "so_to_in": "Standing orders ÷ average monthly money in",
    "penalty_hist": "Any penalty interest before this month (1 = yes)",
    "neg_months_win": "Months with a negative balance (last 6)",
    "joint": "Two clients on the account (1 = yes)",
}


def render_overdraft_risk(repo: LocalDataRepository):
    st.markdown("## ⚠️ Overdraft risk (next 6 months)")
    st.caption(
        "Estimated chance that the account has at least one overdraft event in the six months after the "
        "selected month: a month with days below zero or a negative minimum balance, or a penalty-interest charge."
    )

    accounts = repo.get_all_accounts()
    default_id = st.session_state.get("active_account_id", accounts[0])
    account_id = st.selectbox(
        "Account", accounts, index=accounts.index(default_id) if default_id in accounts else 0, key="risk_account"
    )
    st.session_state["active_account_id"] = account_id

    months = sorted(repo.get_monthly_summary(account_id)["month"].astype(str).unique())
    eligible = months[MIN_HISTORY - 1:]
    if not eligible:
        st.warning(f"This account has fewer than {MIN_HISTORY} monthly records, so no estimate is available.")
        return
    as_of = st.selectbox("Estimate as of month", eligible[::-1], index=0, key="risk_as_of")

    result = get_overdraft_risk(int(account_id), repo, as_of=as_of)
    if result is None:
        st.error(f"Account {account_id} was not found.")
        return

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Chance of an overdraft event", result.display, help="Rounded to two decimal places.")
    with c2:
        st.metric("Based on data up to", result.as_of_month)
    with c3:
        st.metric("Looks ahead", f"{result.horizon_months} months")

    with st.expander("🧾 Inputs used for this estimate"):
        rows = [
            {"Predictor": key, "Meaning": FEATURE_LABELS.get(key, key), "Value": value}
            for key, value in result.features.items()
        ]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        meta = load_model()
        st.caption(
            f"Logistic regression trained on {meta['training_rows']:,} account-months "
            f"(cutoffs {meta['training_cutoffs'][0]} to {meta['training_cutoffs'][-1]}, labels {meta['label_period']}). "
            f"Tested on 2025 outcomes: AUC {meta['test_metrics_2025']['AUC']}. Missing values are filled with "
            "the training median."
        )

    st.caption(
        "This is a statistical association from past account behaviour, not a credit decision. An overdraft "
        "event is a proxy for financial stress and does not show its size or cause."
    )
