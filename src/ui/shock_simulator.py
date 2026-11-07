"""
Screen 3: Shock Simulator & Interactive Live Twist Engine
Implements official competition shock cards, custom sliders, and adaptive runways.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from src.data.local_repository import LocalDataRepository
from src.services.customer_profile import get_customer_profile
from src.services.baseline_metrics import compute_official_baseline
from src.services.shock_engine import simulate_shock, calculate_judge_runway
from src.services.timeline_projection import project_shock_timeline
from config.scenarios import OFFICIAL_PRESETS, ShockScenario
from config.settings import THEME

def render_shock_simulator(repo: LocalDataRepository):
    st.markdown("## ⚡ Financial Shock Simulator (Live Twist Engine)")
    st.caption("Apply multidimensional economic shocks to test the customer's survival runway live.")

    account_id = st.session_state.get("active_account_id", 20111)
    profile = get_customer_profile(account_id, repo)
    if not profile:
        st.error("Please select a valid Account ID in the Customer Explorer first.")
        return

    monthly_df = repo.get_monthly_summary(account_id)
    acc_meta = repo.get_account_meta(account_id)
    baseline = compute_official_baseline(account_id, monthly_df, acc_meta)

    # 1. Preset Shock Selection
    st.markdown("#### 1. Select a Competition Shock Preset or Create a Custom Twist")
    preset_cols = st.columns(4)
    
    preset_idx = st.session_state.get("active_preset_idx", 1)  # Default: Twist 1 (EI 55%)

    for i, p in enumerate(OFFICIAL_PRESETS):
        with preset_cols[i]:
            btn_type = "primary" if preset_idx == i else "secondary"
            if st.button(p.name, key=f"preset_{p.scenario_id}", type=btn_type, use_container_width=True):
                st.session_state["active_preset_idx"] = i
                preset_idx = i

    chosen_preset = OFFICIAL_PRESETS[preset_idx]
    st.info(f"**Active Scenario:** {chosen_preset.description}")

    # 2. Interactive Shock Tuning Controls
    with st.expander("🛠️ Customize Shock Sizing & Stress Parameters", expanded=(preset_idx == 0)):
        sc_col1, sc_col2, sc_col3, sc_col4 = st.columns(4)
        with sc_col1:
            income_pct = st.slider(
                "Income Multiplier (%)",
                min_value=0,
                max_value=150,
                value=int(chosen_preset.income_multiplier * 100),
                step=5,
                help="EI pays 55% of usual money-in during layoff"
            ) / 100.0
        with sc_col2:
            bills_pct = st.slider(
                "Household Bills Change (%)",
                min_value=-30,
                max_value=100,
                value=int(chosen_preset.household_bills_pct * 100),
                step=5,
                help="Rent or utility increase (e.g. +15%)"
            ) / 100.0
        with sc_col3:
            one_off_spend_mult = st.slider(
                "Repair Cost (× Monthly Spending S)",
                min_value=0.0,
                max_value=3.0,
                value=float(chosen_preset.one_off_spend_multiplier),
                step=0.25,
                help="e.g. furnace dies = 1.0 * S"
            )
        with sc_col4:
            custom_fixed_cost = st.number_input(
                "Additional One-Off Cost ($ CAD)",
                min_value=0,
                max_value=50000,
                value=int(chosen_preset.one_off_fixed_amount),
                step=500
            )

    # Build active scenario object
    active_scenario = ShockScenario(
        scenario_id=f"CUSTOM_{chosen_preset.scenario_id}",
        name=chosen_preset.name,
        description=chosen_preset.description,
        income_multiplier=income_pct,
        household_bills_pct=bills_pct,
        one_off_spend_multiplier=one_off_spend_mult,
        one_off_fixed_amount=float(custom_fixed_cost),
        duration_months=chosen_preset.duration_months
    )

    # Execute simulation
    shock_res = simulate_shock(baseline, active_scenario)

    st.markdown("---")

    # 3. Before vs After Shock Results
    st.subheader("📊 Post-Shock Runway & Cash-Flow Impact")

    res1, res2, res3, res4 = st.columns(4)
    with res1:
        st.metric(
            "Monthly Money In",
            f"${shock_res.income_after_shock:,.2f}",
            delta=f"${shock_res.income_after_shock - baseline.I:,.2f}",
            delta_color="normal"
        )
    with res2:
        st.metric(
            "Monthly Spending",
            f"${shock_res.spending_after_shock:,.2f}",
            delta=f"${shock_res.spending_after_shock - baseline.S:,.2f}",
            delta_color="inverse"
        )
    with res3:
        st.metric(
            "Monthly Shortfall (Gap)",
            f"${shock_res.monthly_gap:,.2f}",
            delta="Surplus" if shock_res.monthly_gap <= 0 else "Burn",
            delta_color="inverse" if shock_res.monthly_gap > 0 else "normal"
        )
    with res4:
        st.metric(
            "Buffer After One-Off Cost",
            f"${shock_res.buffer_left:,.2f}",
            delta=f"-${shock_res.one_off_costs:,.2f}" if shock_res.one_off_costs > 0 else "0",
            delta_color="inverse" if shock_res.one_off_costs > 0 else "off"
        )

    # 4. Runway Comparison Showcase (Official Judge Match vs Adaptive Runway)
    st.markdown("#### 🎯 Runway Evaluation")
    rw_col1, rw_col2 = st.columns(2)

    with rw_col1:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 20px; border-radius: 8px; border-left: 6px solid {THEME['primary_orange']};">
            <span style="font-size: 12px; color: {THEME['text_muted']}; text-transform: uppercase;">Official Tangerine Judge Match</span>
            <h2 style="color: {THEME['text_main']}; margin: 5px 0;">{shock_res.runway_label}</h2>
            <p style="font-size: 13px; color: {THEME['text_muted']}; margin-bottom: 0;">
                Calculated strictly via challenge formula: <code>min((B - one_off) / gap, 120)</code>. 
                Assumes spending stays frozen at baseline levels.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with rw_col2:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 20px; border-radius: 8px; border-left: 6px solid {THEME['accent_blue']};">
            <span style="font-size: 12px; color: {THEME['text_muted']}; text-transform: uppercase;">Adaptive Survival Runway (30% Cash Cut)</span>
            <h2 style="color: {THEME['accent_blue']}; margin: 5px 0;">{shock_res.adaptive_runway_label}</h2>
            <p style="font-size: 13px; color: {THEME['text_muted']}; margin-bottom: 0;">
                Compresses discretionary cash withdrawals while maintaining fixed rent and debt service. 
                <b>Extends survival by +{shock_res.months_gained_by_adaptation:.1f} months</b>.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # 5. Month-by-Month Trajectory Projection
    st.subheader("📉 Month-by-Month Cash Burn Trajectory (6-Month Shock Window)")
    projection_baseline = project_shock_timeline(baseline, shock_res, duration_months=6, adaptive_mode=False)
    projection_adaptive = project_shock_timeline(baseline, shock_res, duration_months=6, adaptive_mode=True)

    months_labels = [p.month_name for p in projection_baseline.trajectory]
    balances_base = [p.ending_buffer for p in projection_baseline.trajectory]
    balances_adapt = [p.ending_buffer for p in projection_adaptive.trajectory]

    fig_proj = go.Figure()
    fig_proj.add_trace(go.Scatter(
        x=["Start"] + months_labels,
        y=[shock_res.buffer_left] + balances_base,
        mode="lines+markers",
        name="Static Spending (Uncompressed)",
        line=dict(color=THEME["alert_red"], width=3)
    ))
    fig_proj.add_trace(go.Scatter(
        x=["Start"] + months_labels,
        y=[shock_res.buffer_left] + balances_adapt,
        mode="lines+markers",
        name="Adaptive Spending (30% Discretionary Compression)",
        line=dict(color=THEME["accent_blue"], width=3, dash="dash")
    ))
    fig_proj.add_hline(y=0, line_color="white", line_dash="dot", annotation_text="Buffer Exhaustion ($0)")

    fig_proj.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis_title="Timeline Progression",
        yaxis_title="Remaining Buffer ($ CAD)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig_proj, use_container_width=True)

    # Survival verdict alert
    if projection_baseline.survives_full_shock_period:
        st.success(f"✅ **Survival Verdict:** Customer successfully withstands the full 6-month shock period with ${projection_baseline.ending_buffer_at_shock_end:,.2f} CAD in reserve.")
    else:
        st.warning(f"⚠️ **Survival Alert:** Under static spending, the buffer exhausts in **Month +{projection_baseline.months_until_depleted}**. However, under Adaptive Mode, survival is extended.")
