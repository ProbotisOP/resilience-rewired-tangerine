"""
Screen 7: AI Financial Resilience Advisor & Executive Q&A
Translates verified evidence JSON into high-level business briefings.
"""

import streamlit as st

from src.data.local_repository import LocalDataRepository
from src.services.customer_profile import get_customer_profile
from src.services.baseline_metrics import compute_official_baseline
from src.services.shock_engine import simulate_shock
from src.services.recovery_planner import build_goal_plan, build_backup_plan
from src.services.ai_narrative import get_ai_narrative
from config.scenarios import OFFICIAL_PRESETS
from config.settings import THEME

def render_ai_advisor(repo: LocalDataRepository):
    st.markdown("## 💬 AI Financial Resilience Advisor (Executive Briefing)")
    st.caption("AI-powered strategic translation for bank executives, credit risk analysts, and customer wellness advisors.")

    account_id = st.session_state.get("active_account_id", 20111)
    profile = get_customer_profile(account_id, repo)
    if not profile:
        st.error("Please select a valid Account ID first.")
        return

    monthly_df = repo.get_monthly_summary(account_id)
    acc_meta = repo.get_account_meta(account_id)
    baseline = compute_official_baseline(account_id, monthly_df, acc_meta)

    preset_idx = st.session_state.get("active_preset_idx", 1)
    scenario = OFFICIAL_PRESETS[preset_idx]
    shock_res = simulate_shock(baseline, scenario)
    goal = build_goal_plan(baseline, target_months=3)
    backup = build_backup_plan(baseline, shock_res, acc_meta)

    narrative = get_ai_narrative(profile, baseline, shock_res, goal, backup)

    # 1. Executive Briefing Box
    st.markdown(f"### 📋 Strategic Executive Briefing: Account #{account_id}")
    st.markdown(f"""
    <div style="background-color: {THEME['card_bg']}; padding: 20px; border-radius: 8px; border-left: 5px solid {THEME['primary_orange']};">
        <h4 style="color: {THEME['text_main']}; margin-top: 0;">{narrative['headline']}</h4>
        <p style="font-size: 14px; color: {THEME['text_main']}; line-height: 1.6;">{narrative['executive_summary']}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 2. Key Business Drivers & Action Items
    col_d, col_a = st.columns(2)
    with col_d:
        st.markdown("#### 🔍 Primary Financial Drivers")
        for d in narrative["key_drivers"]:
            st.markdown(f"- {d}")

    with col_a:
        st.markdown("#### ⚡ Recommended Strategic Actions")
        for a in narrative["recommended_actions"]:
            st.markdown(f"- {a}")

    st.markdown("---")

    # 3. Quick Strategic Q&A for Hackathon Judges
    st.markdown("#### 💡 Common Strategic Questions (Click to Explore)")
    
    q_col1, q_col2 = st.columns(2)
    with q_col1:
        with st.expander("❓ Why does an EI shock crush high earners faster than low earners?"):
            st.write(
                "Because of **Spend-Scale Burn (Lifestyle Inflation)**. High earners ($25k/mo) have high baseline spending ($23k/mo). "
                "A 45% income drop creates a monthly dollar deficit of ~$9,000/mo, burning their $34k buffer in under 4 months. "
                "Low earners ($1.5k/mo) have a dollar gap of only $450/mo, which their modest buffer sustains for over 3 years."
            )

        with st.expander("❓ How can a bank utilize 'The Spousal Shield' commercially?"):
            st.write(
                "Across 869 joint accounts in 6 years, **zero accounts defaulted (0.00%)** compared to 14.15% in solo accounts. "
                "Banks can offer interest rate discounts (e.g. 50 bps) or elevated credit limits when a customer adds a verified "
                "household co-partner as an authorized user, fostering dual financial accountability."
            )

    with q_col2:
        with st.expander("❓ Why replace overdraft penalty fees with a 'Resilience Freeze'?"):
            st.write(
                "The data reveals that **90.0% of loan holders charged penalty interest subsequently defaulted** (72 out of 80). "
                "Overdraft penalty interest generates negligible revenue (<0.1% of bank outflows) but accelerates the customer's "
                "cash-flow death spiral. Pausing fees in exchange for automated recovery plan enrollment protects loan capital."
            )

        with st.expander("❓ What makes this engine superior to a traditional credit score?"):
            st.write(
                "Traditional credit scores are backward-looking bureau snapshots that miss real-time retail transaction dynamics. "
                "This engine captures daily overdraft frequency, statement hyper-vigilance, and discretionary cash velocity, "
                "detecting financial fragility months before an official credit bureau delinquency occurs."
            )
