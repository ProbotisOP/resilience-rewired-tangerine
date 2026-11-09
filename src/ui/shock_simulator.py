"""
Screen 3: Live twist solver — apply any shock to any account and see the runway move.
"""

from typing import Any, Dict, List
from html import escape

import numpy as np
import streamlit as st

from config.scenarios import OFFICIAL_PRESETS, ShockScenario
from src.services.baseline_metrics import calculate_runway_details, compute_official_baseline
from src.services.shock_engine import simulate_shock
from src.services.timeline_projection import _timeline_duration, _timeline_series, project_shock_timeline
from src.ui import charts
from src.ui.nav import new_click
from src.ui.presentation import scenario_display_description, scenario_display_name

PRESET_LABELS = ["Baseline", "Job loss · EI 55%", "Furnace repair · 1 month of spending", "EI 55% + bills +15%"]
PRESET_ICONS = [":material/balance:", ":material/work_off:", ":material/home_repair_service:", ":material/trending_down:"]
PRESET_CHANGES = ["No change: today's money in and spending", "Money in drops to 55% of usual",
                  "One-off bill = 1 month of typical spending", "Money in to 55% and household bills +15%"]
HEAT_INCOME = list(range(0, 105, 10))          # % of money-in kept
HEAT_BILLS = list(range(0, 55, 5))             # % household-bill increase


def _apply_pending_scenario():
    """Heatmap clicks queue slider values; apply them before the sliders are created."""
    pending = st.session_state.pop("_pending_shock", None)
    if pending:
        for key, value in pending.items():
            st.session_state[key] = value


def _use_preset(idx: int) -> None:
    st.session_state["active_preset_idx"] = idx


def _shock_cards(baseline, preset_idx: int) -> None:
    """One card per challenge shock: what changes and this account's resulting runway. Click to load it."""
    st.markdown("#### Shock examples")
    st.caption("Each card applies one challenge shock to this account. Pick one to load it into the sliders below, "
               "then fine-tune.")
    cols = st.columns(len(OFFICIAL_PRESETS))
    for i, (col, preset) in enumerate(zip(cols, OFFICIAL_PRESETS)):
        result = simulate_shock(baseline, preset)
        months = result.runway_months
        color = charts.RED if months < 3 else charts.ORANGE if months < 6 else charts.YELLOW if months < 12 else charts.TEAL
        active = i == preset_idx
        col.markdown(
            f"<div class='rr-card' style='border-left-color:{color};"
            f"{'border-color:#FF6A13;background:rgba(255,106,19,.08);' if active else ''}min-height:150px'>"
            f"<div class='rr-card-title'>{'● In use · ' if active else ''}{escape(PRESET_LABELS[i])}</div>"
            f"<div class='rr-card-value' style='color:{color}'>{escape(result.runway_label)}</div>"
            f"<div class='rr-card-body'>{escape(PRESET_CHANGES[i])}<br/>"
            f"<span style='color:#9AA3AD'>{escape(scenario_display_description(preset))}</span></div></div>",
            unsafe_allow_html=True)
        col.button("In use" if active else "Use this shock", key=f"shock_card_{i}", icon=PRESET_ICONS[i],
                   type="primary" if active else "secondary", use_container_width=True, disabled=active,
                   on_click=_use_preset, args=(i,))


def _runway_text(value: float, buffer_left: float, gap: float) -> str:
    if buffer_left <= 0:
        return "0.0 months"
    if gap <= 0:
        return "120+ months"
    return f"{value:.1f} months"


def render_shock_simulator(repo: Any):
    _apply_pending_scenario()
    accounts = repo.get_all_accounts()
    active = st.session_state.get("active_account_id", accounts[0])
    if active not in accounts:
        active = accounts[0]

    st.markdown("## Live twist solver")
    st.caption("Pick the judge's account and a shock example. Everything recalculates instantly from the official formulas. "
               "These are SIMULATED scenarios, not predictions.")

    top = st.columns([1, 3])
    with top[0]:
        st.session_state["twist_account"] = active
        st.selectbox("Account", accounts, format_func=lambda v: f"Account #{v}", key="twist_account",
                     on_change=lambda: st.session_state.update(active_account_id=int(st.session_state["twist_account"])))
    account_id = int(st.session_state["active_account_id"])
    preset_idx = int(st.session_state.setdefault("active_preset_idx", 1))
    preset = OFFICIAL_PRESETS[preset_idx]

    meta = repo.get_account_meta(account_id) or {}
    baseline = compute_official_baseline(account_id, repo.get_monthly_summary(account_id), meta)
    _shock_cards(baseline, preset_idx)

    # Slider keys are tied to the preset so switching cards loads that card's defaults.
    keys = {name: f"tw_{name}_{preset.scenario_id}" for name in ("income", "bills", "oneoff", "fixed", "adjust")}
    for name, default in (("income", int(preset.income_multiplier * 100)), ("bills", int(preset.household_bills_pct * 100)),
                          ("oneoff", float(preset.one_off_spend_multiplier)), ("fixed", int(preset.one_off_fixed_amount)),
                          ("adjust", 0)):
        st.session_state.setdefault(keys[name], default)

    st.markdown(f"#### Fine-tune: {PRESET_LABELS[preset_idx]}")

    s = st.columns(5)
    income_pct = s[0].slider("Money-in kept", 0, 150, step=5, format="%d%%", key=keys["income"])
    bills_pct = s[1].slider("Household bills change", -30, 100, step=5, format="%d%%", key=keys["bills"])
    one_off_mult = s[2].slider("One-off cost (× monthly spending)", 0.0, 3.0, step=0.25, key=keys["oneoff"])
    fixed = s[3].number_input("Extra one-off cost ($)", 0, 100000, step=500, key=keys["fixed"])
    scenario = ShockScenario(scenario_id=f"LIVE_{preset.scenario_id}", name=scenario_display_name(preset),
                             description=scenario_display_description(preset), income_multiplier=income_pct / 100,
                             household_bills_pct=bills_pct / 100, one_off_spend_multiplier=one_off_mult,
                             one_off_fixed_amount=float(fixed), duration_months=preset.duration_months)
    raw = simulate_shock(baseline, scenario)
    adjust_max = max(100, int(raw.spending_after_shock))
    if st.session_state[keys["adjust"]] > adjust_max:
        st.session_state[keys["adjust"]] = adjust_max
    adjust = s[4].slider("Test a monthly adjustment ($)", 0, adjust_max, step=50, key=keys["adjust"],
                         help="A what-if you choose. The app never decides which spending could change.")
    shock = simulate_shock(baseline, scenario, monthly_spending_adjustment=float(adjust))

    # ---------------------------------------------------------------- headline numbers
    st.markdown(
        f"<div class='rr-verdict' style='border-left-color:{charts.RED if shock.runway_months < 6 else charts.TEAL}'>"
        f"<span>SIMULATED · Account #{account_id} · {PRESET_LABELS[preset_idx]}</span>"
        f"<b>{shock.runway_label}</b> of runway (baseline {baseline.baseline_runway_label}) · "
        f"monthly gap ${shock.monthly_gap:,.2f} · buffer after one-off ${shock.buffer_left:,.2f} · {shock.resilience_status}</div>",
        unsafe_allow_html=True)
    m = st.columns(4)
    d_in, d_out = round(shock.income_after_shock - baseline.I, 2), round(shock.spending_after_shock - baseline.S, 2)
    m[0].metric("Money in / month", f"${shock.income_after_shock:,.2f}", charts.signed_money(d_in) if d_in else None)
    m[1].metric("Spending / month", f"${shock.spending_after_shock:,.2f}", charts.signed_money(d_out) if d_out else None,
                delta_color="inverse")
    m[2].metric("Monthly gap", f"${shock.monthly_gap:,.2f}", "shortfall" if shock.monthly_gap > 0 else "surplus",
                delta_color="inverse" if shock.monthly_gap > 0 else "normal")
    m[3].metric("Buffer after one-off", f"${shock.buffer_left:,.2f}", f"-${shock.one_off_costs:,.2f}" if shock.one_off_costs else "no one-off",
                delta_color="inverse" if shock.one_off_costs else "off")

    g = st.columns(3)
    with g[0]:
        charts.gauge_chart(baseline.baseline_runway, key=f"gz_b_{account_id}", title="Baseline",
                           display="120+ mo" if baseline.baseline_runway >= 120 else None)
    with g[1]:
        charts.gauge_chart(shock.runway_months, key=f"gz_s_{account_id}", title="Challenge runway (official)",
                           display="120+ mo" if shock.runway_months >= 120 else None)
    with g[2]:
        charts.gauge_chart(shock.adaptive_runway_months, key=f"gz_a_{account_id}", title=f"With ${adjust:,}/mo adjustment",
                           display="120+ mo" if shock.adaptive_runway_months >= 120 else None)

    # ---------------------------------------------------------------- buffer timeline
    duration = _timeline_duration(shock, no_shortfall_duration=max(preset.duration_months, 6))
    proj = project_shock_timeline(baseline, shock, duration_months=duration, adaptive_mode=False)
    proj_adj = project_shock_timeline(baseline, shock, duration_months=duration, adaptive_mode=True)
    x1, y1, _, _ = _timeline_series(baseline, shock, proj, shock.monthly_gap, shock.runway_months, "Challenge")
    x2, y2, _, _ = _timeline_series(baseline, shock, proj_adj, shock.adaptive_gap, shock.adaptive_runway_months, "Adjusted")
    x_axis = x1 if len(x1) >= len(x2) else x2
    pad = lambda ys: [round(v, 2) for v in ys] + [None] * (len(x_axis) - len(ys))
    replay = st.session_state.setdefault(f"replay_{account_id}", 0)
    head = st.columns([4, 1])
    head[0].markdown("#### Buffer month by month")
    if head[1].button("▶ Replay", key=f"replay_btn_{account_id}", use_container_width=True):
        st.session_state[f"replay_{account_id}"] = replay + 1
        st.rerun()
    series = [{"name": "Official challenge scenario", "data": pad(y1), "color": charts.ORANGE, "area": True}]
    if adjust:
        series.append({"name": f"With ${adjust:,}/mo adjustment", "data": pad(y2), "color": charts.BLUE, "dashed": True})
    charts.line_chart(
        x_axis, series, key=f"tl_{account_id}_{preset_idx}_{replay}", x_name="Month", y_name="Buffer ($)", height=380, zoom=len(x_axis) > 30,
        subtitle="Holds the simulated monthly gap constant (calculation convention, not a forecast) · hover for each month",
        mark_lines=[charts.mark_line(0, "Buffer reaches $0", charts.RED)],
    )

    # ---------------------------------------------------------------- monthly bridge + sensitivity
    b1, b2 = st.columns([1, 1.25])
    with b1:
        charts.bar_chart(
            ["Money in", "Spending", "Monthly gap", "One-off cost"],
            [{"name": "Baseline", "data": [baseline.I, baseline.S, max(baseline.gap, 0), 0], "color": charts.GREY},
             {"name": "This scenario", "data": [shock.income_after_shock, shock.spending_after_shock,
                                                max(shock.monthly_gap, 0), shock.one_off_costs],
              "color": charts.ORANGE, "labels": True}],
            key=f"cmp_{account_id}", x_name="Measure", y_name="Amount per month ($)", money=True, height=380, title="Baseline vs this scenario (per month)",
            subtitle="Gap shown as 0 when money in covers spending · hover for exact values")
    with b2:
        grid: List[List[float]] = []
        for bp in HEAT_BILLS:
            row = []
            for ip in HEAT_INCOME:
                spend = round(baseline.S + bp / 100 * baseline.H, 2)
                row.append(calculate_runway_details(baseline.B, round(ip / 100 * baseline.I, 2), spend, shock.one_off_costs)["runway"])
            grid.append(row)
        marker = None
        if income_pct in HEAT_INCOME and bills_pct in HEAT_BILLS:
            marker = [HEAT_INCOME.index(income_pct), HEAT_BILLS.index(bills_pct)]
        event = charts.heatmap_chart([f"{v}%" for v in HEAT_INCOME], [f"+{v}%" for v in HEAT_BILLS], grid,
                                     key=f"heat_{account_id}_{preset_idx}", x_name="Money in kept (%)", y_name="Household bills change (%)", title="Runway sensitivity (months)",
                                     subtitle="Same one-off cost · white box = current sliders · click a cell to load it", marker=marker, height=380)
        clicked = new_click(event, f"heat_{account_id}_{preset_idx}")
        if clicked and isinstance(clicked.get("data"), list):
            xi, yi = int(clicked["data"][0]), int(clicked["data"][1])
            st.session_state["_pending_shock"] = {keys["income"]: HEAT_INCOME[xi], keys["bills"]: HEAT_BILLS[yi]}
            st.rerun()

    # ---------------------------------------------------------------- recovery gap
    target = st.slider("Target runway for the recovery gap", 1, 24, 6, format="%d months", key="tw_target")
    required = round(max(0.0, shock.monthly_gap - max(shock.buffer_left, 0) / target), 2)
    st.markdown(
        f"**Recovery gap (SIMULATED):** to keep the buffer above $0 for {target} months under this scenario, the monthly "
        f"position must improve by **${required:,.2f}** = max(0, ${shock.monthly_gap:,.2f} − ${max(shock.buffer_left, 0):,.2f} ÷ {target})."
    )

    # ---------------------------------------------------------------- Snowflake cross-check + receipt
    with st.expander("Calculation receipt and Snowflake cross-check", expanded=False):
        sql_result = None
        if getattr(repo, "is_connected", False):
            try:
                sql_result = repo.run_shock_simulation(account_id, income_pct / 100, bills_pct / 100, one_off_mult,
                                                       float(fixed), float(target))
            except Exception as error:  # Show, never hide, a backend failure.
                st.error(f"Snowflake shock function failed: {error}")
        if sql_result:
            same = abs(float(sql_result["runway_months"]) - shock.runway_months) < 0.05
            st.markdown(f"{'✅' if same else '⚠️'} `MART.FN_ACCOUNT_SHOCK` in Snowflake returned "
                        f"**{float(sql_result['runway_months']):.1f} months** and a required improvement of "
                        f"**${float(sql_result['required_monthly_improvement']):,.2f}** "
                        f"({'matches' if same else 'differs from'} the Python engine).")
        st.code("\n".join([
            f"I = ${baseline.I:,.2f}   S = ${baseline.S:,.2f}   H = ${baseline.H:,.2f}   B = ${baseline.B:,.2f}",
            f"money in after shock  = {income_pct}% × ${baseline.I:,.2f} = ${shock.income_after_shock:,.2f}",
            f"spending after shock  = ${baseline.S:,.2f} + {bills_pct}% × ${baseline.H:,.2f} = ${shock.spending_after_shock:,.2f}",
            f"one-off cost          = {one_off_mult:.2f} × ${baseline.S:,.2f} + ${fixed:,.2f} = ${shock.one_off_costs:,.2f}",
            f"buffer left           = ${baseline.B:,.2f} − ${shock.one_off_costs:,.2f} = ${shock.buffer_left:,.2f}",
            f"monthly gap           = ${shock.spending_after_shock:,.2f} − ${shock.income_after_shock:,.2f} = ${shock.monthly_gap:,.2f}",
            f"runway                = {_runway_text(shock.runway_months, shock.buffer_left, shock.monthly_gap)}"
            + (f"  (= min(120, {shock.buffer_left:,.2f} ÷ {shock.monthly_gap:,.2f}))" if shock.buffer_left > 0 and shock.monthly_gap > 0 else ""),
        ]), language="text")
