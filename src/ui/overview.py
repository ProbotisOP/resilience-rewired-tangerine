"""
Screen 1: Portfolio Overview & Executive Discovery Dashboard
"""

import streamlit as st
from src.ui.charting import axis_style, base_options, render_chart

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
    st.markdown("## 🏠 Financial resilience at a glance")
    st.markdown(
        "A clear view of cash flow, savings buffers and potential pressure points across the accounts in this dataset. "
        "Compare simple what-if scenarios to support planning and customer conversations."
    )

    summary = get_population_summary(repo)

    st.caption("Portfolio figures summarize each account first, then show the middle value across accounts.")
    st.info(
        f"**Portfolio signal:** {summary.accounts_in_deficit:,} of {summary.total_accounts:,} accounts "
        f"({summary.pct_in_deficit:.1f}%) have typical monthly spending above typical money coming in. "
        "Use the what-if below to explore how a change in income, bills or a one-time cost could affect the buffer."
    )
    kpi_row1 = st.columns(3)
    kpi_row2 = st.columns(3)
    with kpi_row1[0]:
        st.metric("Accounts in data", f"{summary.total_accounts:,}")
    with kpi_row1[1]:
        st.metric("Typical monthly money in", f"${summary.median_I:,.0f}")
    with kpi_row1[2]:
        st.metric("Typical spending", f"${summary.median_S:,.0f}")
    with kpi_row2[0]:
        st.metric("Typical available balance", f"${summary.median_B:,.0f}")
    with kpi_row2[1]:
        st.metric("Accounts spending above inflow", f"{summary.accounts_in_deficit:,}", f"{summary.pct_in_deficit}% of accounts")
    with kpi_row2[2]:
        st.metric("Typical monthly recurring costs", f"${summary.median_F:,.0f}")

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
    st.subheader("⚡ How could the portfolio handle a change?")
    st.caption(
        "These scenarios apply the same transparent rules to every account. They are what-ifs, not predictions."
    )

    scenarios_df = get_population_scenario_distributions(repo)
    scenario_display_df = scenarios_df.copy()
    scenario_display_df["Scenario"] = scenario_display_df["Scenario"].replace(
        {
            "Baseline (Status Quo)": "Keep things steady",
            "Job Loss (EI @ 55%)": "Money-in falls to 55% (what-if)",
            "Emergency Repair (Cost = S)": "One-time cost of one typical spending month",
            "Combined Shock (EI 55% + Bills +15%)": "Money-in at 55% + bills up 15% (what-if)",
        }
    )

    col_tbl, col_chart = st.columns([1, 1.2])

    with col_tbl:
        st.markdown("**Accounts with less than the time shown**")
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
            f"six months by the runway measure. The combined bill scenario gives "
            f"{int(combined_row['Below 6M']):,} ({combined_row['Below 6M (%)']:.1f}%). "
            "That is a scenario result—not a forecast or confirmed job-loss outcome."
        )

    with col_chart:
        # Grouped bar chart of shares below 6 months
        scenario_labels = [
            "Baseline",
            "Money-in at 55% (simulation)",
            "One-off cost = monthly spending",
            "55% money-in + bills up 15%",
        ]
        scenario_options = base_options()
        scenario_options.update(
            {
                "grid": {"left": 12, "right": 24, "top": 54, "bottom": 48, "containLabel": True},
                "xAxis": {"type": "category", "data": scenario_labels, "axisLabel": {"color": THEME["text_muted"], "interval": 0, "rotate": 12, "hideOverlap": True}, **{k: v for k, v in axis_style().items() if k != "axisLabel"}},
                "yAxis": {"type": "value", "name": "% of accounts", "min": 0, "max": 100, "axisLabel": {"color": THEME["text_muted"], "formatter": "{value}%"}, "splitLine": {"lineStyle": {"color": "rgba(141,153,174,.16)"}}},
                "series": [
                    {"name": f"Below {threshold} months", "type": "bar", "barMaxWidth": 28, "data": scenario_display_df[f"Below {threshold}M (%)"].round(1).tolist(), "itemStyle": {"color": color, "borderRadius": [5, 5, 0, 0]}, "emphasis": {"focus": "series"}}
                    for threshold, color in ((3, THEME["alert_red"]), (6, THEME["primary_orange"]), (12, THEME["accent_blue"]))
                ],
            }
        )
        scenario_options["tooltip"]["trigger"] = "axis"
        render_chart(scenario_options, key="portfolio-runway-distribution", height=430)
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
                "Money-in level (usual = 100%)",
                min_value=0,
                max_value=150,
                value=55,
                step=5,
                format="%d%%",
                key="portfolio_whatif_income",
                help=(
                    "Sets monthly money-in as a share of its usual level. "
                    "For example, 55% models 45% less money-in; 100% keeps it usual. "
                    "This is a scenario, not a forecast."
                ),
            )
        with dial2:
            if st.session_state.get("portfolio_whatif_bills", 0) < 0:
                st.session_state["portfolio_whatif_bills"] = 0
            household_change = st.slider(
                "Household-bill increase",
                min_value=0,
                max_value=100,
                value=0,
                step=5,
                format="%d%%",
                key="portfolio_whatif_bills",
                help=(
                    "Adds to the usual household bills. For example, 15% means "
                    "bills are 15% higher; 0% keeps them unchanged."
                ),
            )
        with dial3:
            one_off_months = st.slider(
                "One-off cost (typical spending months)",
                min_value=0.0,
                max_value=3.0,
                value=0.0,
                step=0.25,
                key="portfolio_whatif_oneoff",
                help=(
                    "A one-time cost measured in typical monthly spending. "
                    "For example, 1.0 means one usual month of spending; 0 means no cost."
                ),
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

        custom_options = base_options()
        custom_options.update(
            {
                "grid": {"left": 16, "right": 24, "top": 28, "bottom": 42, "containLabel": True},
                "legend": {"show": False},
                "xAxis": {"type": "category", "name": "Runway threshold", "data": [f"Below {threshold} months" for threshold in (3, 6, 12)], "axisLabel": {"color": THEME["text_muted"]}, **{k: v for k, v in axis_style().items() if k != "axisLabel"}},
                "yAxis": {"type": "value", "name": "Accounts below threshold", "axisLabel": {"color": THEME["text_muted"], "formatter": "{value}"}, "splitLine": {"lineStyle": {"color": "rgba(141,153,174,.16)"}}},
                "series": [{
                    "name": "Accounts below threshold",
                    "type": "bar",
                    "barMaxWidth": 46,
                    "data": [
                        {"value": selected_counts[threshold], "itemStyle": {"color": color, "borderRadius": [6, 6, 0, 0]}, "rate": round(selected_rates[threshold], 1)}
                        for threshold, color in zip((3, 6, 12), (THEME["alert_red"], THEME["primary_orange"], THEME["accent_blue"]))
                    ],
                    "label": {"show": True, "position": "top", "color": THEME["text_main"], "formatter": "{c}"},
                    "emphasis": {"focus": "series", "itemStyle": {"shadowBlur": 14, "shadowColor": "rgba(255,91,0,.32)"}},
                }],
            }
        )
        custom_options["tooltip"]["trigger"] = "item"
        render_chart(custom_options, key="portfolio-live-whatif", height=380)
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
    st.subheader("📊 Portfolio signals to explore")
    st.caption("Three useful starting points for a business conversation. Each reflects the supplied data and a defined comparison, not a prediction.")
    deciles = get_income_decile_discovery(repo)
    preloan = get_preloan_early_warning_data(repo)
    c1, c2, c3 = st.columns(3)

    with c1:
        bottom = deciles.iloc[0]
        top = deciles.iloc[-1]
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 18px; border-radius: 8px; border-left: 4px solid {THEME['success_green']};">
            <h4 style="color: {THEME['text_main']}; margin-top:0;">Lower money-in group · 55% what-if</h4>
            <p style="font-size: 24px; font-weight: bold; color: {THEME['success_green']}; margin-bottom: 5px;">{bottom['Median Runway (EI 55%)']:.1f} months</p>
            <p style="font-size: 13px; color: {THEME['text_muted']};">
                This is the middle estimated time the available balance could cover a monthly shortfall across
                {int(bottom['Accounts'])} accounts, if recorded money coming in were set to 55% of usual.
                The records do not verify pay or show actual job-loss outcomes.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 18px; border-radius: 8px; border-left: 4px solid {THEME['primary_orange']};">
            <h4 style="color: {THEME['text_main']}; margin-top:0;">Higher money-in group · 55% what-if</h4>
            <p style="font-size: 24px; font-weight: bold; color: {THEME['primary_orange']}; margin-bottom: 5px;">{int(top['Accounts Below 6 Months'])} of {int(top['Accounts'])} under 6 months</p>
            <p style="font-size: 13px; color: {THEME['text_muted']};">
                If recorded money coming in were set to 55% of usual, {top['% Below 6 Months']:.1f}% of these accounts
                would have less than six months of estimated buffer coverage. Groups are refreshed from the supplied records.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with c3:
        preloan_text = (
            f"{preloan['cohort_size']:,} of {preloan.get('eligible_loan_count', 0):,} loans have "
            "at least six earlier monthly records."
        )
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 18px; border-radius: 8px; border-left: 4px solid {THEME['alert_red']};">
            <h4 style="color: {THEME['text_main']}; margin-top:0;">Savings before a loan</h4>
            <p style="font-size: 20px; font-weight: bold; color: {THEME['alert_red']}; margin-bottom: 5px;">{preloan_text}</p>
            <p style="font-size: 13px; color: {THEME['text_muted']};">
                For {preloan['cohort_size']:,} loans with at least six earlier monthly records, we compare savings before the loan with its recorded status.
                Some loans may still be active. This comparison cannot explain why an outcome happened.
            </p>
        </div>
        """, unsafe_allow_html=True)
