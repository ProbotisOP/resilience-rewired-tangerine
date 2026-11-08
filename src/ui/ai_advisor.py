"""Screen 6: Answers grounded in verified deterministic account metrics."""

import streamlit as st

from src.data.local_repository import LocalDataRepository
from src.services.baseline_metrics import compute_official_baseline
from src.services.customer_profile import get_customer_profile
from src.services.shock_engine import simulate_shock
from src.services.recovery_planner import build_goal_plan, build_backup_plan
from src.services.ai_narrative import get_ai_narrative, answer_verified_question
from config.scenarios import OFFICIAL_PRESETS
from src.ui.presentation import scenario_display_name


def render_ai_advisor(repo: LocalDataRepository):
    st.markdown("## 💬 Ask the data")
    st.caption(
        "Get a plain-language explanation of this account's available numbers. The calculations "
        "stay in Python; optional Gemini can only rephrase the verified results."
    )

    account_id = st.session_state.get("active_account_id")
    if account_id not in repo.get_all_accounts():
        st.error("Select an account from the supplied directory before opening the advisor.")
        return
    profile = get_customer_profile(account_id, repo)
    if not profile:
        st.error(f"Account #{account_id} has no usable profile in the loaded data.")
        return

    baseline = compute_official_baseline(
        account_id,
        repo.get_monthly_summary(account_id),
        repo.get_account_meta(account_id),
    )
    preset_idx = st.session_state.get("active_preset_idx", 1)
    if not isinstance(preset_idx, int) or not 0 <= preset_idx < len(OFFICIAL_PRESETS):
        preset_idx = 1
    scenario = OFFICIAL_PRESETS[preset_idx]
    shock = simulate_shock(baseline, scenario)
    goal = build_goal_plan(baseline, target_months=3)
    backup = build_backup_plan(baseline, shock, repo.get_account_meta(account_id))
    narrative = get_ai_narrative(profile, baseline, shock, goal, backup)

    st.markdown(f"### Account #{account_id} · {scenario_display_name(scenario)}")
    st.info(narrative["headline"])
    st.write(narrative["executive_summary"])
    if narrative.get("ai_explanation"):
        st.markdown("**Optional Gemini explanation**")
        st.write(narrative["ai_explanation"])
    st.caption(narrative["ai_status"])

    st.markdown("#### The numbers behind this explanation")
    metric_cols = st.columns(4)
    metric_cols[0].metric("Typical money in", f"${baseline.I:,.2f}/mo")
    metric_cols[1].metric("Typical spending", f"${baseline.S:,.2f}/mo")
    metric_cols[2].metric("Scenario monthly gap", f"${shock.monthly_gap:,.2f}/mo")
    metric_cols[3].metric("Buffer after one-off cost", f"${shock.buffer_left:,.2f}")
    with st.expander("🧾 Show the calculations and limits"):
        st.code(
            "\n".join(
                [
                    f"Money in = median of {baseline.history_months} monthly money_in rows = ${baseline.I:,.2f}",
                    f"Spending = median of {baseline.history_months} monthly money_out rows = ${baseline.S:,.2f}",
                    f"Scenario money in = ${shock.income_after_shock:,.2f}",
                    f"Scenario spending = ${shock.spending_after_shock:,.2f}",
                    f"Monthly gap = spending - money in = ${shock.spending_after_shock:,.2f} - ${shock.income_after_shock:,.2f} = ${shock.monthly_gap:,.2f}",
                    f"Buffer after one-off cost = ${baseline.B:,.2f} - ${shock.one_off_costs:,.2f} = ${shock.buffer_left:,.2f}",
                    f"Challenge runway = {shock.runway_label}",
                ]
            ),
            language="text",
        )
        st.markdown("**Limits**")
        for limitation in narrative["limitations"]:
            st.markdown(f"- {limitation}")

    st.markdown("---")
    st.markdown("### What would you like to know?")
    question = st.text_input(
        "Ask a question",
        placeholder="For example: How much is the monthly gap in this scenario?",
    )
    if question:
        st.write(answer_verified_question(question, baseline, shock))
