"""
Screen 2: Customer Explorer & Longitudinal Account Intelligence
"""

import streamlit as st
import pandas as pd

from src.data.local_repository import LocalDataRepository
from src.services.customer_profile import get_customer_profile
from src.services.baseline_metrics import compute_official_baseline
from config.settings import THEME
from src.ui.charting import axis_style, base_options, render_chart


def _sync_active_account():
    """Apply the selector value before the sidebar and page rerender."""
    st.session_state["active_account_id"] = st.session_state["customer_account_selector"]


def _select_sample_account(account_id: int):
    """Keep the page selector and the shared account-in-focus state aligned."""
    st.session_state["customer_account_selector"] = account_id
    st.session_state["active_account_id"] = account_id

def render_customer_explorer(repo: LocalDataRepository):
    st.markdown("## 👤 Explore an account")
    st.caption(
        "Choose an account to review its monthly history and key figures. These records are only part of its financial picture."
    )

    # 1. Select from all supplied account IDs
    valid_accounts = repo.get_all_accounts()
    current_account = st.session_state.get("active_account_id", valid_accounts[0])
    if current_account not in valid_accounts:
        current_account = valid_accounts[0]
    if st.session_state.get("customer_account_selector") != current_account:
        st.session_state["customer_account_selector"] = current_account
    col_input, col_preset = st.columns([1, 2])
    
    with col_input:
        selected_id = st.selectbox(
            "Choose an account",
            options=valid_accounts,
            index=valid_accounts.index(current_account),
            format_func=lambda value: f"Account #{value}",
            key="customer_account_selector",
            on_change=_sync_active_account,
        )
        st.session_state["active_account_id"] = selected_id

    with col_preset:
        st.write("Or jump to a sample:")
        b1, b2, b3, b4 = st.columns(4)
        b1.button(
            "Account 20111", use_container_width=True,
            on_click=_select_sample_account, args=(20111,),
        )
        b2.button(
            "Account 55447", use_container_width=True,
            on_click=_select_sample_account, args=(55447,),
        )
        b3.button(
            "Account 62236", use_container_width=True,
            on_click=_select_sample_account, args=(62236,),
        )
        b4.button(
            "Account 74958", use_container_width=True,
            on_click=_select_sample_account, args=(74958,),
        )

    account_id = st.session_state["active_account_id"]
    monthly_df = repo.get_monthly_summary(account_id)
    monthly_df = monthly_df.sort_values("month").copy()
    acc_meta = repo.get_account_meta(account_id)
    if acc_meta is None or monthly_df.empty:
        st.error(f"❌ Account ID #{account_id} not found in the 4,500 retail account directory. Please enter a valid account ID.")
        return
    baseline = compute_official_baseline(account_id, monthly_df, acc_meta)
    profile = get_customer_profile(account_id, repo, account_meta=acc_meta, baseline=baseline)
    if not profile:
        st.error(f"❌ Account ID #{account_id} not found in the 4,500 retail account directory. Please enter a valid account ID.")
        return
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
    st.subheader("📐 A typical month")
    metric_row1 = st.columns(4)
    metric_row2 = st.columns(3)
    with metric_row1[0]:
        st.metric("Money in", f"${baseline.I:,.2f}", help="Median of monthly money in.")
    with metric_row1[1]:
        st.metric("Fixed costs", f"${baseline.F:,.2f}", help="Median of monthly household bills, insurance and loan payments added together.")
    with metric_row1[2]:
        st.metric("Spending", f"${baseline.S:,.2f}", help="Median of monthly money out.")
    with metric_row1[3]:
        st.metric("Buffer", f"${baseline.B:,.2f}", help="Average daily balance across up to the latest six monthly rows.")
    with metric_row2[0]:
        st.metric("Household bills", f"${baseline.H:,.2f}", help="Median of monthly household bills.")
    with metric_row2[1]:
        st.metric("Recorded loan payment", f"${baseline.P:,.2f}", help="Supplied payment for a loan marked C or D; otherwise $0.")
    with metric_row2[2]:
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
    st.subheader("📈 See the monthly history")
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
        chart_months = visible_monthly_df["month"].astype(str).tolist()
        cashflow_options = base_options(zoom=True)
        cashflow_options.update(
            {
                "grid": {"left": 20, "right": 24, "top": 52, "bottom": 78, "containLabel": True},
                "xAxis": {
                    "type": "category",
                    "boundaryGap": False,
                    "name": "Month",
                    "nameLocation": "middle",
                    "nameGap": 30,
                    "data": chart_months,
                    "axisLabel": {"color": THEME["text_muted"], "hideOverlap": True},
                    **{k: v for k, v in axis_style().items() if k != "axisLabel"},
                },
                "yAxis": {
                    "type": "value",
                    "name": "CAD ($)",
                    "axisLabel": {"color": THEME["text_muted"], "formatter": "${value}"},
                    "axisLine": {"show": False},
                    "splitLine": {"lineStyle": {"color": "rgba(141,153,174,.16)"}},
                },
                "series": [
                    {
                        "name": "Money in",
                        "type": "line",
                        "data": visible_monthly_df["money_in"].round(2).tolist(),
                        "showSymbol": False,
                        "lineStyle": {"color": THEME["success_green"], "width": 3},
                        "itemStyle": {"color": THEME["success_green"]},
                        "emphasis": {"focus": "series"},
                        "markLine": {
                            "symbol": "none",
                            "lineStyle": {"type": "dashed", "color": THEME["success_green"], "opacity": 0.7},
                            "label": {"formatter": f"Typical in ${baseline.I:,.0f}", "color": THEME["success_green"]},
                            "data": [{"yAxis": baseline.I}],
                        },
                    },
                    {
                        "name": "Spending",
                        "type": "line",
                        "data": visible_monthly_df["money_out"].round(2).tolist(),
                        "showSymbol": False,
                        "lineStyle": {"color": THEME["primary_orange"], "width": 3},
                        "itemStyle": {"color": THEME["primary_orange"]},
                        "emphasis": {"focus": "series"},
                        "markLine": {
                            "symbol": "none",
                            "lineStyle": {"type": "dashed", "color": THEME["primary_orange"], "opacity": 0.7},
                            "label": {"formatter": f"Typical spend ${baseline.S:,.0f}", "color": THEME["primary_orange"]},
                            "data": [{"yAxis": baseline.S}],
                        },
                    },
                ],
            }
        )
        render_chart(cashflow_options, key=f"account-cashflow-{account_id}", height=430)

    with t_tab2:
        balance_months = visible_monthly_df["month"].astype(str).tolist()
        balance_options = base_options(zoom=True)
        balance_options["legend"] = {"data": ["Average daily balance", "Days below zero"], "top": 4, "textStyle": {"color": THEME["text_muted"]}}
        balance_options["grid"] = [
            {"left": 24, "right": 24, "top": 52, "height": "42%", "containLabel": True},
            {"left": 24, "right": 24, "top": "61%", "height": "24%", "containLabel": True},
        ]
        balance_options["xAxis"] = [
            {"type": "category", "gridIndex": 0, "data": balance_months, "axisLabel": {"show": False}, **axis_style()},
            {"type": "category", "gridIndex": 1, "data": balance_months, "axisLabel": {"color": THEME["text_muted"], "hideOverlap": True}, **{k: v for k, v in axis_style().items() if k != "axisLabel"}},
        ]
        balance_options["yAxis"] = [
            {"type": "value", "gridIndex": 0, "name": "Balance (CAD)", "axisLabel": {"color": THEME["text_muted"], "formatter": "${value}"}, "splitLine": {"lineStyle": {"color": "rgba(141,153,174,.16)"}}},
            {"type": "value", "gridIndex": 1, "name": "Below-zero days", "min": 0, "max": 31, "interval": 10, "axisLabel": {"color": THEME["text_muted"]}, "splitLine": {"lineStyle": {"color": "rgba(141,153,174,.16)"}}},
        ]
        balance_options["dataZoom"][0]["xAxisIndex"] = [0, 1]
        balance_options["dataZoom"][1]["xAxisIndex"] = [0, 1]
        balance_options["series"] = [
            {
                "name": "Average daily balance",
                "type": "line",
                "xAxisIndex": 0,
                "yAxisIndex": 0,
                "data": visible_monthly_df["avg_daily_balance"].round(2).tolist(),
                "showSymbol": False,
                "lineStyle": {"color": THEME["primary_orange"], "width": 3},
                "areaStyle": {"color": "rgba(255,91,0,.10)"},
                "emphasis": {"focus": "series"},
            },
            {
                "name": "Days below zero",
                "type": "bar",
                "xAxisIndex": 1,
                "yAxisIndex": 1,
                "data": visible_monthly_df["days_below_zero"].fillna(0).astype(int).tolist(),
                "barMaxWidth": 18,
                "itemStyle": {"color": THEME["alert_red"], "borderRadius": [4, 4, 0, 0]},
                "emphasis": {"focus": "series"},
            },
        ]
        balance_options["tooltip"]["axisPointer"] = {"type": "line"}
        render_chart(balance_options, key=f"account-balance-{account_id}", height=490)
