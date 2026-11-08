"""Screen 4: Transparent reserve goals and customer-controlled gap simulations."""

import streamlit as st
import plotly.graph_objects as go

from src.data.local_repository import LocalDataRepository
from src.services.baseline_metrics import compute_official_baseline
from src.services.customer_profile import get_customer_profile
from src.services.recovery_planner import (
    build_backup_plan,
    build_goal_plan,
    build_resilience_gap_plan,
    recent_six_month_median_net_cash_flow,
)
from src.services.shock_engine import simulate_shock
from config.scenarios import OFFICIAL_PRESETS
from src.ui.presentation import scenario_display_name


def _runway_calculation(label: str, buffer: float, gap: float, result: float) -> str:
    if buffer <= 0:
        return f"{label} = 0.0 months because the available buffer is zero or below."
    if gap <= 0:
        return f"{label} = 120+ months because the monthly gap is zero or below."
    return (
        f"{label} = min(120, ${buffer:,.2f} ÷ ${gap:,.2f}) "
        f"= {result:.1f} months."
    )


def _runway_display(buffer: float, gap: float, result: float) -> str:
    if buffer <= 0:
        return "0.0 months"
    if gap <= 0:
        return "120+ months"
    return f"{result:.1f} months"


def render_recovery_planner(repo: LocalDataRepository):
    st.markdown("## 🧭 Build a resilience plan")
    st.caption(
        "Try a target buffer and monthly adjustment. You stay in control of the assumptions; "
        "the app will show the arithmetic, not tell you what to cut."
    )

    account_id = st.session_state.get("active_account_id")
    if account_id not in repo.get_all_accounts():
        st.error("Select an account from the supplied account directory before planning.")
        return

    profile = get_customer_profile(account_id, repo)
    if not profile:
        st.error(f"Account #{account_id} has no usable profile in the loaded data.")
        return

    monthly_df = repo.get_monthly_summary(account_id)
    account_meta = repo.get_account_meta(account_id)
    baseline = compute_official_baseline(account_id, monthly_df, account_meta)

    st.markdown("### 1. Pick a buffer goal")
    st.caption(
        "Start with the observed fixed-cost figure or enter a different monthly essential-cost "
        "assumption. If the observed figure is zero, enter your own estimate—nothing is guessed."
    )
    goal_col1, goal_col2, goal_col3 = st.columns(3)
    with goal_col1:
        target_months = st.slider(
            "How many months to cover?", min_value=1, max_value=12, value=3
        )
    with goal_col2:
        essential_default = max(0.0, baseline.F)
        essential_input = st.number_input(
            "Monthly essential-cost estimate ($ CAD)",
            min_value=0.0,
            max_value=100000.0,
            value=float(essential_default),
            step=100.0,
            help="Zero means no target is calculated. Confirm or edit this assumption.",
        )
    recent_net = recent_six_month_median_net_cash_flow(
        baseline.last_6_months_summary
    )
    with goal_col3:
        st.metric(
            "Recent monthly net cash flow (median)",
            f"${recent_net:,.2f}" if recent_net is not None else "Unavailable",
        )

    contribution_default = max(0.0, recent_net or 0.0)
    contribution = st.number_input(
        "Monthly contribution to test ($ CAD)",
        min_value=0.0,
        max_value=100000.0,
        value=min(contribution_default, 100000.0),
        step=50.0,
        help="Recent net cash flow is a reference statistic, not a promise or recommendation.",
    )
    goal = build_goal_plan(
        baseline,
        target_months=target_months,
        custom_monthly_savings=contribution,
        essential_monthly_cost=(
            float(essential_input) if essential_input > 0 else None
        ),
    )

    if goal.emergency_target is None:
        st.warning(goal.plan_explanation)
    else:
        goal_metrics = st.columns(4)
        goal_metrics[0].metric(
            "Essential-cost assumption", f"${goal.essential_monthly_cost:,.2f}/mo"
        )
        goal_metrics[1].metric("Reserve target", f"${goal.emergency_target:,.2f}")
        goal_metrics[2].metric("Funding gap", f"${goal.funding_gap:,.2f}")
        goal_metrics[3].metric(
            "Estimated months",
            str(goal.months_to_goal) if goal.months_to_goal is not None else "Not estimated",
        )
        st.info(goal.plan_explanation)
    if goal.recent_six_month_median_net_cash_flow is not None:
        st.caption(
            f"Reference: median of money in minus money out across the latest "
            f"{len(baseline.last_6_months_summary)} available monthly rows. This is historical "
            "cash flow—not a forecast or a recommended contribution."
        )
    with st.expander("🧾 Show the buffer-goal calculation"):
        if goal.emergency_target is None:
            st.write("No goal is calculated until a positive monthly essential-cost estimate is entered.")
        else:
            if goal.is_target_met:
                months_calculation = "Time to goal = 0 months; the current buffer already meets the target."
            elif (
                goal.months_to_goal is not None
                and goal.recommended_monthly_deposit > 0
                and goal.funding_gap is not None
            ):
                months_calculation = (
                    f"Time to goal = ceil(amount to goal ÷ contribution) "
                    f"= ceil(${goal.funding_gap:,.2f} ÷ "
                    f"${goal.recommended_monthly_deposit:,.2f}) "
                    f"= {goal.months_to_goal} months"
                )
            else:
                months_calculation = (
                    "Time to goal is not estimated without a positive contribution."
                )
            st.code(
                "\n".join(
                    [
                        f"Target = {goal.target_months} months × ${goal.essential_monthly_cost:,.2f}/month = ${goal.emergency_target:,.2f}",
                        f"Current buffer = ${goal.current_buffer:,.2f}",
                        f"Amount to goal = max(0, target - buffer) = max(0, ${goal.emergency_target:,.2f} - ${goal.current_buffer:,.2f}) = ${goal.funding_gap:,.2f}",
                        months_calculation,
                    ]
                ),
                language="text",
            )

    st.markdown("---")
    st.markdown("### 2. See what it would take to reach your target")
    preset_idx = st.session_state.get("active_preset_idx", 1)
    if not isinstance(preset_idx, int) or not 0 <= preset_idx < len(OFFICIAL_PRESETS):
        preset_idx = 1
    scenario = OFFICIAL_PRESETS[preset_idx]
    shock = simulate_shock(baseline, scenario)
    st.write(
        f"**What-if in use:** {scenario_display_name(scenario)} · "
        f"{scenario.duration_months} months"
    )
    st.caption("To change the what-if, open “Try a what-if” in the menu.")
    st.caption(
        "Required improvement is the minimum monthly reduction in total spending needed for "
        "the selected buffer to cover the selected target period. It does not identify a "
        "discretionary category."
    )
    optimizer_col1, optimizer_col2 = st.columns(2)
    with optimizer_col1:
        survival_months = st.slider(
            "How long should the buffer last?",
            min_value=1,
            max_value=24,
            value=min(24, max(1, scenario.duration_months)),
        )
    with optimizer_col2:
        selected_adjustment = st.number_input(
            "Monthly adjustment to test ($ CAD)",
            min_value=0.0,
            max_value=max(100000.0, float(shock.spending_after_shock)),
            value=0.0,
            step=50.0,
            help="This is a user-selected what-if, not an automatic recommendation.",
        )

    plan = build_resilience_gap_plan(
        buffer=shock.buffer_left,
        monthly_gap=shock.monthly_gap,
        target_months=survival_months,
        selected_monthly_adjustment=selected_adjustment,
    )
    result_cols = st.columns(4)
    result_cols[0].metric("Current monthly shock gap", f"${plan.current_monthly_gap:,.2f}")
    result_cols[1].metric("Available buffer after one-off", f"${plan.available_buffer:,.2f}")
    result_cols[2].metric(
        "Required monthly improvement",
        f"${plan.required_monthly_improvement:,.2f}",
    )
    result_cols[3].metric(
        "Target survival duration", f"{plan.target_months} months"
    )

    comparison_cols = st.columns(3)
    comparison_cols[0].metric(
        "Current plan · estimated runway",
        _runway_display(
            plan.available_buffer,
            plan.current_monthly_gap,
            plan.current_runway_months,
        ),
    )
    comparison_cols[1].metric(
        "Proposed plan · monthly gap",
        f"${plan.proposed_monthly_gap:,.2f}",
        delta=f"Selected adjustment: ${plan.selected_monthly_adjustment:,.2f}/mo",
    )
    comparison_cols[2].metric(
        "Proposed plan · estimated runway",
        _runway_display(
            plan.available_buffer,
            plan.proposed_monthly_gap,
            plan.proposed_runway_months,
        ),
    )
    trajectory_months = list(range(survival_months + 1))
    current_buffer = [plan.available_buffer]
    proposed_buffer = [plan.available_buffer]
    for _ in range(survival_months):
        current_buffer.append(round(current_buffer[-1] - plan.current_monthly_gap, 2))
        proposed_buffer.append(round(proposed_buffer[-1] - plan.proposed_monthly_gap, 2))
    trajectory_fig = go.Figure()
    trajectory_fig.add_trace(
        go.Scatter(
            x=trajectory_months,
            y=current_buffer,
            mode="lines+markers",
            name="Current what-if",
            line=dict(color="#FF5B00", width=3),
            hovertemplate="Month %{x}<br>Buffer: $%{y:,.2f}<extra></extra>",
        )
    )
    trajectory_fig.add_trace(
        go.Scatter(
            x=trajectory_months,
            y=proposed_buffer,
            mode="lines+markers",
            name="With your selected adjustment",
            line=dict(color="#4EA8DE", width=3, dash="dash"),
            hovertemplate="Month %{x}<br>Buffer: $%{y:,.2f}<extra></extra>",
        )
    )
    trajectory_fig.add_hline(y=0, line_color="#E63946", line_dash="dot")
    trajectory_fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Month in selected target period",
        yaxis_title="Illustrative buffer (CAD)",
        margin=dict(l=20, r=20, t=25, b=20),
        height=360,
    )
    st.plotly_chart(trajectory_fig, use_container_width=True)
    st.caption(
        "The lines recalculate as you change the target or adjustment. They extend the "
        "selected monthly gap at a constant rate; they are not forecasts."
    )
    achieved = plan.proposed_runway_months >= plan.target_months
    st.success("Nice—this what-if reaches the target on paper.") if achieved else st.warning(
        "This what-if does not reach the target yet. Try another amount or target."
    )
    st.caption(
        "The challenge runway and this optional adjustment simulation are separate. "
        "The proposed result is not a promise or personal recommendation."
    )
    with st.expander("🧾 Show the gap-optimizer calculation"):
        st.code(
            "\n".join(
                [
                    f"Monthly shock gap = ${plan.current_monthly_gap:,.2f}",
                    f"Available buffer = ${plan.available_buffer:,.2f}",
                    f"Target duration = {plan.target_months} months",
                    f"Required monthly improvement = max(0, gap - buffer ÷ target months)",
                    f"= max(0, ${plan.current_monthly_gap:,.2f} - ${plan.available_buffer:,.2f} ÷ {plan.target_months})",
                    f"= ${plan.required_monthly_improvement:,.2f}/month",
                    f"Proposed gap = current gap - your selected adjustment",
                    f"= ${plan.current_monthly_gap:,.2f} - ${plan.selected_monthly_adjustment:,.2f} = ${plan.proposed_monthly_gap:,.2f}/month",
                    _runway_calculation(
                        "Current runway",
                        plan.available_buffer,
                        plan.current_monthly_gap,
                        plan.current_runway_months,
                    ),
                    _runway_calculation(
                        "Proposed runway",
                        plan.available_buffer,
                        plan.proposed_monthly_gap,
                        plan.proposed_runway_months,
                    ),
                ]
            ),
            language="text",
        )
        st.caption(
            "Runway is capped at 120 months, rounded to one decimal, and shown as 120+ "
            "when the simulated monthly gap is non-positive and the buffer is positive."
        )

    st.markdown("---")
    st.markdown("### 3. Questions you could investigate")
    backup = build_backup_plan(baseline, shock, account_meta)
    st.write(
        f"Current monthly shortfall under this shock: **${backup.monthly_shortfall:,.2f}**. "
        "The options below have no assumed savings or guaranteed availability."
    )
    if not backup.actions:
        st.caption("No standing-order or running-loan review prompt applies to this account.")
    for action in backup.actions:
        st.markdown(f"**{action.title}** — {action.description}")
