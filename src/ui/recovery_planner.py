"""Account-specific savings goal and shock backup planner."""

import streamlit as st

from config.scenarios import OFFICIAL_PRESETS, ShockScenario
from config.settings import THEME
from src.data.local_repository import LocalDataRepository
from src.services.baseline_metrics import compute_official_baseline
from src.services.recovery_planner import (
    build_backup_plan,
    build_goal_plan,
    build_resilience_gap_plan,
    recent_six_month_median_net_cash_flow,
)
from src.services.shock_engine import simulate_shock
from src.ui.charting import axis_style, base_options, render_chart
from src.ui.presentation import scenario_display_name


def _runway_label(buffer: float, gap: float, runway: float) -> str:
    if buffer <= 0:
        return "0 months"
    if gap <= 0:
        return "120+ months"
    return f"{runway:.1f} months"


def _money(value: float) -> str:
    return f"${value:,.2f}"


def _linked_records(repo: LocalDataRepository, account_id: int, account_meta: dict, baseline):
    """Show loan and scheduled-payment records linked to this account."""
    with st.expander("🔗 Account records used for follow-up ideas"):
        loan_cols = st.columns(2)
        if account_meta.get("has_loan"):
            loan_cols[0].markdown("**Loan record**")
            loan_cols[0].write(
                f"{account_meta.get('loan_status_meaning', 'Status not described')} · "
                f"original amount {_money(float(account_meta.get('loan_amount', 0) or 0))} · "
                f"{int(account_meta.get('loan_duration_months', 0) or 0)} months"
            )
            if baseline.has_running_loan:
                loan_cols[0].caption(
                    f"The loan is marked as running at the end of 2025. Its recorded monthly payment is "
                    f"{_money(baseline.P)}. Monthly spending already includes recorded loan payments, "
                    "so this amount is shown as context and is not added again to the what-if."
                )
            else:
                loan_cols[0].caption(
                    "The loan is marked as finished in the supplied records. Its payment is not treated as ongoing."
                )
        else:
            loan_cols[0].markdown("**Loan record**")
            loan_cols[0].caption("No loan is listed for this account in the supplied loan file.")

        orders = repo.standing_orders
        account_orders = orders.loc[orders["account_id"] == account_id].copy()
        loan_cols[1].markdown("**Scheduled-payment instructions**")
        if account_orders.empty:
            loan_cols[1].caption("No scheduled-payment instructions are listed for this account.")
        else:
            order_summary = (
                account_orders["purpose"].fillna("").replace("", "Other / not labelled")
                .value_counts()
                .rename_axis("Label")
                .reset_index(name="Instructions")
            )
            loan_cols[1].dataframe(order_summary, use_container_width=True, hide_index=True)
            loan_cols[1].caption(
                f"The file lists {len(account_orders)} instructions totalling "
                f"{_money(float(account_orders['amount'].sum()))}. This is an undated snapshot "
                "with no payment frequency, so the total is not treated as a monthly bill."
            )


def render_recovery_planner(repo: LocalDataRepository):
    st.markdown("## 🧭 Savings goal and shock backup plan")
    st.caption(
        "First, plan a savings goal. Then choose a shock and see what extra buffer and monthly change "
        "the numbers would require. Every figure updates from this account's records."
    )

    account_id = st.session_state.get("active_account_id")
    if account_id not in repo.get_all_accounts():
        st.error("Choose an account from the account list before building a plan.")
        return

    monthly_df = repo.get_monthly_summary(account_id)
    account_meta = repo.get_account_meta(account_id)
    if account_meta is None or monthly_df.empty:
        st.error(f"Account #{account_id} has no usable monthly records in the supplied data.")
        return

    baseline = compute_official_baseline(account_id, monthly_df, account_meta)
    recent_net = recent_six_month_median_net_cash_flow(baseline.last_6_months_summary)

    st.markdown(f"### Account #{account_id} · starting point")
    st.caption(
        f"Based on {baseline.history_months} available monthly records. Figures describe the supplied data, "
        "not the account holder's complete finances."
    )
    snapshot = st.columns(4)
    snapshot[0].metric("Usual money in / month", _money(baseline.I))
    snapshot[1].metric("Usual spending / month", _money(baseline.S))
    snapshot[2].metric("Household bills / month", _money(baseline.H))
    snapshot[3].metric("Current balance buffer", _money(baseline.B))
    detail = st.columns(3)
    detail[0].metric(
        "Fixed costs / month",
        _money(baseline.F),
        help="Recorded household bills, insurance and loan payments added together. This may not include every essential cost.",
    )
    detail[1].metric(
        "Active loan payment",
        _money(baseline.P),
        help="Payment from the loan file when its status is marked as running at the end of 2025.",
    )
    detail[2].metric(
        "Recent money left over / month",
        _money(recent_net) if recent_net is not None else "Unavailable",
        help="Middle value of money-in minus money-out across up to the latest six available records. This is historical, not guaranteed savings capacity.",
    )
    st.caption(
        "The active-loan payment is a cross-check from the linked loan file. It may already be included in fixed costs; "
        "the plan does not add it twice."
    )

    with st.expander("How to read this starting point"):
        st.markdown(
            "The app uses the middle monthly money-in, spending and household-bill amounts. "
            "The buffer is the average daily balance across up to the latest six available monthly records. "
            "Fixed costs combine household bills, insurance and recorded loan payments. "
            "These are separate measures: fixed costs are not added on top of spending in the shock calculation."
        )

    st.markdown("---")
    st.markdown("### 1 · Set a savings-buffer goal")
    st.caption(
        "Choose how many months of essential costs to hold. The fixed-cost figure is only a starting point; "
        "edit it to match the monthly costs you want this goal to cover."
    )
    goal_controls = st.columns(3)
    with goal_controls[0]:
        goal_months = st.select_slider(
            "Months of costs to cover",
            options=[1, 2, 3, 4, 6, 9, 12],
            value=3,
            key=f"planner_goal_months_{account_id}",
        )
    with goal_controls[1]:
        essential_reference = baseline.F if baseline.F > 0 else baseline.P
        essential_default = min(max(0.0, essential_reference), 1_000_000.0)
        essential_cost = st.number_input(
            "Essential costs to cover each month ($)",
            min_value=0.0,
            max_value=1_000_000.0,
            value=essential_default,
            step=100.0,
            key=f"planner_essential_cost_{account_id}",
            help="Starts with fixed costs in the monthly records; if those are zero, it uses a separately listed running-loan payment when available. Check whether that payment is already included, then edit to cover the costs you choose.",
        )
    with goal_controls[2]:
        monthly_saving = st.number_input(
            "Monthly amount to try saving ($)",
            min_value=0.0,
            max_value=1_000_000.0,
            value=0.0,
            step=50.0,
            key=f"planner_monthly_saving_{account_id}",
            help="This is an amount to test, not a recommendation. The app does not know how much the customer can afford to save.",
        )

    essential_for_goal = essential_cost if essential_cost > 0 else None
    if essential_for_goal is None and baseline.F > 0:
        # A zero entered value means use the visible fixed-cost starting point.
        essential_for_goal = baseline.F
    if baseline.F <= 0 and baseline.P > 0:
        st.info(
            f"No fixed costs are recorded in the monthly summaries for this account, but its linked loan record "
            f"lists a {_money(baseline.P)} monthly payment. The goal starts from that amount. "
            "Confirm whether it is already reflected in spending and add any other essential costs you want covered."
        )
    goal = build_goal_plan(
        baseline,
        target_months=goal_months,
        custom_monthly_savings=monthly_saving,
        essential_monthly_cost=essential_for_goal,
    )

    if goal.emergency_target is None:
        st.warning("Enter a monthly essential-cost amount to calculate the savings goal.")
    else:
        goal_cols = st.columns(4)
        goal_cols[0].metric("Goal balance", _money(goal.emergency_target))
        goal_cols[1].metric("Current recorded buffer", _money(goal.current_buffer))
        goal_cols[2].metric("Still needed", _money(goal.funding_gap or 0.0))
        goal_cols[3].metric(
            "Time at the amount you entered",
            f"{goal.months_to_goal} months" if goal.months_to_goal is not None else "Enter an amount",
        )
        ratio = (
            min(1.0, max(0.0, goal.current_buffer / goal.emergency_target))
            if goal.emergency_target > 0
            else 0.0
        )
        st.progress(ratio, text=f"{ratio:.0%} of the selected goal covered by the recorded buffer")
        if goal.is_target_met:
            st.success("The recorded buffer already meets this selected goal.")
        elif monthly_saving <= 0:
            st.info(
                f"The goal is {_money(goal.funding_gap or 0.0)} above the recorded buffer. "
                "Enter a monthly amount to see a simple time-to-goal estimate."
            )
        else:
            st.info(
                f"At the amount you entered ({_money(monthly_saving)} per month), "
                f"the remaining {_money(goal.funding_gap or 0.0)} would take about "
                f"{goal.months_to_goal} months to build."
            )
        if recent_net is not None:
            st.caption(
                f"Reference only: recent monthly money-in minus spending was {_money(recent_net)} "
                "at the middle value across up to six available records. It is not assumed to be available to save."
            )

    with st.expander("Show the savings-goal math"):
        st.markdown(
            f"**Goal balance** = {goal_months} months × {_money(essential_for_goal or 0.0)} "
            f"essential costs = {_money(goal.emergency_target or 0.0)}.  \n"
            f"**Still needed** = goal balance − recorded buffer = {_money(goal.funding_gap or 0.0)}.  \n"
            "**Time estimate** = still needed ÷ the monthly amount you chose, rounded up to a whole month."
        )
        st.caption(
            "The recorded buffer is based on average daily balances. The source data does not identify "
            "which part is immediately accessible savings."
        )

    st.markdown("---")
    st.markdown("### 2 · Prepare for a what-if")
    st.caption(
        "Select a challenge example, then change the assumptions. Money-in means recorded deposits and transfers; "
        "it is not verified pay or proof of benefit eligibility."
    )

    default_scenario = st.session_state.get("active_preset_idx", 1)
    if not isinstance(default_scenario, int) or not 0 <= default_scenario < len(OFFICIAL_PRESETS):
        default_scenario = 1
    if "planner_scenario_idx" not in st.session_state:
        st.session_state["planner_scenario_idx"] = default_scenario
    selected_idx = st.selectbox(
        "What should we test?",
        options=range(len(OFFICIAL_PRESETS)),
        format_func=lambda index: scenario_display_name(OFFICIAL_PRESETS[index]),
        key="planner_scenario_idx",
    )
    preset = OFFICIAL_PRESETS[selected_idx]

    income_key = f"planner_income_{account_id}_{preset.scenario_id}"
    bills_key = f"planner_bills_{account_id}_{preset.scenario_id}"
    cost_key = f"planner_cost_{account_id}_{preset.scenario_id}"
    if st.session_state.get(bills_key, int(preset.household_bills_pct * 100)) < 0:
        st.session_state[bills_key] = 0
    default_cost = min(
        1_000_000.0,
        max(0.0, preset.one_off_spend_multiplier * baseline.S + preset.one_off_fixed_amount),
    )
    shock_cols = st.columns(3)
    with shock_cols[0]:
        income_pct = st.slider(
            "Money-in level (usual = 100%)",
            min_value=0,
            max_value=150,
            value=int(preset.income_multiplier * 100),
            step=5,
            format="%d%%",
            key=income_key,
            help="For example, 55% models 45% less recorded money-in; 100% leaves it unchanged.",
        )
    with shock_cols[1]:
        bill_pct = st.slider(
            "Household-bill increase",
            min_value=0,
            max_value=100,
            value=int(preset.household_bills_pct * 100),
            step=5,
            format="%d%%",
            key=bills_key,
            help="For example, 15% means recorded household bills are 15% higher. Bills cannot be reduced in this shock control.",
        )
    with shock_cols[2]:
        one_off_cost = st.number_input(
            "One-time cost ($ CAD)",
            min_value=0.0,
            max_value=1_000_000.0,
            value=default_cost,
            step=100.0,
            key=cost_key,
            help="A one-time cost taken from the starting balance. The repair example starts at one typical month of spending.",
        )

    scenario = ShockScenario(
        scenario_id=f"PLAN_{preset.scenario_id}",
        name=scenario_display_name(preset),
        description="A customer-selected what-if built from the supplied account records.",
        income_multiplier=income_pct / 100.0,
        household_bills_pct=bill_pct / 100.0,
        one_off_fixed_amount=float(one_off_cost),
        duration_months=preset.duration_months,
        is_judge_preset=True,
    )
    shock = simulate_shock(baseline, scenario)

    st.markdown("#### What changes in this scenario")
    shock_metrics = st.columns(4)
    shock_metrics[0].metric("Money in / month", _money(shock.income_after_shock), delta=f"Usual: {_money(baseline.I)}")
    shock_metrics[1].metric("Spending / month", _money(shock.spending_after_shock), delta=f"Usual: {_money(baseline.S)}", delta_color="inverse")
    shock_metrics[2].metric("Balance after one-time cost", _money(shock.buffer_left), delta=f"Starting: {_money(baseline.B)}", delta_color="inverse")
    shock_metrics[3].metric("Monthly shortfall", _money(max(0.0, shock.monthly_gap)), help="Spending minus money-in when spending is higher. If money-in covers spending, there is no shortfall.")

    st.markdown("#### Make a backup plan for this shock")
    backup_controls = st.columns(2)
    with backup_controls[0]:
        coverage_months = st.select_slider(
            "How many months should the buffer cover?",
            options=[1, 2, 3, 4, 6, 9, 12],
            value=min(6, max(1, preset.duration_months)),
            key=f"planner_shock_target_months_{account_id}",
        )
    plan_core = build_resilience_gap_plan(
        buffer=shock.buffer_left,
        monthly_gap=shock.monthly_gap,
        target_months=coverage_months,
    )
    with backup_controls[1]:
        monthly_reduction_key = f"planner_reduction_{account_id}_{preset.scenario_id}_{coverage_months}"
        max_monthly_reduction = max(0.0, float(shock.spending_after_shock))
        if st.session_state.get(monthly_reduction_key, 0.0) > max_monthly_reduction:
            st.session_state[monthly_reduction_key] = max_monthly_reduction
        monthly_reduction = st.number_input(
            "Monthly spending reduction to try ($)",
            min_value=0.0,
            max_value=max_monthly_reduction,
            value=min(max_monthly_reduction, plan_core.required_monthly_improvement),
            step=50.0,
            key=monthly_reduction_key,
            help="Starts at the amount the formula says would meet this duration using the current positive buffer. This is a test amount, not a recommendation or a claim that any category is reducible.",
        )
    plan = build_resilience_gap_plan(
        buffer=shock.buffer_left,
        monthly_gap=shock.monthly_gap,
        target_months=coverage_months,
        selected_monthly_adjustment=monthly_reduction,
    )

    plan_results = st.columns(4)
    plan_results[0].metric(
        "Additional buffer to add now",
        _money(plan.additional_buffer_needed),
        help="Additional money needed now for the selected monthly reduction to cover the chosen number of months.",
    )
    plan_results[1].metric(
        "Monthly reduction needed for this target",
        _money(plan.required_monthly_improvement),
        help="Calculated using the current buffer when positive. Any buffer shortfall after the one-time cost is shown separately.",
    )
    plan_results[2].metric(
        "Shortfall after your test amount",
        _money(max(0.0, plan.proposed_monthly_gap)),
    )
    plan_results[3].metric(
        "Months covered with current buffer",
        _runway_label(plan.available_buffer, plan.proposed_monthly_gap, plan.proposed_runway_months),
        help="Uses the buffer after the one-time cost. An upfront buffer shortfall cannot be fixed by a monthly reduction alone.",
    )

    if plan.additional_buffer_needed > 0:
        st.markdown(
            f"**Your plan in one sentence:** With a monthly spending reduction of "
            f"{_money(monthly_reduction)}, you would also need to add "
            f"{_money(plan.additional_buffer_needed)} to the buffer now to cover {coverage_months} months."
        )
        st.warning(
            f"With the monthly reduction you entered, the plan still needs "
            f"{_money(plan.additional_buffer_needed)} in the buffer to cover {coverage_months} months. "
            "A monthly change cannot pay a one-time cost that has already used up the starting buffer."
        )
    elif plan.proposed_runway_months >= coverage_months:
        st.markdown(
            f"**Your plan in one sentence:** Your selected {_money(monthly_reduction)} monthly spending "
            f"reduction lets the current buffer cover the {coverage_months}-month goal; no additional "
            "upfront buffer is needed in this scenario."
        )
        st.success(
            f"On these assumptions, the current buffer and the monthly reduction you entered "
            f"cover the {coverage_months}-month goal. This is a calculation, not a recommendation or forecast."
        )
    else:
        st.markdown(
            f"**Your plan in one sentence:** The selected monthly spending reduction leaves "
            f"{_money(max(0.0, plan.proposed_monthly_gap))} short each month. "
            f"Add {_money(plan.additional_buffer_needed)} to the buffer to cover {coverage_months} months."
        )
        st.info(
            f"On these assumptions, the tested monthly reduction does not yet cover {coverage_months} months. "
            f"The formula's monthly amount is {_money(plan.required_monthly_improvement)}."
        )

    st.markdown("#### Buffer over the selected period")
    timeline = list(range(coverage_months + 1))
    current_path = [shock.buffer_left]
    tested_path = [shock.buffer_left]
    for _ in range(coverage_months):
        current_path.append(round(current_path[-1] - shock.monthly_gap, 2))
        tested_path.append(round(tested_path[-1] - plan.proposed_monthly_gap, 2))

    chart = base_options(zoom=False)
    chart.update(
        {
            "grid": {"left": 26, "right": 24, "top": 48, "bottom": 36, "containLabel": True},
            "tooltip": {**chart["tooltip"], "trigger": "axis"},
            "legend": {"show": True, "top": 4, "textStyle": {"color": THEME["text_muted"]}},
            "xAxis": {
                "type": "category",
                "name": "Months after the shock",
                "nameLocation": "middle",
                "nameGap": 28,
                "data": timeline,
                **axis_style(),
            },
            "yAxis": {
                "type": "value",
                "name": "Buffer ($ CAD)",
                "nameLocation": "middle",
                "nameGap": 70,
                "axisLabel": {"color": THEME["text_muted"], "formatter": "${value}"},
                "splitLine": {"lineStyle": {"color": "rgba(141,153,174,.16)"}},
            },
            "series": [
                {
                    "name": "As-is, with no monthly reduction",
                    "type": "line",
                    "data": current_path,
                    "smooth": 0.15,
                    "showSymbol": True,
                    "symbolSize": 7,
                    "lineStyle": {"width": 3, "color": THEME["primary_orange"]},
                    "itemStyle": {"color": THEME["primary_orange"]},
                    "markLine": {
                        "symbol": "none",
                        "silent": True,
                        "lineStyle": {"color": THEME["alert_red"], "type": "dashed", "width": 1.5},
                        "label": {"formatter": "$0 buffer", "color": THEME["alert_red"]},
                        "data": [{"yAxis": 0}],
                    },
                },
                {
                    "name": "With your tested monthly reduction",
                    "type": "line",
                    "data": tested_path,
                    "smooth": 0.15,
                    "showSymbol": True,
                    "symbolSize": 7,
                    "lineStyle": {"width": 3, "type": "dashed", "color": THEME["accent_blue"]},
                    "itemStyle": {"color": THEME["accent_blue"]},
                },
            ],
        }
    )
    chart["tooltip"]["trigger"] = "axis"
    render_chart(chart, key="recovery-plan-trajectory", height=390)
    st.caption(
        "The chart repeats the same monthly shortfall or surplus for each month so you can compare the arithmetic. "
        "It does not predict future transactions. A negative starting buffer means more money is needed upfront."
    )

    with st.expander("How the backup-plan numbers are worked out"):
        st.markdown(
            f"- **After-shock balance** = {_money(baseline.B)} starting buffer − {_money(one_off_cost)} one-time cost = {_money(shock.buffer_left)}.\n"
            f"- **Monthly shortfall** = {_money(shock.spending_after_shock)} scenario spending − {_money(shock.income_after_shock)} scenario money-in = {_money(shock.monthly_gap)}.\n"
            f"- **Monthly reduction needed** = max(0, monthly shortfall − positive buffer ÷ {coverage_months}) = {_money(plan.required_monthly_improvement)}.\n"
            f"- **Extra buffer needed for your test amount** = max(0, {coverage_months} × positive shortfall after test − after-shock balance) = {_money(plan.additional_buffer_needed)}."
        )
        st.caption(
            "This follows the challenge runway definition: one-time costs reduce the buffer; higher household bills add to spending; "
            "a lower money-in assumption changes recorded income. Fixed costs are shown for context and are not added again."
        )

    backup = build_backup_plan(baseline, shock, account_meta)
    st.markdown("---")
    st.markdown("### 3 · Account-specific follow-up ideas")
    st.caption(
        "These are questions suggested by records linked to this account. The app assumes no savings, approval, "
        "payment change or customer eligibility."
    )
    if backup.actions:
        for action in backup.actions:
            st.markdown(f"**{action.title}**  \n{action.description}")
    else:
        st.info(
            "The supplied account records do not point to a specific loan or leasing-payment follow-up. "
            "A customer can still review which costs or income changes are realistic for them."
        )
    _linked_records(repo, account_id, account_meta, baseline)

    st.caption(
        "Planning figures use the supplied account history and linked records. They are scenarios for a conversation, "
        "not personal financial advice, a promise of future results, or an automated credit decision."
    )
