"""
Screen 1: Portfolio Overview & Executive Discovery Dashboard
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from src.data.local_repository import LocalDataRepository
from src.services.discovery_engine import (
    get_population_summary,
    get_population_scenario_distributions,
    get_income_decile_discovery,
    get_preloan_early_warning_data,
    get_portfolio_scenario_runways,
)
from config.settings import THEME

def render_overview(repo: LocalDataRepository):
    st.markdown("## 🏠 Your portfolio snapshot")
    st.markdown(
        "A plain-language view of the supplied account data: what money usually comes in, "
        "what goes out, and how selected what-ifs change the picture."
    )

    summary = get_population_summary(repo)

    st.caption("Portfolio figures summarize account-level calculations—not all monthly rows pooled together.")
    kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
    with kpi1:
        st.metric("Accounts in data", f"{summary.total_accounts:,}")
    with kpi2:
        st.metric("Typical money in", f"${summary.median_I:,.0f}")
    with kpi3:
        st.metric("Typical spending", f"${summary.median_S:,.0f}")
    with kpi4:
        st.metric("Typical buffer", f"${summary.median_B:,.0f}")
    with kpi5:
        st.metric("Spending above money in", f"{summary.accounts_in_deficit:,}", f"{summary.pct_in_deficit}% of accounts")
    with kpi6:
        st.metric("Typical fixed costs", f"${summary.median_F:,.0f}")

    with st.expander("🧾 Where these portfolio numbers come from"):
        st.markdown(
            f"""
            The app first calculates one value per account, then takes the median across
            **{summary.total_accounts:,} accounts**:

            - **Typical money in:** median of each account's monthly `money_in` median = **${summary.median_I:,.2f}**.
            - **Typical spending:** median of each account's monthly `money_out` median = **${summary.median_S:,.2f}**.
            - **Typical fixed costs:** median of account-level medians of household bills + insurance + loan payments = **${summary.median_F:,.2f}**.
            - **Typical buffer:** median across accounts of each account's average `avg_daily_balance` over up to its latest six rows = **${summary.median_B:,.2f}**.
            - **Spending above money in:** {summary.accounts_in_deficit:,} / {summary.total_accounts:,} accounts, or **{summary.pct_in_deficit:.1f}%**, where account median spending exceeds account median money in.

            The word “typical” refers to medians, not a promise that every month will look this way.
            """
        )

    st.markdown("---")

    # 2. Portfolio Stress Under Challenge Scenarios
    st.subheader("⚡ What if the money picture changes?")
    st.caption(
        "These scenarios apply the same transparent rules to every account. They are what-ifs, not predictions."
    )

    scenarios_df = get_population_scenario_distributions(repo)
    scenario_display_df = scenarios_df.copy()
    scenario_display_df["Scenario"] = scenario_display_df["Scenario"].replace(
        {
            "Baseline (Status Quo)": "Keep things steady",
            "Job Loss (EI @ 55%)": "Money-in at 55% of usual (simulation)",
            "Emergency Repair (Cost = S)": "One-off cost = typical monthly spending",
            "Combined Shock (EI 55% + Bills +15%)": "55% money-in + 15% household bills",
        }
    )

    col_tbl, col_chart = st.columns([1, 1.2])

    with col_tbl:
        st.markdown("**Accounts with less than the runway shown**")
        styled_df = scenario_display_df.style.format({
            "Below 3M": "{:,}",
            "Below 6M": "{:,}",
            "Below 12M": "{:,}",
            "Below 3M (%)": "{:.1f}%",
            "Below 6M (%)": "{:.1f}%",
            "Below 12M (%)": "{:.1f}%"
        })
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        ei_row = scenarios_df.loc[scenarios_df["Scenario"] == "Job Loss (EI @ 55%)"].iloc[0]
        combined_row = scenarios_df.loc[
            scenarios_df["Scenario"] == "Combined Shock (EI 55% + Bills +15%)"
        ].iloc[0]
        st.info(
            f"In the simulated 55% money-in scenario, {int(ei_row['Below 6M']):,} of "
            f"{summary.total_accounts:,} accounts ({ei_row['Below 6M (%)']:.1f}%) have less than "
            f"six months of Judge Match runway. The combined bill scenario gives "
            f"{int(combined_row['Below 6M']):,} ({combined_row['Below 6M (%)']:.1f}%). "
            "That is a scenario result—not a forecast or confirmed job-loss outcome."
        )

    with col_chart:
        # Grouped bar chart of shares below 6 months
        fig_bar = px.bar(
            scenario_display_df,
            x="Scenario",
            y=["Below 3M (%)", "Below 6M (%)", "Below 12M (%)"],
            barmode="group",
            title="How many accounts fall below each runway marker?",
            color_discrete_sequence=[THEME["alert_red"], THEME["primary_orange"], THEME["accent_blue"]]
        )
        fig_bar.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            legend_title="Threshold",
            xaxis_title="",
            yaxis_title="% of accounts",
            margin=dict(l=20, r=20, t=40, b=20)
        )
        st.plotly_chart(fig_bar, use_container_width=True)
    with st.expander("🧮 How the scenario counts are calculated"):
        st.markdown(
            """
            For each account, the app applies the scenario to its own typical money-in,
            spending, bills, and buffer. Runway is `buffer after one-off costs ÷ positive
            monthly gap`, capped at 120 months; a non-positive gap is shown as 120+ months
            when the buffer is positive. Runway is rounded to one decimal **before**
            strict `<3`, `<6`, and `<12` month counts are calculated. The percentage is
            `accounts below the marker ÷ accounts with monthly records × 100`.
            """
        )
        st.caption(
            f"Current 55% money-in scenario: {int(ei_row['Below 6M']):,} / "
            f"{int(ei_row['Accounts']):,} accounts ({ei_row['Below 6M (%)']:.1f}%) "
            "are below 6 months."
        )

    with st.expander("🎛️ Try a live portfolio what-if"):
        st.caption(
            "Move the dials to change the assumptions. The account-level runways and chart "
            "recalculate from the supplied data; nothing is predicted."
        )
        dial1, dial2, dial3 = st.columns(3)
        with dial1:
            income_level = st.slider(
                "Money-in level",
                min_value=0,
                max_value=150,
                value=55,
                step=5,
                format="%d%%",
                key="portfolio_whatif_income",
            )
        with dial2:
            household_change = st.slider(
                "Household-bill change",
                min_value=-30,
                max_value=100,
                value=0,
                step=5,
                format="%d%%",
                key="portfolio_whatif_bills",
            )
        with dial3:
            one_off_months = st.slider(
                "One-off cost (typical spending months)",
                min_value=0.0,
                max_value=3.0,
                value=0.0,
                step=0.25,
                key="portfolio_whatif_oneoff",
            )

        portfolio_runways = get_portfolio_scenario_runways(
            repo,
            income_multiplier=income_level / 100,
            household_bill_change=household_change / 100,
            one_off_spend_multiplier=one_off_months,
        )
        account_count = len(portfolio_runways)
        selected_counts = {
            threshold: int((portfolio_runways["runway_months"] < threshold).sum())
            for threshold in (3, 6, 12)
        }
        selected_rates = {
            threshold: count / account_count * 100
            for threshold, count in selected_counts.items()
        }

        result_cols = st.columns(3)
        for column, threshold in zip(result_cols, (3, 6, 12)):
            column.metric(
                f"Below {threshold} months",
                f"{selected_counts[threshold]:,} accounts",
                f"{selected_rates[threshold]:.1f}% of {account_count:,}",
            )

        custom_fig = go.Figure(
            go.Bar(
                x=[f"Below {threshold} months" for threshold in (3, 6, 12)],
                y=[selected_counts[threshold] for threshold in (3, 6, 12)],
                text=[
                    f"{selected_counts[threshold]:,} · {selected_rates[threshold]:.1f}%"
                    for threshold in (3, 6, 12)
                ],
                textposition="outside",
                marker_color=[THEME["alert_red"], THEME["primary_orange"], THEME["accent_blue"]],
                hovertemplate="%{x}<br>%{y:,} accounts<extra></extra>",
            )
        )
        custom_fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Runway threshold",
            yaxis_title="Accounts below threshold",
            margin=dict(l=20, r=20, t=25, b=20),
        )
        st.plotly_chart(custom_fig, use_container_width=True)
        with st.expander("🧾 Show the calculation"):
            st.code(
                "\n".join(
                    [
                        f"Scenario money-in multiplier = {income_level}%",
                        f"Scenario household-bill change = {household_change}%",
                        f"One-off cost = {one_off_months:.2f} × each account's typical spending",
                        "For each account: apply the selected shock; compute buffer after one-off and monthly gap.",
                        "Runway = 0 if the remaining buffer is non-positive; 120+ if the gap is non-positive; otherwise min(120, buffer ÷ gap), rounded to one decimal.",
                        f"Displayed shares = accounts below threshold ÷ {account_count:,} accounts × 100.",
                    ]
                ),
                language="text",
            )
            st.caption(
                "Threshold counts use the same one-decimal official runway as the main portfolio matrix."
            )

    st.markdown("---")

    # 3. Evidence-led portfolio observations
    st.subheader("📊 A few patterns worth a closer look")
    deciles = get_income_decile_discovery(repo)
    preloan = get_preloan_early_warning_data(repo)
    c1, c2, c3 = st.columns(3)

    with c1:
        bottom = deciles.iloc[0]
        top = deciles.iloc[-1]
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 18px; border-radius: 8px; border-left: 4px solid {THEME['success_green']};">
            <h4 style="color: {THEME['text_main']}; margin-top:0;">1. Lowest money-in group · simulated 55% scenario</h4>
            <p style="font-size: 24px; font-weight: bold; color: {THEME['success_green']}; margin-bottom: 5px;">{bottom['Median Runway (EI 55%)']:.1f} months</p>
            <p style="font-size: 13px; color: {THEME['text_muted']};">
                Median one-decimal Judge Match runway for {int(bottom['Accounts'])} accounts in the lowest money-in decile.
                Money-in is not verified payroll. This is a scenario comparison, not observed job-loss outcomes.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 18px; border-radius: 8px; border-left: 4px solid {THEME['primary_orange']};">
            <h4 style="color: {THEME['text_main']}; margin-top:0;">2. Highest money-in group · simulated 55% scenario</h4>
            <p style="font-size: 24px; font-weight: bold; color: {THEME['primary_orange']}; margin-bottom: 5px;">{top['% Below 6 Months']:.1f}% below 6 months</p>
            <p style="font-size: 13px; color: {THEME['text_muted']};">
                {int(top['Accounts Below 6 Months'])} of {int(top['Accounts'])} accounts have less than six months of simulated runway.
                Deciles are calculated dynamically from account-level median money-in.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        preloan_text = (
            f"{preloan['cohort_size']:,} of {preloan.get('eligible_loan_count', 0):,} loans had "
            "at least six pre-origination monthly records."
        )
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 18px; border-radius: 8px; border-left: 4px solid {THEME['alert_red']};">
            <h4 style="color: {THEME['text_main']}; margin-top:0;">3. Pre-loan buffer association</h4>
            <p style="font-size: 20px; font-weight: bold; color: {THEME['alert_red']}; margin-bottom: 5px;">{preloan_text}</p>
            <p style="font-size: 13px; color: {THEME['text_muted']};">
                Latest six available pre-start months only. The supplied default flag is an outcome association;
                running loans are not necessarily completed, and association does not establish cause.
            </p>
        </div>
        """, unsafe_allow_html=True)
