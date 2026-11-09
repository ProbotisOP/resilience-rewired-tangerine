"""
Screen 4: Recovery plan — plan at a glance, four question-led tabs (situation, recovery paths, Ask TANG,
customer brief). Every visual is titled with the business question it answers and a computed one-line answer.
"""

from datetime import date
from html import escape
from typing import Any, List, Optional

import streamlit as st

from config.scenarios import OFFICIAL_PRESETS
from src.services.baseline_metrics import calculate_runway, compute_official_baseline
from src.services.recovery_planner import (
    build_backup_plan,
    build_goal_plan,
    build_resilience_gap_plan,
    recent_six_month_median_net_cash_flow,
)
from src.services.shock_engine import simulate_shock
from src.ui import charts
from src.ui.customer_explorer import FEATURE_LABELS
from src.ui.presentation import scenario_display_name

TANG_PROMPTS = [
    "Explain this plan in plain English",
    "Which path should we discuss first, and why?",
    "What has to change each month, and by when?",
    "What happens if the customer does nothing?",
    "What can't we promise the customer?",
    "Help me plan the customer conversation",
]


def _runway_display(buffer: float, gap: float, result: float) -> str:
    if buffer <= 0:
        return "0.0 months"
    if gap <= 0:
        return "120+ months"
    return f"{result:.1f} months"


def _path(buffer: float, gap: float, months: int):
    values = [round(buffer, 2)]
    for _ in range(months):
        values.append(round(values[-1] - gap, 2))
    return values


def _runs_out_month(values: List[float]) -> Optional[int]:
    """First simulated month in which the buffer is below $0 (None if it stays above $0)."""
    return next((m for m, v in enumerate(values) if v < 0), None)


LABEL_COLOURS = {"OBSERVED FACT": charts.TEAL, "CALCULATED FROM OBSERVED DATA": charts.BLUE,
                 "SIMULATED SCENARIO": charts.ORANGE, "MODEL ESTIMATE": charts.YELLOW, "PROPOSED ACTION": "#B388EB"}


def _money(v: float) -> str:
    return f"${v:,.2f}"


def _h(v: float, digits: int = 0) -> str:
    """Dollar amount for HTML answers; the entity keeps Streamlit markdown from reading $…$ as LaTeX."""
    return f"&#36;{v:,.{digits}f}"


def _question(number: int, question: str, answer_html: str) -> None:
    st.markdown(f"<div class='rr-q'>Business question {number}</div><div class='rr-qtitle'>{escape(question)}</div>"
                f"<div class='rr-answer'><b>Answer:</b> {answer_html}</div>", unsafe_allow_html=True)


def _seed(key: str, value: Any) -> Any:
    """Seed a widget's state once so the plan-at-a-glance strip can read it before the widget is drawn."""
    st.session_state.setdefault(key, value)
    return st.session_state[key]


def _set_state(**values: Any) -> None:
    st.session_state.update(values)


def _case_facts(repo, account_id, meta, base, monthly, preset, shock, target, plan, rows, goal, target_months, essential, backup):
    recent = monthly.tail(6)
    facts = {
        "account_id": int(account_id),
        "baseline (OBSERVED / CALCULATED)": {
            "typical_money_in": _money(base.I), "typical_spending": _money(base.S), "fixed_costs": _money(base.F),
            "household_bills": _money(base.H), "buffer": _money(base.B), "monthly_gap": _money(base.gap),
            "baseline_runway": base.baseline_runway_label, "months_on_record": base.history_months,
            "months_with_negative_balance_day": base.months_with_overdraft,
            "latest_6_months_with_negative_balance_day": int((recent["days_below_zero"] > 0).sum()),
            "loan": (f"status {meta.get('loan_status')} ({meta.get('loan_status_meaning')}), "
                     f"{_money(meta.get('loan_monthly_payment', 0))}/month") if meta.get("has_loan") else "none",
        },
        "scenario (SIMULATED)": {
            "name": scenario_display_name(preset), "money_in_after": _money(shock.income_after_shock),
            "spending_after": _money(shock.spending_after_shock), "one_off_cost": _money(shock.one_off_costs),
            "monthly_gap": _money(shock.monthly_gap), "runway": shock.runway_label,
            "target_months": target, "required_monthly_improvement": _money(plan.required_monthly_improvement),
            "paths": [{"path": r["Path"], "monthly_improvement": _money(r["Monthly improvement"]),
                       "monthly_gap_after": _money(r["Monthly gap"]), "runway": r["Runway"],
                       "reaches_target": r["Reaches target"], "buffer_below_zero_in_month": r["Runs out"]} for r in rows],
        },
        "reserve_goal (CALCULATED)": {"target_months": target_months, "essential_monthly_cost": _money(essential),
                                      "reserve_target": _money(goal.emergency_target or 0), "gap_to_goal": _money(goal.funding_gap or 0),
                                      "months_to_goal": goal.months_to_goal},
        "support_prompts (PROPOSED ACTION, customer decides, nothing approved)": [f"{a.title}: {a.description}" for a in backup.actions]
        + ["Any relief or product must be confirmed under current Tangerine policy."],
    }
    if meta.get("ml_stress_probability") is not None:
        facts["model (MODEL ESTIMATE, outreach research only, never a credit decision)"] = {
            "stress_probability": (">95%" if meta["ml_stress_probability"] >= 0.95 else f"{meta['ml_stress_probability'] * 100:.1f}%"),
            "tier_track_record_2025_test": repo.tier_track_record(meta.get("ml_risk_tier")) if hasattr(repo, "tier_track_record") else None,
            "as_of": meta.get("ml_as_of_month"),
            "tier": meta.get("ml_risk_tier"), "meaning": "chance of at least one negative-balance day in the next 3 months",
            "top_drivers": [FEATURE_LABELS.get(d["feature"], d["feature"]) for d in meta.get("ml_top_drivers", [])]}
    anomalies = repo.account_anomalies(account_id) if hasattr(repo, "account_anomalies") else None
    if anomalies is not None and not anomalies.empty:
        flagged = anomalies[anomalies["story"].notna()]
        facts["unusual_2025_months (MODEL ESTIMATE, anomaly detection)"] = [
            {"month": r.month, "what": r.story, "observed": _money(r.observed), "expected": _money(r.expected)}
            for r in flagged.itertuples()] or "none flagged"
    fc = repo.account_forecast(account_id) if hasattr(repo, "account_forecast") else None
    if fc is not None and not fc.empty and getattr(repo, "forecast_validated", False):
        end = fc.iloc[-1]
        facts["balance_projection (MODEL ESTIMATE, backtested)"] = {
            "month": end["month"], "projected_avg_balance": _money(end["forecast"]),
            "range_80pct": f"{_money(end['lower_bound'])} to {_money(end['upper_bound'])}"}
    return facts


def _render_story(story):
    unverified = story.get("unverified_numbers", [])
    if unverified:
        st.warning("Number check: these figures could not be traced to the facts and should not be used: " + ", ".join(unverified))
    else:
        st.success("Number check passed: every figure in the story appears in the verified facts.")
    with st.container(border=True):
        st.markdown(f"**{story.get('headline', '')}**")
        for item in story.get("statements", []):
            colour = LABEL_COLOURS.get(item.get("label"), charts.GREY)
            st.markdown(f"<span class='rr-badge' style='color:{colour};border-color:{colour}'>{escape(str(item.get('label')))}</span> "
                        f"{escape(str(item.get('text')))} <span style='color:#6B7480;font-size:.75rem'>· "
                        f"{escape(str(item.get('source')))}</span>", unsafe_allow_html=True)
        st.markdown(f"💬 *“{story.get('conversation_opener', '')}”*")
        st.caption(story.get("limits", ""))


def _story_markdown(story) -> str:
    lines = [f"**{story.get('headline', '')}**"]
    lines += [f"- [{s.get('label')}] {s.get('text')}" for s in story.get("statements", [])]
    lines += [f"- Opener: \"{story.get('conversation_opener', '')}\"", f"- Limits: {story.get('limits', '')}"]
    if story.get("unverified_numbers"):
        lines.append("- Number check FAILED for: " + ", ".join(story["unverified_numbers"]))
    return "\n".join(lines)


def _render_tang_reply(reply) -> None:
    st.markdown(escape(str(reply.get("answer", ""))).replace("$", "&#36;"), unsafe_allow_html=True)
    for p in reply.get("points", []):
        colour = LABEL_COLOURS.get(p.get("label"), charts.GREY)
        st.markdown(f"<span class='rr-badge' style='color:{colour};border-color:{colour}'>{escape(str(p.get('label')))}</span> "
                    f"{escape(str(p.get('text'))).replace('$', '&#36;')}", unsafe_allow_html=True)
    if reply.get("next_step"):
        st.markdown(f"<div class='rr-answer'><b>Next step:</b> {escape(str(reply['next_step'])).replace('$', '&#36;')}</div>",
                    unsafe_allow_html=True)
    if reply.get("unverified_numbers"):
        st.warning("Number check: do not use these figures, they are not in the plan facts: " + ", ".join(reply["unverified_numbers"]))
    elif not reply.get("error"):
        st.caption("✅ Number check passed: every figure is in the plan facts.")


def _render_tang(repo, account_id, facts) -> None:
    st.markdown("<div class='tang-hero'><div class='tang-logo'>🍊</div><div><div class='tang-name'>TANG</div>"
                "<div class='tang-sub'>Your planning assistant: explains this recovery plan and helps you prepare the "
                "customer conversation. It reads only the plan on this page.</div></div></div>", unsafe_allow_html=True)
    if not getattr(repo, "is_connected", False):
        st.warning("TANG needs the Snowflake connection; the app is running on local CSVs.")
        return
    history_key = f"tang_plan_{account_id}"
    history = st.session_state.setdefault(history_key, [])

    top = st.columns([5, 1])
    top[0].caption("TANG sees the current sliders and paths. Change a path, then ask again to compare.")
    if top[1].button("Clear chat", key="tang_plan_clear", use_container_width=True, disabled=not history):
        st.session_state[history_key] = []
        st.rerun()

    queued = None
    cols = st.columns(3)
    for i, q in enumerate(TANG_PROMPTS):
        if cols[i % 3].button(q, key=f"tang_plan_q_{i}", use_container_width=True):
            queued = q

    for msg in history:
        with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🍊"):
            if msg["role"] == "user":
                st.markdown(msg["content"])
            else:
                _render_tang_reply(msg["reply"])

    prompt = st.chat_input("Ask TANG about this recovery plan…", key="tang_plan_input") or queued
    if prompt:
        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🍊"):
            with st.spinner("TANG is reading the plan…"):
                try:
                    reply = repo.ask_plan_coach(facts, prompt, [{"role": m["role"], "content": m["content"]} for m in history])
                except Exception as error:
                    reply = {"answer": f"TANG could not answer: {type(error).__name__}: {error}", "points": [],
                             "next_step": "", "unverified_numbers": [], "error": True}
            _render_tang_reply(reply)
        history.append({"role": "user", "content": prompt})
        history.append({"role": "assistant", "content": reply.get("answer", ""), "reply": reply})


def render_recovery_planner(repo: Any):
    account_id = st.session_state.get("active_account_id")
    if account_id is None:
        st.error("Open an account first.")
        return
    meta = repo.get_account_meta(account_id) or {}
    monthly = repo.get_monthly_summary(account_id)
    base = compute_official_baseline(account_id, monthly, meta)

    head = st.columns([3, 2])
    head[0].markdown(f"## Recovery plan · Account #{account_id}")
    active_idx = st.session_state.get("active_preset_idx", 1)
    active_idx = active_idx if 0 <= active_idx < len(OFFICIAL_PRESETS) else 1
    preset_idx = head[1].selectbox("Scenario to plan for", range(len(OFFICIAL_PRESETS)), index=active_idx,
                                   format_func=lambda i: scenario_display_name(OFFICIAL_PRESETS[i]),
                                   help="Same scenario as the Live twist solver page.")
    st.session_state["active_preset_idx"] = preset_idx
    preset = OFFICIAL_PRESETS[preset_idx]
    shock = simulate_shock(base, preset)
    scen = scenario_display_name(preset)
    st.caption("How to use: ① check the situation → ② pick a recovery path → ③ ask TANG to explain it → ④ download the "
               "customer brief. Every number is arithmetic on this account's own records. Paths are SIMULATED; nothing "
               "here is advice, an approval or a product offer.")

    # ------------------------------------------------ inputs (seeded first so the glance strip can use them)
    sfx = f"{account_id}_{preset_idx}"
    k_target, k_a, k_b = f"rp_target_{sfx}", f"rp_a_{sfx}", f"rp_b_{sfx}"
    target = int(_seed(k_target, max(6, min(preset.duration_months, 24))))
    plan = build_resilience_gap_plan(buffer=shock.buffer_left, monthly_gap=shock.monthly_gap, target_months=target)
    required = plan.required_monthly_improvement
    half = float(round(required / 2, -1))
    option_a = float(_seed(k_a, half))
    option_b = float(_seed(k_b, float(required)))

    k_months, k_ess, k_contrib = f"rp_goal_months_{account_id}", f"rp_essential_{account_id}", f"rp_contrib_{account_id}"
    recent_net = recent_six_month_median_net_cash_flow(base.last_6_months_summary)
    target_months = int(_seed(k_months, 3))
    essential = float(_seed(k_ess, float(min(max(0.0, base.F), 100000.0))))
    contribution = float(_seed(k_contrib, float(min(max(0.0, recent_net or 0.0), 100000.0))))
    goal = build_goal_plan(base, target_months=target_months, custom_monthly_savings=contribution,
                           essential_monthly_cost=essential if essential > 0 else None)

    paths = [("Do nothing", 0.0, charts.RED), ("Path A", option_a, charts.YELLOW), ("Path B", option_b, charts.TEAL)]
    horizon = max(target, 6)
    months = [f"M{m}" for m in range(horizon + 1)]
    series, rows = [], []
    for name, improve, color in paths:
        p = build_resilience_gap_plan(buffer=shock.buffer_left, monthly_gap=shock.monthly_gap, target_months=target,
                                      selected_monthly_adjustment=improve)
        values = _path(shock.buffer_left, p.proposed_monthly_gap, horizon)
        out = _runs_out_month(values)
        series.append({"name": f"{name} (${improve:,.0f}/mo)", "data": values, "color": color, "dashed": name == "Do nothing"})
        rows.append({"Path": name, "Monthly improvement": improve, "Monthly gap": p.proposed_monthly_gap,
                     "Runway": _runway_display(p.available_buffer, p.proposed_monthly_gap, p.proposed_runway_months),
                     "Runway (months)": p.proposed_runway_months,
                     "Reaches target": "Yes" if p.proposed_runway_months >= target else "No",
                     "Runs out": f"M{out}" if out is not None else f"not within {horizon} months", "_color": color})
    reaching = [r["Path"] for r in rows if r["Reaches target"] == "Yes" and r["Path"] != "Do nothing"]

    # ------------------------------------------------ plan at a glance
    if shock.buffer_left <= 0:
        verdict = (f"Under <b>{escape(scen)}</b> the one-off cost uses up the whole buffer, so runway is <b>0 months</b> "
                   "under every path. Start by rebuilding the reserve.")
    elif shock.monthly_gap <= 0:
        verdict = (f"Under <b>{escape(scen)}</b>, money in still covers spending: <b>no monthly shortfall</b>. "
                   "Focus the conversation on the emergency reserve goal.")
    else:
        reach_txt = (f"<b>{' and '.join(reaching)}</b> {'gets' if len(reaching) == 1 else 'get'} there."
                     if reaching else "Neither tested path gets there yet. Try <b>Path B = minimum</b> in tab ②.")
        verdict = (f"Under <b>{escape(scen)}</b> the buffer lasts <b>{escape(shock.runway_label)}</b>. To reach "
                   f"<b>{target} months</b>, spending or money in must improve by <b>{_h(required)}/mo</b>. {reach_txt}")
    st.markdown(f"<div class='rr-verdict'><span>Plan at a glance</span>{verdict}</div>", unsafe_allow_html=True)
    g = st.columns(4)
    g[0].metric("How long today?", base.baseline_runway_label.replace("no shortfall (120+)", "120+ months"),
                help="Baseline runway = buffer ÷ (typical spending − typical money in).")
    g[1].metric("How long in the scenario?", shock.runway_label.replace("no shortfall (120+)", "120+ months"),
                delta=(f"{shock.delta_runway_vs_baseline:+.1f} months vs today"
                       if base.baseline_runway < 120 and shock.runway_months < 120 else None))
    g[2].metric(f"Change needed for {target} months", f"${required:,.0f}/mo")
    if goal.emergency_target is None:
        g[3].metric("Reserve goal", "Needs essential cost")
    else:
        g[3].metric(f"{target_months}-month reserve", "Met ✅" if goal.is_target_met else f"${goal.funding_gap:,.0f} short")

    backup = build_backup_plan(base, shock, meta)
    facts = _case_facts(repo, account_id, meta, base, monthly, preset, shock, target, plan, rows, goal, target_months,
                        essential, backup)

    tabs = st.tabs(["① Situation", "② Recovery paths", "③ 🍊 Ask TANG", "④ Customer brief"])

    # ================================================ ① situation
    with tabs[0]:
        _question(1, "How long can this customer last, today vs. if the twist hits?",
                  f"Today the buffer of <b>{_h(base.B, 2)}</b> covers <b>{escape(base.baseline_runway_label)}</b>; under "
                  f"{escape(scen)} it covers <b>{escape(shock.runway_label)}</b>. Under 3 months is red, 3–6 is amber, "
                  "6+ is green.")
        c = st.columns(2)
        with c[0]:
            charts.gauge_chart(base.baseline_runway, key=f"rp_g_base_{account_id}", title="Runway today",
                               display="120+ mo" if base.baseline_runway >= 120 else None)
        with c[1]:
            charts.gauge_chart(shock.runway_months, key=f"rp_g_shock_{sfx}", title=f"Runway · {scen}",
                               display="120+ mo" if shock.runway_months >= 120 else None)

        other_today = max(0.0, base.S - base.F)
        other_shock = max(0.0, shock.spending_after_shock - base.F)
        hole = (f"leaving a <b>{_h(shock.monthly_gap)}/mo</b> shortfall that the buffer has to cover"
                if shock.monthly_gap > 0 else f"leaving a <b>{_h(-shock.monthly_gap)}/mo</b> surplus")
        _question(2, "Where does the monthly money go, and how big is the hole?",
                  f"In the scenario, money in is <b>{_h(shock.income_after_shock)}</b> against spending of "
                  f"<b>{_h(shock.spending_after_shock)}</b>, {hole}. <b>{_h(base.F)}</b> of spending is fixed costs, "
                  "which are the hardest to change.")
        charts.bar_chart(["Money in", "Fixed costs", "Other spending", "Monthly gap"],
                         [{"name": "Today (observed)", "data": [round(base.I, 2), round(base.F, 2), round(other_today, 2),
                                                               round(base.gap, 2)], "color": charts.GREY, "labels": True},
                          {"name": f"{scen} (simulated)", "data": [round(shock.income_after_shock, 2), round(base.F, 2),
                                                                  round(other_shock, 2), round(shock.monthly_gap, 2)],
                           "color": charts.ORANGE, "labels": True}],
                         key=f"rp_flow_{sfx}", x_name="Measure", y_name="Amount per month ($)", money=True, height=330, mark_lines=[charts.mark_line(0, "$0", charts.GREY)],
                         title="Monthly money in vs. spending", subtitle="Monthly gap = spending − money in (negative = surplus)")

        st.markdown("---")
        if goal.emergency_target is None:
            q3_answer = escape(goal.plan_explanation)
        elif goal.is_target_met:
            q3_answer = (f"Yes. The buffer of <b>{_h(base.B, 2)}</b> already covers the {target_months}-month reserve of "
                         f"<b>{_h(goal.emergency_target, 2)}</b>.")
        else:
            when = (f"At <b>{_h(contribution)}/mo</b> saved it takes about <b>{goal.months_to_goal} months</b> to close."
                    if goal.months_to_goal else "Set a monthly contribution to see how long it takes to close.")
            q3_answer = (f"Not yet. The buffer is <b>{_h(goal.funding_gap, 2)}</b> short of the {target_months}-month "
                         f"reserve of <b>{_h(goal.emergency_target, 2)}</b>. {when}")
        _question(3, "Is the emergency reserve big enough?", q3_answer)
        c = st.columns(3)
        c[0].slider("Months of essential costs to cover", 1, 12, key=k_months)
        c[1].number_input("Monthly essential cost ($)", 0.0, 100000.0, step=100.0, key=k_ess,
                          help="Starts at the observed typical fixed costs (F). Edit it with the customer.")
        c[2].number_input("Monthly contribution to test ($)", 0.0, 100000.0, step=50.0, key=k_contrib,
                          help="Defaults to the latest 6-month median net cash flow (a reference, not a promise).")
        if goal.emergency_target is not None:
            met_col = charts.TEAL if goal.is_target_met else charts.RED
            charts.bar_chart(["Current buffer", "Reserve target"],
                             [{"name": "Amount", "data": [
                                 {"value": round(base.B, 2), "itemStyle": {"color": met_col},
                                  "label": {"show": True, "position": "right", "color": charts.TEXT, "formatter": f"${base.B:,.0f}"}},
                                 {"value": round(goal.emergency_target, 2), "itemStyle": {"color": charts.ORANGE},
                                  "label": {"show": True, "position": "right", "color": charts.TEXT,
                                            "formatter": f"${goal.emergency_target:,.0f}"}}]}],
                             key=f"rp_reserve_{account_id}", x_name="", y_name="Amount ($)", money=True, horizontal=True, height=200)
            if goal.months_to_goal and goal.months_to_goal > 0 and contribution > 0:
                gh = min(goal.months_to_goal + 3, 60)
                charts.line_chart(
                    [f"M{m}" for m in range(gh + 1)],
                    [{"name": "Buffer with contribution", "data": [round(base.B + contribution * m, 2) for m in range(gh + 1)],
                      "color": charts.TEAL, "area": True}],
                    key=f"rp_goal_{account_id}", x_name="Months from now", y_name="Buffer ($)", height=260, zoom=False,
                    mark_lines=[charts.mark_line(goal.emergency_target, f"Target ${goal.emergency_target:,.0f}", charts.ORANGE)],
                    title="Path to the reserve target", subtitle="Assumes the tested contribution is saved every month")
            st.caption(goal.plan_explanation)

    # ================================================ ② recovery paths
    with tabs[1]:
        st.markdown(f"**Planning for:** {scen}. Set a target runway, then test two paths. A path is a monthly improvement "
                    "(spending cut, extra money in, or both); the customer decides how.")
        c = st.columns(3)
        c[0].slider("Target runway", 1, 24, format="%d months", key=k_target)
        c[1].number_input("Path A: monthly improvement ($)", 0.0, 100000.0, step=50.0, key=k_a)
        c[2].number_input("Path B: monthly improvement ($)", 0.0, 100000.0, step=50.0, key=k_b,
                          help="Starts at the minimum improvement needed to reach the target.")
        b = st.columns(3)
        b[0].button(f"Path B = minimum needed (${required:,.0f})", key=f"rp_qb_{sfx}", use_container_width=True,
                    on_click=_set_state, kwargs={k_b: float(required)})
        b[1].button(f"Path A = half of minimum (${half:,.0f})", key=f"rp_qa_{sfx}", use_container_width=True,
                    on_click=_set_state, kwargs={k_a: half})
        b[2].button("Reset both paths", key=f"rp_qr_{sfx}", use_container_width=True,
                    on_click=_set_state, kwargs={k_a: half, k_b: float(required)})

        k = st.columns(3)
        k[0].metric("Scenario monthly gap", f"${shock.monthly_gap:,.2f}")
        k[1].metric("Buffer after one-off", f"${shock.buffer_left:,.2f}")
        k[2].metric(f"Minimum improvement for {target} months", f"${required:,.2f}/mo")

        # Q4 · which path reaches the target
        do_nothing = rows[0]
        if shock.monthly_gap <= 0:
            q4 = "Every path reaches the target, because there is no monthly shortfall in this scenario."
        elif reaching:
            q4 = (f"<b>{' and '.join(reaching)}</b> {'reaches' if len(reaching) == 1 else 'reach'} the {target}-month target. "
                  f"Doing nothing lasts <b>{escape(do_nothing['Runway'])}</b>.")
        else:
            q4 = (f"No tested path reaches {target} months yet. The minimum is <b>{_h(required)}/mo</b>; doing nothing "
                  f"lasts <b>{escape(do_nothing['Runway'])}</b>.")
        _question(4, "Which recovery path reaches the target runway?", q4)
        cap = max(target * 2, 12)
        bar_items = []
        for r in rows:
            ok = r["Reaches target"] == "Yes"
            bar_items.append({"value": min(r["Runway (months)"], cap),
                              "itemStyle": {"color": charts.TEAL if ok else (charts.RED if r["Path"] == "Do nothing" else charts.YELLOW)},
                              "label": {"show": True, "position": "right", "color": charts.TEXT,
                                        "formatter": f"{r['Runway']} · {'✓ reaches target' if ok else '✗ short'}"}})
        charts.bar_chart([f"{r['Path']} (${r['Monthly improvement']:,.0f}/mo)" for r in rows],
                         [{"name": "Runway", "data": bar_items}], key=f"rp_runway_{sfx}", x_name="Path", y_name="Runway (months)", horizontal=True, height=240,
                         value_suffix=" mo", mark_lines=[charts.mark_line(target, f"Target {target} mo", charts.ORANGE, axis="xAxis")],
                         title="Runway by path", subtitle=f"Bars capped at {cap} months for readability")

        # Q5 · when does the money run out
        outs = "; ".join(f"{escape(r['Path'])}: <b>{'below &#36;0 in ' + r['Runs out'] if r['Runs out'].startswith('M') else 'stays above &#36;0 through M' + str(horizon)}</b>"
                         for r in rows)
        _question(5, "When does the money run out under each path?", outs + ".")
        charts.line_chart(months, series, key=f"rp_paths_{sfx}", x_name="Months from now", y_name="Buffer ($)", height=340, zoom=False,
                          title="Buffer month by month", subtitle="Toggle paths in the legend · hover for month-by-month values",
                          mark_lines=[charts.mark_line(0, "$0", charts.RED)],
                          mark_areas=[[{"xAxis": f"M{target}", "itemStyle": {"color": "rgba(46,196,182,0.10)"}}, {"xAxis": f"M{horizon}"}]])

        # Q6 · what each extra dollar buys
        if shock.monthly_gap <= 0 or shock.buffer_left <= 0:
            _question(6, "What does each extra dollar a month buy?",
                      "Not applicable here: " + ("there is no monthly shortfall to close." if shock.monthly_gap <= 0
                                                 else "the buffer is already used up by the one-off cost."))
        else:
            top_x = max(required * 1.5, option_a * 1.2, option_b * 1.2, 100.0)
            xs = sorted({round(top_x * i / 20, 0) for i in range(21)} | {round(required, 0), round(option_a, 0), round(option_b, 0)})
            ys = [min(calculate_runway(shock.buffer_left, shock.monthly_gap - x), cap) for x in xs]
            lab = [f"${x:,.0f}" for x in xs]
            pts = [{"name": n, "coord": [f"${v:,.0f}", min(calculate_runway(shock.buffer_left, shock.monthly_gap - v), cap)],
                    "value": n[-1] if n.startswith("Path") else "Min", "itemStyle": {"color": col}}
                   for n, v, col in (("Minimum", required, charts.ORANGE), ("Path A", option_a, charts.YELLOW),
                                     ("Path B", option_b, charts.TEAL))]
            step = 500.0
            gain = calculate_runway(shock.buffer_left, max(shock.monthly_gap - step, 0.01)) - shock.runway_months
            gain_txt = (f"The first <b>{_h(step)}/mo</b> adds about <b>{gain:.1f} months</b>. " if shock.monthly_gap > step else "")
            _question(6, "What does each extra dollar a month buy?",
                      f"{gain_txt}The curve crosses the {target}-month line at <b>{_h(required)}/mo</b>, the minimum. "
                      "Gains speed up as the gap closes, so the last dollars matter most.")
            charts.line_chart(lab, [{"name": "Runway", "data": ys, "color": charts.ORANGE, "area": True, "smooth": True,
                                     "points": pts}],
                              key=f"rp_sens_{sfx}", x_name="Monthly improvement ($)", y_name="Runway (months)", height=320, zoom=False, money=False,
                              mark_lines=[charts.mark_line(target, f"Target {target} mo", charts.TEAL)],
                              title="Runway vs. monthly improvement",
                              subtitle=f"x = monthly improvement · y = runway (capped at {cap} months)")

        with st.expander("Path details table and formula"):
            st.dataframe([{k2: v for k2, v in r.items() if not k2.startswith("_") and k2 != "Runway (months)"} for r in rows],
                         hide_index=True, use_container_width=True,
                         column_config={"Monthly improvement": st.column_config.NumberColumn(format="dollar"),
                                        "Monthly gap": st.column_config.NumberColumn(format="dollar")})
            st.caption(f"Minimum improvement = max(0, gap − buffer ÷ target) = max(0, ${shock.monthly_gap:,.2f} − "
                       f"${max(shock.buffer_left, 0):,.2f} ÷ {target}) = ${required:,.2f}. "
                       "The customer decides which spending, if any, changes; no category is assumed discretionary.")

    # ================================================ ③ ask TANG
    with tabs[2]:
        _render_tang(repo, account_id, facts)

    # ================================================ ④ customer brief
    with tabs[3]:
        prob = meta.get("ml_stress_probability")
        model_line = (f"- MODEL ESTIMATE: {'>95%' if prob is not None and prob >= 0.95 else f'{(prob or 0) * 100:.1f}%'} chance of at least one negative-balance day in the 3 months after "
                      f"{meta.get('ml_as_of_month')} (tier: {meta.get('ml_risk_tier')}). Research signal for supportive outreach "
                      "only; never a credit decision." if prob is not None else "- MODEL ESTIMATE: not available (local CSV mode).")
        recent = monthly.tail(6)
        neg_recent = int((recent["days_below_zero"] > 0).sum())
        lines = [
            f"### Resilience support brief · Account #{account_id}",
            f"Prepared {date.today().isoformat()} · data source: {getattr(repo, 'source_label', 'Local CSV')}",
            "",
            "#### Observed facts",
            f"- Typical money in (I) ${base.I:,.2f}/mo; typical spending (S) ${base.S:,.2f}/mo; fixed costs (F) ${base.F:,.2f}/mo.",
            f"- Buffer (B) ${base.B:,.2f}; baseline runway {base.baseline_runway_label} (CALCULATED FROM OBSERVED DATA).",
            f"- {neg_recent} of the latest 6 months had a negative-balance day; {base.months_with_overdraft} such months in "
            f"{base.history_months} on record.",
            f"- Loan: {('status ' + str(meta.get('loan_status')) + ', $' + format(meta.get('loan_monthly_payment', 0), ',.2f') + '/mo') if meta.get('has_loan') else 'none'}; "
            f"authorized users: {meta.get('authorized_user_count', 0)} (access role only).",
            "",
            f"#### Simulated scenario: {scen}",
            f"- Money in ${shock.income_after_shock:,.2f}/mo, spending ${shock.spending_after_shock:,.2f}/mo, "
            f"gap ${shock.monthly_gap:,.2f}/mo, buffer after one-off ${shock.buffer_left:,.2f}.",
            f"- Runway {shock.runway_label}. Minimum improvement for {target} months: ${required:,.2f}/mo.",
            "",
            "#### Model estimate",
            model_line,
            "",
            "#### Proposed conversation (for the customer to decide)",
            f"- Reserve goal: {target_months} months × ${essential:,.2f} = ${goal.emergency_target or 0:,.2f}; "
            f"gap to goal ${goal.funding_gap or 0:,.2f}.",
            f"- Recovery paths compared: " + "; ".join(f"{r['Path']} ${r['Monthly improvement']:,.0f}/mo → {r['Runway']}" for r in rows) + ".",
        ]
        lines += [f"- {a.title}: {a.description}" for a in backup.actions]
        lines += ["- Any relief, deferral or product must be confirmed under current Tangerine policy; this brief approves nothing.",
                  "", "#### Limits",
                  "- Money in is recorded deposits and transfers, not verified income. Standing orders are undated and not assumed monthly.",
                  "- Scenario runways hold the simulated gap constant; they are not forecasts."]
        brief = "\n".join(lines)

        story_key = f"rp_story_{sfx}_{target}"
        if getattr(repo, "is_connected", False):
            if st.button("🍊 TANG, write the case story (from verified facts only)", key="rp_story_btn", type="primary"):
                with st.spinner("TANG (Cortex AI_COMPLETE) is writing a labelled story; every number is then checked…"):
                    try:
                        st.session_state[story_key] = repo.generate_case_narrative(facts)
                    except Exception as error:
                        st.error(f"TANG could not write the story: {type(error).__name__}: {error}")
        story = st.session_state.get(story_key)
        if story:
            _render_story(story)
            brief += "\n\n#### Case story (written by TANG with Cortex AI from the verified facts above)\n" + _story_markdown(story)
        with st.expander("Facts sent to TANG (nothing else is shared)"):
            st.json(facts)

        with st.container(border=True):
            st.markdown(brief)
        st.download_button("Download brief (.md)", brief, file_name=f"resilience_brief_{account_id}.md", mime="text/markdown",
                           use_container_width=True)
