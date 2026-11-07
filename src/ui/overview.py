"""
Screen 1: Portfolio Overview & Executive Discovery Dashboard
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from src.data.local_repository import LocalDataRepository
from src.services.discovery_engine import get_population_summary, get_population_scenario_distributions
from config.settings import THEME

def render_overview(repo: LocalDataRepository):
    st.markdown("## 🏛️ Portfolio Resilience & Macro Executive Overview")
    st.markdown(
        "Longitudinal forensic intelligence across **4,500 retail accounts**, **1,056,320 transactions**, "
        "and **185,326 monthly ledger entries** (2020–2025)."
    )

    summary = get_population_summary(repo)

    # 1. Executive Macro KPIs
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
    with kpi1:
        st.metric("Total Accounts", f"{summary.total_accounts:,}")
    with kpi2:
        st.metric("Typical In (I)", f"${summary.median_I:,.0f}")
    with kpi3:
        st.metric("Typical Spend (S)", f"${summary.median_S:,.0f}")
    with kpi4:
        st.metric("Median Buffer (B)", f"${summary.median_B:,.0f}")
    with kpi5:
        st.metric("Baseline Deficit (S>I)", f"{summary.accounts_in_deficit:,}", f"{summary.pct_in_deficit}%")
    with kpi6:
        st.metric("Active Loans (2025)", f"{summary.active_loans_end_2025}", f"Defaults: {summary.defaulted_loans}")

    st.markdown("---")

    # 2. Portfolio Stress Under Challenge Scenarios
    st.subheader("⚡ Portfolio Vulnerability Under Economic Shocks")
    st.caption("Distribution of accounts dropping below critical survival runway thresholds under official challenge twists.")

    scenarios_df = get_population_scenario_distributions(repo)

    col_tbl, col_chart = st.columns([1, 1.2])

    with col_tbl:
        st.markdown("**Shock Impact Matrix**")
        styled_df = scenarios_df.style.format({
            "Below 3M": "{:,}",
            "Below 6M": "{:,}",
            "Below 12M": "{:,}",
            "Below 3M (%)": "{:.1f}%",
            "Below 6M (%)": "{:.1f}%",
            "Below 12M (%)": "{:.1f}%"
        })
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        st.info(
            "💡 **Key Discovery:** Under the challenge's 55% EI layoff shock, **35.5% of the portfolio (1,596 accounts)** "
            "falls below 6 months of runway. When combined with a 15% household-bill increase, this surges to **38.9% (1,752 accounts)**."
        )

    with col_chart:
        # Grouped bar chart of shares below 6 months
        fig_bar = px.bar(
            scenarios_df,
            x="Scenario",
            y=["Below 3M (%)", "Below 6M (%)", "Below 12M (%)"],
            barmode="group",
            title="Share of Accounts Falling Below Runway Thresholds",
            color_discrete_sequence=[THEME["alert_red"], THEME["primary_orange"], THEME["accent_blue"]]
        )
        fig_bar.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title="Threshold",
            xaxis_title="",
            yaxis_title="% of Portfolio",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    st.markdown("---")

    # 3. Three Pillars of Hidden Intelligence Cards
    st.subheader("🏆 The 3 Breakthrough Behavioral Discoveries")
    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 18px; border-radius: 8px; border-left: 4px solid {THEME['success_green']};">
            <h4 style="color: {THEME['text_main']}; margin-top:0;">🛡️ 1. The Spousal Shield</h4>
            <p style="font-size: 24px; font-weight: bold; color: {THEME['success_green']}; margin-bottom: 5px;">0.00% Default Rate</p>
            <p style="font-size: 13px; color: {THEME['text_muted']};">
                Across 869 joint accounts (owner + authorized user), <b>zero accounts defaulted</b> and <b>zero entered negative balances</b> over 6 years. 
                100% of all 76 portfolio defaults occurred in solo accounts (14.15% default rate; &chi;&sup2; = 21.69, p = 3.2&times;10<sup>-6</sup>).
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 18px; border-radius: 8px; border-left: 4px solid {THEME['primary_orange']};">
            <h4 style="color: {THEME['text_main']}; margin-top:0;">🚨 2. The Statement Canary</h4>
            <p style="font-size: 24px; font-weight: bold; color: {THEME['primary_orange']}; margin-bottom: 5px;">23.7% Overdraft Rate</p>
            <p style="font-size: 13px; color: {THEME['text_muted']};">
                Customers requesting a <b>"statement after each transaction"</b> have a <b>4.3x higher overdraft rate</b> (23.66% vs 5.50%) and 
                nearly double the default rate (18.75%). What banks view as an admin setting is a behavioral canary for extreme cash-flow turbulence.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 18px; border-radius: 8px; border-left: 4px solid {THEME['alert_red']};">
            <h4 style="color: {THEME['text_main']}; margin-top:0;">📉 3. Inverted Resilience Paradox</h4>
            <p style="font-size: 24px; font-weight: bold; color: {THEME['alert_red']}; margin-bottom: 5px;">3.6 Mo Runway for Top 10%</p>
            <p style="font-size: 13px; color: {THEME['text_muted']};">
                High nominal earners crash fastest: Under a 55% EI shock, <b>84.4% of top-decile earners crash below 6 months</b> (median 3.6 mos) 
                due to massive dollar burn ($9k/mo gap), while low earners survive 38.1 months on modest living costs.
            </p>
        </div>
        """, unsafe_allow_html=True)
