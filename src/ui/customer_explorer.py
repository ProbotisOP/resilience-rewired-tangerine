"""
Screen 2: Customer Explorer & Longitudinal Account Intelligence
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from src.data.local_repository import LocalDataRepository
from src.services.customer_profile import get_customer_profile
from src.services.baseline_metrics import compute_official_baseline
from config.settings import THEME

def render_customer_explorer(repo: LocalDataRepository):
    st.markdown("## 👤 Explore an account")
    st.caption(
        "Choose any account to see its observed monthly history and how the app builds "
        "the baseline. These figures describe the supplied records, not the person's full finances."
    )

    # 1. Select from all supplied account IDs
    valid_accounts = repo.get_all_accounts()
    current_account = st.session_state.get("active_account_id", valid_accounts[0])
    if current_account not in valid_accounts:
        current_account = valid_accounts[0]
    col_input, col_preset = st.columns([1, 2])
    
    with col_input:
        selected_id = st.selectbox(
            "Choose an account",
            options=valid_accounts,
            index=valid_accounts.index(current_account),
            format_func=lambda value: f"Account #{value}",
        )
        st.session_state["active_account_id"] = selected_id

    with col_preset:
        st.write("Or jump to a sample:")
        b1, b2, b3, b4 = st.columns(4)
        if b1.button("Account 20111", use_container_width=True):
            st.session_state["active_account_id"] = 20111
            st.rerun()
        if b2.button("Account 55447", use_container_width=True):
            st.session_state["active_account_id"] = 55447
            st.rerun()
        if b3.button("Account 62236", use_container_width=True):
            st.session_state["active_account_id"] = 62236
            st.rerun()
        if b4.button("Account 74958", use_container_width=True):
            st.session_state["active_account_id"] = 74958
            st.rerun()

    account_id = st.session_state["active_account_id"]
    profile = get_customer_profile(account_id, repo)

    if not profile:
        st.error(f"❌ Account ID #{account_id} not found in the 4,500 retail account directory. Please enter a valid account ID.")
        return

    monthly_df = repo.get_monthly_summary(account_id)
    monthly_df = monthly_df.sort_values("month").copy()
    acc_meta = repo.get_account_meta(account_id)
    baseline = compute_official_baseline(account_id, monthly_df, acc_meta)
    if baseline.history_months < 6:
        st.warning(
            f"Only {baseline.history_months} monthly records are available; the buffer uses "
            "the available rows rather than a full six-month window."
        )

    # 2. Header & Observed Indicators
    banner_col1, banner_col2 = st.columns([2.5, 1.5])
    with banner_col1:
        st.markdown(f"### Account #{profile.account_id}")
        st.markdown(
            f"**Account opened:** {profile.account_opened} · "
            f"**Monthly records available:** {baseline.history_months} · "
            f"**Branch area:** {profile.branch_district_name} ({profile.branch_region})"
        )

    with banner_col2:
        st.markdown("**Details visible in the data**")
        st.write(", ".join(profile.observed_indicators) if profile.observed_indicators else "No additional details flagged.")
        st.caption(profile.indicator_description)

    st.markdown("---")

    # 3. Official Judging Metrics Display
    st.subheader("📐 Typical monthly picture")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    with m1:
        st.metric("Money in", f"${baseline.I:,.2f}", help="Median of monthly money in.")
    with m2:
        st.metric("Fixed costs", f"${baseline.F:,.2f}", help="Median of monthly household bills, insurance and loan payments added together.")
    with m3:
        st.metric("Spending", f"${baseline.S:,.2f}", help="Median of monthly money out.")
    with m4:
        st.metric("Buffer", f"${baseline.B:,.2f}", help="Average daily balance across up to the latest six monthly rows.")
    with m5:
        st.metric("Household bills", f"${baseline.H:,.2f}", help="Median of monthly household bills.")
    with m6:
        st.metric("Recorded loan payment", f"${baseline.P:,.2f}", help="Supplied payment for a loan marked C or D; otherwise $0.")
    with m7:
        st.metric("Runway", baseline.baseline_runway_label, delta=f"Monthly gap: ${baseline.gap:,.2f}", delta_color="inverse")

    with st.expander("🧾 Show how this account's figures were calculated", expanded=True):
        st.markdown(
            f"Each monthly statistic uses **{baseline.history_months} available monthly records** "
            "for this account, sorted by month. The buffer uses up to the latest six records."
        )
        st.code(
            "\n".join(
                [
                    f"Money in = median(monthly money_in) = ${baseline.I:,.2f}",
                    f"Spending = median(monthly money_out) = ${baseline.S:,.2f}",
                    f"Fixed costs = median(household_bills + insurance + loan_payments by month) = ${baseline.F:,.2f}",
                    f"Household bills = median(monthly household_bills) = ${baseline.H:,.2f}",
                    f"Buffer = mean(avg_daily_balance in latest {len(baseline.last_6_months_summary)} rows) = ${baseline.B:,.2f}",
                    f"Monthly gap = spending - money in = ${baseline.S:,.2f} - ${baseline.I:,.2f} = ${baseline.gap:,.2f}",
                    (
                        f"Runway = {baseline.B:,.2f} ÷ {baseline.gap:,.2f}, capped at 120 and rounded to one decimal = {baseline.baseline_runway_label}"
                        if baseline.B > 0 and baseline.gap > 0
                        else (
                            "Runway = 0.0 months because the buffer is zero or below."
                            if baseline.B <= 0
                            else "Runway = 120+ months because money in covers spending and the buffer is positive."
                        )
                    ),
                    (
                        f"Recorded loan payment = ${baseline.P:,.2f} (status {profile.loan_status})"
                        if baseline.has_running_loan
                        else "Recorded loan payment = $0.00 (no C/D loan payment is included)"
                    ),
                ]
            ),
            language="text",
        )
        st.caption(
            "Source: account's monthly_summary rows and supplied loan record. The summary "
            "does not establish which expenses are essential or discretionary."
        )
        display_last6 = baseline.last_6_months_summary[[
            "month", "money_in", "money_out", "avg_daily_balance", "month_end_balance", "days_below_zero"
        ]].copy()
        st.dataframe(
            display_last6.style.format({
                "money_in": "${:,.2f}",
                "money_out": "${:,.2f}",
                "avg_daily_balance": "${:,.2f}",
                "month_end_balance": "${:,.2f}",
                "days_below_zero": "{:.0f}"
            }),
            use_container_width=True,
            hide_index=True
        )

    # 5. Longitudinal Trend Visualizations
    st.subheader("📈 Explore the monthly history")
    month_options = monthly_df["month"].astype(str).tolist()
    initial_start = month_options[max(0, len(month_options) - 24)]
    month_window = st.select_slider(
        "Show months from",
        options=month_options,
        value=(initial_start, month_options[-1]),
        key=f"history_window_{account_id}",
    )
    visible_monthly_df = monthly_df[
        monthly_df["month"].astype(str).between(month_window[0], month_window[1])
    ].copy()
    selected_month_net = (
        visible_monthly_df["money_in"] - visible_monthly_df["money_out"]
    )
    window_col1, window_col2 = st.columns(2)
    window_col1.metric(
        "Months in view",
        f"{len(visible_monthly_df)}",
        f"{month_window[0]} to {month_window[1]}",
    )
    window_col2.metric(
        "Median net cash flow in view",
        f"${selected_month_net.median():,.2f}/mo",
    )
    st.caption(
        "Move either end of the month range to update the graph. The baseline metrics above "
        "continue to use the account's full available history."
    )

    t_tab1, t_tab2 = st.tabs(["💵 Money in vs spending", "🏦 Balance and below-zero days"])

    with t_tab1:
        fig_cf = go.Figure()
        fig_cf.add_trace(go.Scatter(
            x=visible_monthly_df["month"],
            y=visible_monthly_df["money_in"],
            mode="lines+markers",
            name="Money in",
            line=dict(color=THEME["success_green"], width=2.5)
        ))
        fig_cf.add_trace(go.Scatter(
            x=visible_monthly_df["month"],
            y=visible_monthly_df["money_out"],
            mode="lines+markers",
            name="Spending",
            line=dict(color=THEME["alert_red"], width=2.5)
        ))
        fig_cf.add_hline(
            y=baseline.I,
            line_dash="dash",
            line_color=THEME["success_green"],
            annotation_text=f"Typical money in: ${baseline.I:,.0f}"
        )
        fig_cf.add_hline(
            y=baseline.S,
            line_dash="dash",
            line_color=THEME["alert_red"],
            annotation_text=f"Typical spending: ${baseline.S:,.0f}"
        )
        fig_cf.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Month",
            yaxis_title="CAD ($)",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_cf, use_container_width=True)

    with t_tab2:
        fig_bal = go.Figure()
        fig_bal.add_trace(go.Scatter(
            x=visible_monthly_df["month"],
            y=visible_monthly_df["avg_daily_balance"],
            mode="lines",
            name="Average daily balance",
            line=dict(color=THEME["accent_blue"], width=2)
        ))
        fig_bal.add_trace(go.Bar(
            x=visible_monthly_df["month"],
            y=visible_monthly_df["days_below_zero"],
            name="Days below zero",
            marker_color=THEME["alert_red"],
            yaxis="y2"
        ))
        fig_bal.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="Average Daily Balance ($ CAD)"),
            yaxis2=dict(
                title="Days Below Zero (Days)",
                overlaying="y",
                side="right",
                showgrid=False
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=30, b=20)
        )
        st.plotly_chart(fig_bal, use_container_width=True)
