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
    st.markdown("## 👤 Customer Intelligence & Baseline Explorer")
    st.caption("Inspect verified financial parameters, ownership context, and transaction trends for any retail account.")

    # 1. Account Search Bar & Quick Selector
    col_input, col_preset = st.columns([1, 2])
    
    with col_input:
        selected_id = st.number_input(
            "Enter Account ID (1 to 75000):",
            min_value=1,
            max_value=100000,
            value=st.session_state.get("active_account_id", 20111),
            step=1
        )
        st.session_state["active_account_id"] = selected_id

    with col_preset:
        st.write("Or select a representative archetype:")
        b1, b2, b3, b4 = st.columns(4)
        if b1.button("Account 20111\n(Running Loan D)", use_container_width=True):
            st.session_state["active_account_id"] = 20111
            st.rerun()
        if b2.button("Account 55447\n(Healthy Loan C)", use_container_width=True):
            st.session_state["active_account_id"] = 55447
            st.rerun()
        if b3.button("Account 62236\n(Protected Joint)", use_container_width=True):
            st.session_state["active_account_id"] = 62236
            st.rerun()
        if b4.button("Account 74958\n(Full 72 Mo History)", use_container_width=True):
            st.session_state["active_account_id"] = 74958
            st.rerun()

    account_id = st.session_state["active_account_id"]
    profile = get_customer_profile(account_id, repo)

    if not profile:
        st.error(f"❌ Account ID #{account_id} not found in the 4,500 retail account directory. Please enter a valid account ID.")
        return

    monthly_df = repo.get_monthly_summary(account_id)
    acc_meta = repo.get_account_meta(account_id)
    baseline = compute_official_baseline(account_id, monthly_df, acc_meta)

    # 2. Header & Archetype Banner
    banner_col1, banner_col2 = st.columns([2.5, 1.5])
    with banner_col1:
        st.markdown(f"### Account #{profile.account_id} · Client #{profile.owner_client_id}")
        st.markdown(
            f"**Demographics:** {profile.gender}, Age {profile.age:.0f} ({profile.age_bracket}) | "
            f"**Branch:** {profile.branch_district_name} ({profile.branch_region}) | "
            f"**Opened:** {profile.account_opened} ({baseline.history_months} months active)"
        )

    with banner_col2:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 12px; border-radius: 6px; border: 1px solid {profile.archetype_badge_color}; text-align: center;">
            <span style="font-size: 11px; color: {THEME['text_muted']}; text-transform: uppercase;">Behavioral Archetype</span>
            <p style="font-size: 16px; font-weight: bold; color: {profile.archetype_badge_color}; margin: 2px 0;">{profile.primary_archetype}</p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 3. Official Judging Metrics Display
    st.subheader("📐 Official Baseline Parameters (Tangerine Challenge Definitions)")
    m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
    with m1:
        st.metric("Money In (I)", f"${baseline.I:,.2f}", help="Median of money_in")
    with m2:
        st.metric("Fixed Costs (F)", f"${baseline.F:,.2f}", help="Median of row-wise household_bills + insurance + loan_payments")
    with m3:
        st.metric("Spending (S)", f"${baseline.S:,.2f}", help="Median of money_out")
    with m4:
        st.metric("Buffer (B)", f"${baseline.B:,.2f}", help="Mean of avg_daily_balance over the last 6 chronological rows")
    with m5:
        st.metric("Bills (H)", f"${baseline.H:,.2f}", help="Median of household_bills")
    with m6:
        st.metric("Active Loan (P)", f"${baseline.P:,.2f}", help="monthly_payment if loan is still running at end of 2025 (status C or D), else 0")
    with m7:
        st.metric("Baseline Runway", baseline.baseline_runway_label, delta=f"Gap: ${baseline.gap:,.2f}", delta_color="inverse")

    # 4. Contextual Diagnostics & Buffer Provenance
    with st.expander("🔍 Buffer Provenance (Exact 6 Rows Used for B)"):
        st.markdown(
            f"The Tangerine challenge defines **Buffer (B)** as the arithmetic mean of `avg_daily_balance` "
            f"over the account's last 6 chronological monthly records. Average = **${baseline.B:,.2f} CAD**."
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
    st.subheader("📈 Longitudinal Cash Flow & Balance Trajectory")
    
    t_tab1, t_tab2 = st.tabs(["💵 Inflow vs Outflow Cash Velocity", "🏦 End-of-Day Balance & Overdraft Days"])

    with t_tab1:
        fig_cf = go.Figure()
        fig_cf.add_trace(go.Scatter(
            x=monthly_df["month"],
            y=monthly_df["money_in"],
            mode="lines+markers",
            name="Money In (Monthly)",
            line=dict(color=THEME["success_green"], width=2.5)
        ))
        fig_cf.add_trace(go.Scatter(
            x=monthly_df["month"],
            y=monthly_df["money_out"],
            mode="lines+markers",
            name="Money Out (Monthly)",
            line=dict(color=THEME["alert_red"], width=2.5)
        ))
        fig_cf.add_hline(
            y=baseline.I,
            line_dash="dash",
            line_color=THEME["success_green"],
            annotation_text=f"Typical In (I): ${baseline.I:,.0f}"
        )
        fig_cf.add_hline(
            y=baseline.S,
            line_dash="dash",
            line_color=THEME["alert_red"],
            annotation_text=f"Typical Out (S): ${baseline.S:,.0f}"
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
            x=monthly_df["month"],
            y=monthly_df["avg_daily_balance"],
            mode="lines",
            name="Avg Daily Balance",
            line=dict(color=THEME["accent_blue"], width=2)
        ))
        fig_bal.add_trace(go.Bar(
            x=monthly_df["month"],
            y=monthly_df["days_below_zero"],
            name="Days Below Zero",
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
