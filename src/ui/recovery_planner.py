"""
Screen 4: Recovery & Backup Planning Engine
Builds personalized emergency fund targets and hierarchical post-shock mitigation plans.
"""

import streamlit as st
import plotly.graph_objects as go

from src.data.local_repository import LocalDataRepository
from src.services.customer_profile import get_customer_profile
from src.services.baseline_metrics import compute_official_baseline
from src.services.shock_engine import simulate_shock
from src.services.recovery_planner import build_goal_plan, build_backup_plan
from config.scenarios import OFFICIAL_PRESETS
from config.settings import THEME

def render_recovery_planner(repo: LocalDataRepository):
    st.markdown("## 🎯 Personalized Recovery & Backup Planner")
    st.caption("Empower customers with a customized emergency fund roadmap and an actionable shock survival blueprint.")

    account_id = st.session_state.get("active_account_id", 20111)
    profile = get_customer_profile(account_id, repo)
    if not profile:
        st.error("Please select a valid Account ID first.")
        return

    monthly_df = repo.get_monthly_summary(account_id)
    acc_meta = repo.get_account_meta(account_id)
    baseline = compute_official_baseline(account_id, monthly_df, acc_meta)

    # 1. PART 1: EMERGENCY FUND GOAL PLANNER
    st.markdown("### Part 1: Proactive Emergency Fund Goal Plan")
    st.markdown(
        "Build a dedicated resilience cushion based on verified essential monthly obligations ($F$). "
        "Unlike generic rules of thumb, this goal adapts to the customer's real contractual commitments."
    )

    g_col1, g_col2 = st.columns([1, 2])
    with g_col1:
        target_mos = st.slider("Target Buffer Window (Months of Essentials)", min_value=1, max_value=12, value=3, step=1)
        custom_save = st.number_input(
            "Monthly Savings Contribution ($ CAD):",
            min_value=0,
            max_value=10000,
            value=int(max(0.0, baseline.I - baseline.S)),
            step=100,
            help="Default is customer's visible median monthly surplus (I - S)"
        )

    goal = build_goal_plan(baseline, target_months=target_mos, custom_monthly_savings=float(custom_save))

    with g_col2:
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            st.metric("Essential Costs (F)", f"${goal.essential_monthly_cost:,.2f}/mo")
        with k2:
            st.metric("Reserve Target", f"${goal.emergency_target:,.2f}")
        with k3:
            st.metric("Funding Gap", f"${goal.funding_gap:,.2f}", delta="Funded" if goal.is_target_met else "Shortfall", delta_color="normal" if goal.is_target_met else "inverse")
        with k4:
            st.metric("Timeline to Goal", f"{goal.months_to_goal} Months" if goal.months_to_goal is not None else "Action Required")

        st.info(f"📋 **Goal Roadmap:** {goal.plan_explanation}")

    st.markdown("---")

    # 2. PART 2: POST-SHOCK BACKUP PLAN
    st.markdown("### Part 2: Emergency Post-Shock Backup Plan")
    st.markdown(
        "If a financial shock hits, what concrete levers can this specific customer pull to eliminate their monthly shortfall?"
    )

    # Active shock scenario context
    preset_idx = st.session_state.get("active_preset_idx", 1)
    scenario = OFFICIAL_PRESETS[preset_idx]
    shock_res = simulate_shock(baseline, scenario)
    backup = build_backup_plan(baseline, shock_res, acc_meta)

    st.markdown(f"**Under {scenario.name}:** Monthly Shortfall = **${backup.monthly_shortfall:,.2f} CAD/month**.")

    if backup.monthly_shortfall <= 0:
        st.success("✅ **No Action Required:** Customer maintains positive net cash flow even under this shock. Surplus is being added to reserves.")
        return

    # Action Waterfall Table & Explanations
    st.markdown("#### Prioritized Mitigation Levers:")
    for a in backup.actions:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 14px 18px; border-radius: 6px; margin-bottom: 10px; border-left: 4px solid {THEME['primary_orange']};">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span style="font-weight: bold; color: {THEME['text_main']};">Priority {a.priority}: {a.title}</span>
                <span style="color: {THEME['success_green']}; font-weight: bold; font-size: 16px;">+${a.monthly_dollar_impact:,.2f}/mo</span>
            </div>
            <p style="font-size: 13px; color: {THEME['text_muted']}; margin: 4px 0 0 0;">{a.description}</p>
        </div>
        """, unsafe_allow_html=True)

    # Post-Mitigation Outcome
    st.markdown("#### 🏁 Post-Mitigation Financial Position")
    b_res1, b_res2, b_res3 = st.columns(3)
    with b_res1:
        st.metric("Total Mitigation Capacity", f"${backup.total_mitigation_capacity:,.2f}/mo")
    with b_res2:
        st.metric("Remaining Monthly Gap", f"${backup.post_mitigation_gap:,.2f}/mo", delta="Covered" if backup.deficit_fully_covered else "Remaining Deficit", delta_color="normal" if backup.deficit_fully_covered else "inverse")
    with b_res3:
        st.metric("Post-Mitigation Runway", f"{backup.post_mitigation_runway:.1f} Months" if backup.post_mitigation_runway < 120 else "120+ (No Shortfall)")
