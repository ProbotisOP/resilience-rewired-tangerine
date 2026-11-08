"""
Screen 3: Shock Simulator & Interactive Live Twist Engine
Implements official competition shock cards, custom sliders, and adaptive runways.
"""

import math
import streamlit as st
from src.ui.charting import axis_style, base_options, render_chart

from src.data.local_repository import LocalDataRepository
from src.services.customer_profile import get_customer_profile
from src.services.baseline_metrics import compute_official_baseline
from src.services.shock_engine import simulate_shock
from src.services.timeline_projection import project_shock_timeline
from config.scenarios import OFFICIAL_PRESETS, ShockScenario
from config.settings import THEME
from src.ui.presentation import scenario_display_description, scenario_display_name


def _timeline_duration(shock, no_shortfall_duration: int) -> int:
    finite_runways = [
        min(shock.buffer_left / gap, 120.0)
        for gap in (shock.monthly_gap, shock.adaptive_gap)
        if shock.buffer_left > 0 and gap > 0
    ]
    if finite_runways:
        return max(1, math.ceil(max(finite_runways)))
    return 1 if shock.buffer_left <= 0 else no_shortfall_duration


def _timeline_figure(
    baseline,
    shock,
    projection_baseline,
    projection_adjusted,
    frame: int,
):
    def series(projection, gap, runway, label):
        x_values = ["Before event", "After one-off"]
        y_values = [baseline.B, shock.buffer_left]
        raw_runway = shock.buffer_left / gap if shock.buffer_left > 0 and gap > 0 else None
        depletion_step = math.ceil(raw_runway) if raw_runway is not None else None

        if raw_runway is not None and raw_runway <= 120 and frame >= depletion_step:
            visible_points = projection.trajectory[: depletion_step - 1]
            x_values.extend(point.month_name for point in visible_points)
            y_values.extend(point.ending_buffer for point in visible_points)
            x_values.append(f"{label} runway · {runway:.1f} mo")
            y_values.append(0.0)
        else:
            visible_points = projection.trajectory[:frame]
            x_values.extend(point.month_name for point in visible_points)
            y_values.extend(point.ending_buffer for point in visible_points)
        return x_values, y_values, raw_runway, depletion_step

    month_names, baseline_values, challenge_raw_runway, challenge_depletion_step = series(
        projection_baseline,
        shock.monthly_gap,
        shock.runway_months,
        "Challenge",
    )
    adjusted_months, adjusted_values, _, _ = series(
        projection_adjusted,
        shock.adaptive_gap,
        shock.adaptive_runway_months,
        "Adjusted",
    )

    categories = list(dict.fromkeys(month_names + adjusted_months))
    baseline_by_month = dict(zip(month_names, baseline_values))
    adjusted_by_month = dict(zip(adjusted_months, adjusted_values))
    options = base_options(zoom=True)
    options.update(
        {
            "grid": {"left": 24, "right": 24, "top": 58, "bottom": 78, "containLabel": True},
            "xAxis": {
                "type": "category",
                "boundaryGap": False,
                "name": "Month in this what-if · final point marks runway",
                "nameLocation": "middle",
                "nameGap": 32,
                "data": categories,
                **axis_style(),
            },
            "yAxis": {
                "type": "value",
                "name": "Estimated buffer (CAD)",
                "nameLocation": "middle",
                "nameGap": 70,
                "axisLabel": {"color": THEME["text_muted"], "formatter": "${value}"},
                "axisLine": {"show": False},
                "splitLine": {"lineStyle": {"color": "rgba(141,153,174,.16)"}},
            },
            "series": [
                {
                    "name": "Challenge scenario",
                    "type": "line",
                    "data": [baseline_by_month.get(month) for month in categories],
                    "connectNulls": False,
                    "smooth": 0.16,
                    "showSymbol": True,
                    "symbolSize": 7,
                    "lineStyle": {"color": THEME["primary_orange"], "width": 3},
                    "itemStyle": {"color": THEME["primary_orange"]},
                    "areaStyle": {"color": "rgba(255,91,0,.10)"},
                    "emphasis": {"focus": "series", "lineStyle": {"width": 4}},
                    "markLine": {
                        "symbol": "none",
                        "silent": True,
                        "lineStyle": {"color": THEME["alert_red"], "type": "dashed"},
                        "label": {"formatter": "Buffer reaches $0", "color": THEME["alert_red"]},
                        "data": [{"yAxis": 0}],
                    },
                },
                {
                    "name": "With your adjustment",
                    "type": "line",
                    "data": [adjusted_by_month.get(month) for month in categories],
                    "connectNulls": False,
                    "smooth": 0.16,
                    "showSymbol": True,
                    "symbolSize": 7,
                    "lineStyle": {"color": THEME["accent_blue"], "width": 3, "type": "dashed"},
                    "itemStyle": {"color": THEME["accent_blue"]},
                    "emphasis": {"focus": "series", "lineStyle": {"width": 4}},
                },
            ],
        }
    )
    return options, challenge_raw_runway, challenge_depletion_step


def _render_timeline_frame(
    baseline,
    shock,
    projection_baseline,
    projection_adjusted,
    playback_key: str,
    frame_key: str,
    playing_key: str,
):
    duration = projection_baseline.duration_months
    frame = min(duration, max(0, int(st.session_state.get(frame_key, 0))))
    options, challenge_runway, depletion_step = _timeline_figure(
        baseline,
        shock,
        projection_baseline,
        projection_adjusted,
        frame,
    )
    runway_text = (
        f"Challenge runway: {shock.runway_months:.1f} months"
        if shock.monthly_gap > 0 and shock.buffer_left > 0
        else "No modeled depletion under the challenge formula"
    )
    st.progress(frame / duration, text=f"Month {frame} of {duration} · {runway_text}")
    render_chart(options, key=f"live-buffer-plot-{playback_key}", height=420)

    if frame == 0:
        st.markdown(
            f"### 🎬 The surprise lands\n"
            f"Starting buffer: **${baseline.B:,.2f}** → after the one-off cost: "
            f"**${shock.buffer_left:,.2f}**. The surprise has entered the chat."
        )
    elif (
        challenge_runway is not None
        and challenge_runway <= 120
        and depletion_step is not None
        and frame >= depletion_step
    ):
        st.warning(
            f"### 🧯 Challenge runway reached at **{shock.runway_months:.1f} months**. "
            "The chart stops at the modeled $0 point; this is a rehearsal, not a prediction."
        )
    else:
        point = projection_baseline.trajectory[frame - 1]
        if point.ending_buffer <= 0:
            st.warning(
                f"### 🧯 Month +{frame}: the modeled buffer reaches $0 or below. "
                "This is a practice scenario, not a prediction."
            )
        elif point.net_flow >= 0:
            st.success(
                f"### ✨ Month +{frame}: modeled money in covers spending. "
                f"Buffer at month end: **${point.ending_buffer:,.2f}**."
            )
        else:
            st.info(
                f"### 📅 Month +{frame}: modeled net change "
                f"**${point.net_flow:,.2f}**. Buffer at month end: "
                f"**${point.ending_buffer:,.2f}**."
            )

    if st.session_state.get(playing_key):
        if frame >= duration:
            st.session_state[playing_key] = False
            st.rerun(scope="app")
        else:
            st.session_state[frame_key] = frame + 1


def render_shock_simulator(repo: LocalDataRepository):
    st.markdown("## 🎲 Test a what-if for one account")
    st.caption(
        "Choose an account and change the assumptions to see how its savings buffer could respond. "
        "These are calculations using supplied records, not predictions or financial advice."
    )

    valid_accounts = repo.get_all_accounts()
    active_id = st.session_state.get("active_account_id", valid_accounts[0])
    if active_id not in valid_accounts:
        active_id = valid_accounts[0]
    if st.session_state.get("shock_account_id") != active_id:
        st.session_state["shock_account_id"] = active_id
    account_id = st.selectbox(
        "Choose an account",
        options=valid_accounts,
        format_func=lambda value: f"Account #{value}",
        key="shock_account_id",
    )
    st.session_state["active_account_id"] = account_id
    monthly_df = repo.get_monthly_summary(account_id)
    acc_meta = repo.get_account_meta(account_id)
    if acc_meta is None or monthly_df.empty:
        st.error("Please select a valid Account ID in the Customer Explorer first.")
        return
    baseline = compute_official_baseline(account_id, monthly_df, acc_meta)
    profile = get_customer_profile(account_id, repo, account_meta=acc_meta, baseline=baseline)
    if not profile:
        st.error("Please select a valid Account ID in the Customer Explorer first.")
        return

    # 1. Preset Shock Selection
    st.markdown("### Choose what to change")
    scenario_labels = [
        "🧘 Keep things steady",
        "📉 Income takes a dip",
        "🔧 The repair bill arrives",
        "🎭 Two plot twists at once",
    ]
    
    preset_idx = st.session_state.get("active_preset_idx", 1)  # Default: Twist 1 (EI 55%)
    if not isinstance(preset_idx, int) or not 0 <= preset_idx < len(OFFICIAL_PRESETS):
        preset_idx = 1

    preset_idx = st.radio(
        "Pick a scenario",
        options=range(len(OFFICIAL_PRESETS)),
        index=preset_idx,
        format_func=lambda index: scenario_labels[index],
        horizontal=True,
        key="scenario_picker",
        label_visibility="collapsed",
    )
    st.session_state["active_preset_idx"] = preset_idx

    chosen_preset = OFFICIAL_PRESETS[preset_idx]
    st.info(f"**What we're testing:** {scenario_display_description(chosen_preset)}")
    st.markdown("[↓ Jump to the buffer timeline](#play-the-what-if)")
    if preset_idx == 3:
        st.caption("Because apparently one plot twist wasn't enough.")

    # 2. Interactive Shock Tuning Controls
    with st.expander("⚙️ Adjust the what-if assumptions", expanded=(preset_idx == 0)):
        sc_col1, sc_col2, sc_col3, sc_col4 = st.columns(4)
        with sc_col1:
            income_pct = st.slider(
                "Money-in level (usual = 100%)",
                min_value=0,
                max_value=150,
                value=int(chosen_preset.income_multiplier * 100),
                step=5,
                key=f"income_pct_{chosen_preset.scenario_id}",
                help="Sets money coming into the account as a share of its usual level. For example, 55% means 45% less. This is not verified pay or a benefit estimate."
            ) / 100.0
        with sc_col2:
            bill_key = f"bills_pct_{chosen_preset.scenario_id}"
            if st.session_state.get(bill_key, 0) < 0:
                st.session_state[bill_key] = 0
            bills_pct = st.slider(
                "Household-bill change (%)",
                min_value=0,
                max_value=100,
                value=int(chosen_preset.household_bills_pct * 100),
                step=5,
                key=bill_key,
                help="Changes the recorded household bills. For example, +15% means bills are 15% higher; 0% leaves them unchanged."
            ) / 100.0
        with sc_col3:
            one_off_spend_mult = st.slider(
                "One-off cost (typical spending months)",
                min_value=0.0,
                max_value=3.0,
                value=float(chosen_preset.one_off_spend_multiplier),
                step=0.25,
                key=f"one_off_spend_{chosen_preset.scenario_id}",
                help="A one-time cost measured in usual monthly spending. For example, 1 means one typical month of spending."
            )
        with sc_col4:
            custom_fixed_cost = st.number_input(
                "Additional one-time cost ($ CAD)",
                min_value=0,
                max_value=50000,
                value=int(chosen_preset.one_off_fixed_amount),
                step=500,
                key=f"one_off_fixed_{chosen_preset.scenario_id}",
            )
        duration_months = st.slider(
            "How many months to show if spending does not exceed money-in",
            min_value=1,
            max_value=12,
            value=chosen_preset.duration_months,
            key=f"scenario_duration_{chosen_preset.scenario_id}",
            help="Used when the simulated monthly gap is zero or negative. Otherwise playback continues to the estimated runway, up to the 120-month formula cap.",
        )

    # Build active scenario object
    active_scenario = ShockScenario(
        scenario_id=f"CUSTOM_{chosen_preset.scenario_id}",
        name=scenario_display_name(chosen_preset),
        description=scenario_display_description(chosen_preset),
        income_multiplier=income_pct,
        household_bills_pct=bills_pct,
        one_off_spend_multiplier=one_off_spend_mult,
        one_off_fixed_amount=float(custom_fixed_cost),
        duration_months=duration_months
    )

    # Optional adjustment is customer-selected and does not change Judge Match Runway.
    judge_match_result = simulate_shock(baseline, active_scenario)
    adjustment_max = max(1, int(judge_match_result.spending_after_shock))
    st.markdown("### Try a monthly change")
    monthly_adjustment = st.slider(
        "Monthly spending change to try ($ CAD)",
        min_value=0,
        max_value=adjustment_max,
        value=0,
        step=max(1, min(100, adjustment_max // 100 or 1)),
        key=f"monthly_adjustment_{account_id}_{chosen_preset.scenario_id}",
        help="Just a what-if amount you choose. We do not decide which spending could be reduced.",
    )
    shock_res = simulate_shock(
        baseline,
        active_scenario,
        monthly_spending_adjustment=float(monthly_adjustment),
    )
    if shock_res.buffer_left <= 0:
        runway_calculation = "Runway = 0.0 months because the buffer after the one-off cost is zero or below."
    elif shock_res.monthly_gap <= 0:
        runway_calculation = "Runway = 120+ months because the modeled monthly gap is zero or below and the buffer is positive."
    else:
        runway_calculation = (
            f"Runway = min(120, ${shock_res.buffer_left:,.2f} ÷ "
            f"${shock_res.monthly_gap:,.2f}) = {shock_res.runway_label}"
        )
    if shock_res.buffer_left <= 0:
        optional_runway_calculation = "Optional runway = 0.0 months because the buffer after the one-off cost is zero or below."
    elif shock_res.adaptive_gap <= 0:
        optional_runway_calculation = "Optional runway = 120+ months because the adjusted monthly gap is zero or below and the buffer is positive."
    else:
        optional_runway_calculation = (
            f"Optional runway = min(120, ${shock_res.buffer_left:,.2f} ÷ "
            f"${shock_res.adaptive_gap:,.2f}) = {shock_res.adaptive_runway_label}"
        )

    st.markdown("---")

    # 3. Before vs After Shock Results
    st.subheader("📊 What this what-if shows")

    res1, res2, res3, res4 = st.columns(4)
    with res1:
        st.metric(
            "Money in per month",
            f"${shock_res.income_after_shock:,.2f}",
            delta=f"${shock_res.income_after_shock - baseline.I:,.2f}",
            delta_color="normal"
        )
    with res2:
        st.metric(
            "Spending per month",
            f"${shock_res.spending_after_shock:,.2f}",
            delta=f"${shock_res.spending_after_shock - baseline.S:,.2f}",
            delta_color="inverse"
        )
    with res3:
        st.metric(
            "Monthly shortfall / surplus",
            f"${shock_res.monthly_gap:,.2f}",
            delta="Surplus" if shock_res.monthly_gap <= 0 else "Shortfall",
            delta_color="inverse" if shock_res.monthly_gap > 0 else "normal"
        )
    with res4:
        st.metric(
            "Balance after one-time cost",
            f"${shock_res.buffer_left:,.2f}",
            delta=f"-${shock_res.one_off_costs:,.2f}" if shock_res.one_off_costs > 0 else "0",
            delta_color="inverse" if shock_res.one_off_costs > 0 else "off"
        )

    # 4. Estimated coverage with and without the selected adjustment
    st.markdown("### How long could the buffer last?")
    rw_col1, rw_col2 = st.columns(2)

    with rw_col1:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 20px; border-radius: 8px; border-left: 6px solid {THEME['primary_orange']};">
            <span style="font-size: 12px; color: {THEME['text_muted']}; text-transform: uppercase;">Estimated buffer coverage</span>
            <h2 style="color: {THEME['text_main']}; margin: 5px 0;">{shock_res.runway_label}</h2>
            <p style="font-size: 13px; color: {THEME['text_muted']}; margin-bottom: 0;">
                Shows how long the remaining balance could cover the modeled monthly shortfall.
            </p>
        </div>
        """, unsafe_allow_html=True)

    with rw_col2:
        st.markdown(f"""
        <div style="background-color: {THEME['card_bg']}; padding: 20px; border-radius: 8px; border-left: 6px solid {THEME['accent_blue']};">
            <span style="font-size: 12px; color: {THEME['text_muted']}; text-transform: uppercase;">With your monthly change</span>
            <h2 style="color: {THEME['accent_blue']}; margin: 5px 0;">{shock_res.adaptive_runway_label}</h2>
            <p style="font-size: 13px; color: {THEME['text_muted']}; margin-bottom: 0;">
                Tries your ${monthly_adjustment:,.2f}/month input. No category is presumed
                adjustable. Difference: {shock_res.months_gained_by_adaptation:.1f} months.
            </p>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    with st.expander("🧾 Show the calculation receipt", expanded=True):
        st.markdown(
            "Every figure below uses this account's observed monthly summary and the "
            "scenario settings above. Amounts are rounded to cents before runway is rounded to one decimal."
        )
        st.code(
            "\n".join(
                [
                    f"Typical money in (I): median of {baseline.history_months} monthly money_in rows = ${baseline.I:,.2f}",
                    f"Typical spending (S): median of {baseline.history_months} monthly money_out rows = ${baseline.S:,.2f}",
                    f"Household bills (H): median of monthly household_bills rows = ${baseline.H:,.2f}",
                    f"Buffer (B): mean avg_daily_balance over the latest {len(baseline.last_6_months_summary)} rows = ${baseline.B:,.2f}",
                    f"Simulated money in: ${baseline.I:,.2f} × {income_pct:.2f} = ${shock_res.income_after_shock:,.2f}",
                    f"Simulated spending: ${baseline.S:,.2f} + ({bills_pct:.2f} × ${baseline.H:,.2f}) = ${shock_res.spending_after_shock:,.2f}",
                    f"One-off cost: ({one_off_spend_mult:.2f} × ${baseline.S:,.2f}) + ${custom_fixed_cost:,.2f} = ${shock_res.one_off_costs:,.2f}",
                    f"Monthly gap: ${shock_res.spending_after_shock:,.2f} - ${shock_res.income_after_shock:,.2f} = ${shock_res.monthly_gap:,.2f}",
                    f"Buffer remaining: ${baseline.B:,.2f} - ${shock_res.one_off_costs:,.2f} = ${shock_res.buffer_left:,.2f}",
                    runway_calculation,
                    f"Optional spending = max(0, ${shock_res.spending_after_shock:,.2f} - ${monthly_adjustment:,.2f}) = ${shock_res.adaptive_spending:,.2f}",
                    f"Optional monthly gap = ${shock_res.adaptive_spending:,.2f} - ${shock_res.income_after_shock:,.2f} = ${shock_res.adaptive_gap:,.2f}",
                    optional_runway_calculation,
                ]
            ),
            language="text",
        )
        st.caption(
            "Source: this account's monthly records. Money coming in is not verified pay. "
            "The estimate assumes the monthly shortfall stays the same; it is not a forecast."
        )

    st.markdown("---")
    st.subheader("▶ Play the what-if")
    st.caption(
        "Watch the one-off cost arrive, then follow the modeled buffer month by month. "
        "For a positive monthly shortfall, the chart plays through to the calculated runway "
        "and marks the estimated $0 point. A no-shortfall scenario uses the selected preview "
        "length. This is a deterministic rehearsal, not a live bank feed."
    )
    timeline_duration = _timeline_duration(
        shock_res,
        no_shortfall_duration=active_scenario.duration_months,
    )
    projection_baseline = project_shock_timeline(
        baseline, shock_res, duration_months=timeline_duration, adaptive_mode=False
    )
    projection_adaptive = project_shock_timeline(
        baseline, shock_res, duration_months=timeline_duration, adaptive_mode=True
    )
    playback_key = f"{account_id}_{chosen_preset.scenario_id}"
    frame_key = f"timeline_frame_{playback_key}"
    playing_key = f"timeline_playing_{playback_key}"
    if st.session_state.get("timeline_context") != (
        account_id,
        chosen_preset.scenario_id,
        timeline_duration,
        shock_res.buffer_left,
        shock_res.monthly_gap,
        shock_res.adaptive_gap,
    ):
        st.session_state["timeline_context"] = (
            account_id,
            chosen_preset.scenario_id,
            timeline_duration,
            shock_res.buffer_left,
            shock_res.monthly_gap,
            shock_res.adaptive_gap,
        )
        st.session_state[frame_key] = 0
        st.session_state[playing_key] = False

    play_col, speed_col = st.columns([1, 2])
    with play_col:
        if st.session_state.get(playing_key, False):
            if st.button("⏸ Pause playback", key=f"pause_{playback_key}", type="secondary"):
                st.session_state[playing_key] = False
                st.rerun()
        else:
            button_label = (
                "▶ Play again"
                if st.session_state.get(frame_key, 0) >= timeline_duration
                else "▶ Play the what-if"
            )
            if st.button(button_label, key=f"play_{playback_key}", type="primary"):
                st.session_state[frame_key] = 0
                st.session_state[playing_key] = True
                st.rerun()
    with speed_col:
        playback_speed = st.select_slider(
            "Playback pace",
            options=["Cinematic", "Steady", "Quick"],
            value="Cinematic",
            key=f"playback_speed_{playback_key}",
        )
    interval = {"Cinematic": 1.0, "Steady": 0.65, "Quick": 0.3}[playback_speed]
    live_timeline = st.fragment(
        run_every=interval if st.session_state.get(playing_key, False) else None,
    )(_render_timeline_frame)
    live_timeline(
        baseline,
        shock_res,
        projection_baseline,
        projection_adaptive,
        playback_key,
        frame_key,
        playing_key,
    )

    # Survival verdict alert
    if projection_baseline.survives_full_shock_period:
        st.success(
            f"✅ **Scenario-window result:** The starting buffer remains positive through "
            f"{timeline_duration} months, ending at "
            f"${projection_baseline.ending_buffer_at_shock_end:,.2f} CAD."
        )
    else:
        st.warning(
            f"⚠️ **Scenario result:** With these assumptions, the balance reaches "
            f"zero in Month +{projection_baseline.months_until_depleted}."
        )
