"""
Hidden patterns: one page of story charts. Act 1 is what we found in the data; Act 2 is what Snowflake ML found.
Every card leads with the headline a bank would act on, then the metric, an interactive chart, the
"so what" and an honest caveat. All numbers are computed live; nothing is hard-coded.
"""

from html import escape
from typing import Any, Optional

import pandas as pd
import streamlit as st

from src.services.discovery_engine import get_portfolio_scenario_runways, get_preloan_early_warning_data
from src.services.hidden_patterns import default_rate_table, load_pattern_data
from src.services.insight_language import humanize_segment
from src.ui import charts
from src.ui.customer_explorer import FEATURE_LABELS, OUT_PARTS
from src.ui.nav import new_click, open_account
from src.ui.presentation import PRELOAN_BUFFER_LABEL, buffer_group_name, money_in_group_tick, preloan_buffer_explainer

MODEL_ORDER = ["Majority Class Baseline", "Rule-Based Heuristic", "Logistic Regression (calibrated)", "XGBoost (calibrated)"]
MODEL_SHORT = {"Majority Class Baseline": "Guess the average", "Rule-Based Heuristic": "Simple rule",
               "Logistic Regression (calibrated)": "Logistic regression", "XGBoost (calibrated)": "XGBoost"}
CASH_QUARTILES = ["Lowest 25% cash share", "25–50%", "50–75%", "Highest 25% cash share"]
WARNING_SIGNS = {
    "No authorized user": lambda l: ~l["authorized_user"].astype(bool),
    "No card": lambda l: ~l["has_card"].astype(bool),
    "Top-25% cash-deposit share": lambda l: l["cash_quartile"] == 4,
    "Non-monthly statements": lambda l: l["statement_frequency"] != "monthly statement",
    "Penalty interest before the loan": lambda l: l["pre_penalty"] == 1,
}


# ---------------------------------------------------------------------------------------------- building blocks
def _story(tag: str, headline: str, chip: Optional[str] = None) -> None:
    chip_html = f" <span class='rr-badge' style='margin-left:8px'>{escape(chip)}</span>" if chip else ""
    st.markdown(f"<div class='rr-q'>{escape(tag)}</div><div class='rr-qtitle'>{escape(headline)}{chip_html}</div>",
                unsafe_allow_html=True)


def _so_what(text: str) -> None:
    st.markdown(f"<div class='rr-answer'><b>So what for the bank:</b> {text}</div>", unsafe_allow_html=True)


def _caveat(text: str) -> None:
    with st.expander("Method & caveat"):
        st.caption(text)


def _card(col, title: str, value: str, body: str, color: str = charts.ORANGE) -> None:
    col.markdown(
        f"""<div class="rr-card" style="border-left-color:{color}">
        <div class="rr-card-title">{escape(title)}</div>
        <div class="rr-card-value" style="color:{color}">{escape(value)}</div>
        <div class="rr-card-body">{body}</div></div>""",
        unsafe_allow_html=True,
    )


def _pct(n: float, d: float) -> float:
    return round(100.0 * n / d, 1) if d else 0.0


def _times(a: float, b: float) -> str:
    return f"{a / b:.1f}×" if b else "∞"


def _jump_from(key: str) -> None:
    """Selectbox callback: open the picked account, then clear the pick so returning here doesn't jump again."""
    picked = st.session_state.get(key)
    if picked:
        st.session_state[key] = None
        st.session_state["active_account_id"] = int(picked)
        st.query_params["page"] = "account"


# ---------------------------------------------------------------------------------------------- page
def render_hidden_patterns(repo: Any):
    st.markdown("## Hidden patterns")
    st.caption("What a normal dashboard won't show you: patterns we found in the data, and patterns Snowflake ML "
               "found. Every chart is live on RESILIENCE_REWIRED_DB. Associations, not causes; simulations, not forecasts.")
    if not getattr(repo, "is_connected", False):
        st.info("This page reads Snowflake tables and ML outputs directly; it needs the Snowflake connection.")
        return

    data = load_pattern_data(repo)
    loans = data["loans"].copy()
    metrics = repo.get_portfolio_account_metrics()
    drivers = getattr(repo, "vulnerability_drivers", None)
    model_metrics = getattr(repo, "model_metrics", None)
    scores = getattr(repo, "stress_scores", None)

    _hero(loans, metrics, drivers, model_metrics, repo)
    st.markdown("---")
    st.markdown("### Act 1 · Patterns we found in the data")
    _wealth_illusion(repo, metrics)
    st.markdown("---")
    _default_fingerprint(repo, loans)
    st.markdown("---")
    _warning_signs(loans)
    st.markdown("---")
    _payday_pulse(data["payday"])
    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        _spend_mix(data["spend"])
    with c2:
        _shadow_obligations(data["off_book"], data["so_purpose"])
    st.markdown("---")
    st.markdown("### Act 2 · What Snowflake ML found")
    _top_insights(drivers)
    st.markdown("---")
    _stress_model(model_metrics, getattr(repo, "model_calibration", None), scores, metrics)
    st.markdown("---")
    _anomaly_radar(getattr(repo, "anomalies", None), data["anomaly_follow_up"], scores)
    st.markdown("---")
    _forecast_honesty(getattr(repo, "forecast_backtest", None))
    st.markdown("---")
    _monday_actions(data["hidden_risk"], loans, scores)


# ---------------------------------------------------------------------------------------------- hero
def _hero(loans, metrics, drivers, model_metrics, repo) -> None:
    runs = get_portfolio_scenario_runways(repo, income_multiplier=0.55).set_index("account_id")["runway_months"]
    frame = metrics[["I"]].join(runs)
    frame["decile"] = pd.qcut(frame["I"].rank(method="first"), 10, labels=False)
    top, bottom = frame.loc[frame["decile"] == 9, "runway_months"].median(), frame.loc[frame["decile"] == 0, "runway_months"].median()
    au = loans[loans["authorized_user"].astype(bool)]
    cols = st.columns(4)
    _card(cols[0], "Top earners at 55% money in", f"{top:.1f} months",
          f"vs <b>{bottom:.1f} months</b> for the lowest earners. More money in did not mean more runway.", charts.ORANGE)
    hidden = None if drivers is None else drivers[(drivers["accounts_under_6m_baseline"] == 0) & (drivers["segment"] != "Overall")]
    if hidden is not None and not hidden.empty:
        _card(cols[1], "Hidden risk found by ML", f"{int(hidden.iloc[0]['accounts_under_6m_ei55']):,} accounts",
              "Fine today, under 6 months after the money-in drop. None are flagged today.", charts.YELLOW)
    _card(cols[2], "Loans with an authorized user", f"{int(au['defaulted'].sum())} of {len(au)} defaulted",
          f"vs {_pct(loans['defaulted'].sum() - au['defaulted'].sum(), len(loans) - len(au))}% of loans without one.", charts.TEAL)
    if model_metrics is not None and not model_metrics.empty:
        mm = model_metrics.set_index("model_name")
        xgb, rule = mm.loc["XGBoost (calibrated)"], mm.loc["Rule-Based Heuristic"]
        _card(cols[3], "Stress model vs simple rule", f"PR-AUC {xgb['pr_auc']:.2f}",
              f"vs {rule['pr_auc']:.2f} for a rule, tested on 2025 data it never saw.", charts.BLUE)


# ---------------------------------------------------------------------------------------------- Act 1
def _wealth_illusion(repo, metrics) -> None:
    _story("Pattern 01 · we found", "The wealth illusion: the biggest earners have the shortest runway", "metric: % under 6 months")
    level = st.slider("Money in kept (drag to stress the portfolio)", 10, 100, 55, step=5, format="%d%%", key="hp_level")
    runs = get_portfolio_scenario_runways(repo, income_multiplier=level / 100).set_index("account_id")["runway_months"]
    frame = metrics[["I", "baseline_runway"]].join(runs)
    frame["decile"] = pd.qcut(frame["I"].rank(method="first"), 10, labels=[f"D{i}" for i in range(1, 11)])
    g = frame.groupby("decile", observed=True).agg(runway=("runway_months", "median"),
                                                   under6=("runway_months", lambda s: (s < 6).mean() * 100))
    left, right = st.columns([1.7, 1])
    with left:
        charts.bar_chart(
            [money_in_group_tick(c) for c in g.index],
            [{"name": f"Median runway at {level}% money in (months)", "data": g["runway"].round(1).tolist(),
              "color": charts.TEAL, "labels": True},
             {"name": "% of group under 6 months", "data": g["under6"].round(1).tolist(), "color": charts.ORANGE,
              "line": True, "axis": 1, "axis_name": "% under 6 mo", "suffix": "%"}],
            key="hp_wealth", x_name="Money-in group (lowest → highest)", y_name="Median runway (months)", value_suffix=" mo", height=360,
            title="Runway by money-in group, lowest earners on the left",
            subtitle="450 accounts per group · 120 = no monthly shortfall · move the slider above")
    with right:
        lo, hi = g.iloc[0], g.iloc[-1]
        _card(st, "Top 10% money in", f"{hi['runway']:.1f} months", f"{hi['under6']:.0f}% of them under 6 months.", charts.ORANGE)
        _card(st, "Bottom 10% money in", f"{lo['runway']:.1f} months", f"{lo['under6']:.0f}% of them under 6 months.", charts.TEAL)
    _so_what("income-based segmentation hides the most exposed customers. High earners spend almost all they bring in, "
             "so the same percentage cut opens a much bigger hole. Watch <b>spend-to-income</b>, not income.")
    _caveat("Simulation on recorded money in (not verified payroll or EI eligibility); spending and buffer held at their "
            "challenge definitions. Runway rounded to one decimal before the < 6 count.")


def _default_fingerprint(repo, loans) -> None:
    _story("Pattern 02 · we found", "The default fingerprint: four quiet traits that separate good loans from bad",
           "metric: default rate · lift")
    lens = st.segmented_control("Look at loans by", ["Authorized user", "Card", "Cash-deposit share", "Statement habit",
                                                     "Pre-loan buffer", "Penalty interest before loan"],
                                default="Authorized user", key="hp_lens") or "Authorized user"
    if lens == "Pre-loan buffer":
        pre = get_preloan_early_warning_data(repo)
        q = pre["quartile_summary"]
        t = pd.DataFrame({"group": [buffer_group_name(v) for v in q["buffer_quartile"]], "loans": q["loans"],
                          "defaults": q["defaults"], "rate": q["default_rate"].round(1)})
        with st.expander(PRELOAN_BUFFER_LABEL, icon=":material/help:", expanded=True):
            st.markdown(preloan_buffer_explainer(pre))
    elif lens == "Authorized user":
        t = default_rate_table(loans, loans["authorized_user"].map({True: "Has authorized user", False: "No authorized user"}))
    elif lens == "Card":
        t = default_rate_table(loans, loans["has_card"].map({True: "Has a card", False: "No card"}))
    elif lens == "Cash-deposit share":
        t = default_rate_table(loans, loans["cash_quartile"].map(dict(enumerate(CASH_QUARTILES, 1))), order=CASH_QUARTILES)
    elif lens == "Statement habit":
        t = default_rate_table(loans, loans["statement_frequency"])
    else:
        t = default_rate_table(loans, loans["pre_penalty"].map({1: "Penalty interest before loan", 0: "None before loan"}))
    overall = _pct(loans["defaulted"].sum(), len(loans))
    left, right = st.columns([1.6, 1])
    with left:
        charts.bar_chart(t["group"].tolist(), [{"name": "Default rate", "data": t["rate"].tolist(), "color": charts.RED,
                                                "labels": True}],
                         key=f"hp_lens_{lens}", x_name="Loan group", y_name="Default rate (%)", value_suffix="%", height=330,
                         title=f"Default rate by {lens.lower()}", subtitle=f"{len(loans)} supplied loans · dashed line = all loans",
                         mark_lines=[charts.mark_line(overall, f"all loans {overall}%")])
    with right:
        worst, best = t.loc[t["rate"].idxmax()], t.loc[t["rate"].idxmin()]
        _card(st, "Riskiest group", f"{worst['rate']:.1f}%", f"{escape(str(worst['group']))}: {int(worst['defaults'])} of "
              f"{int(worst['loans'])} loans defaulted · {_times(worst['rate'], overall)} the portfolio rate.", charts.RED)
        _card(st, "Safest group", f"{best['rate']:.1f}%", f"{escape(str(best['group']))}: {int(best['defaults'])} of "
              f"{int(best['loans'])} loans.", charts.TEAL)
    _so_what("these traits are already in the core banking system and cost nothing to check. They belong on the "
             "<b>loan-review checklist</b> as prompts for a conversation, not as automatic declines.")
    _caveat("Unadjusted associations over the supplied loan table; the default flag includes running status D. Account "
            "traits (card, authorized user, cash share) describe the whole account history, not only pre-loan. Pre-loan "
            "buffer and penalty interest use only data before the loan started. Authorized user is an access role, not a "
            "spouse or co-borrower. Not used to score anyone.")


def _reset_signs() -> None:
    st.session_state["hp_signs"] = []


def _warning_signs(loans) -> None:
    _story("Pattern 03 · we found", "Warning signs stack: each extra one multiplies the risk", "metric: default rate by sign count")
    pick_col, reset_col = st.columns([6, 1])
    with pick_col:
        picked = st.pills("Choose which warning signs to count", list(WARNING_SIGNS), selection_mode="multi",
                          default=[], key="hp_signs") or []
    reset_col.button("Reset", key="hp_signs_reset", icon=":material/restart_alt:", use_container_width=True,
                     on_click=_reset_signs, disabled=not picked)
    if not picked:
        st.info("Pick one or more warning signs above to build the stack. Each loan is counted by how many of the "
                "chosen signs its account shows, then the default rate is compared across those counts.",
                icon=":material/touch_app:")
        return
    count = sum(WARNING_SIGNS[s](loans).astype(int) for s in picked)
    t = default_rate_table(loans, count, order=list(range(len(picked) + 1))).fillna(0)
    left, right = st.columns([1.6, 1])
    with left:
        charts.bar_chart(
            [f"{int(n)} sign{'s' if n != 1 else ''}" for n in t["group"]],
            [{"name": "Default rate", "data": t["rate"].tolist(), "color": charts.RED, "labels": True},
             {"name": "Loans", "data": t["loans"].astype(int).tolist(), "color": charts.GREY, "line": True, "axis": 1,
              "axis_name": "Loans in group"}],
            key="hp_signs_chart", x_name="Warning signs on the account", y_name="Default rate (%)", value_suffix="%", height=330,
            title="Default rate by number of warning signs on the account", subtitle="Grey line = how many loans sit in each group")
    with right:
        filled = t[t["loans"] > 0]
        first, last = filled.iloc[0], filled.iloc[-1]
        _card(st, f"{int(first['group'])} signs", f"{first['rate']:.1f}%", f"{int(first['defaults'])} of {int(first['loans'])} loans defaulted.",
              charts.TEAL)
        _card(st, f"{int(last['group'])} signs", f"{last['rate']:.1f}%", f"{int(last['defaults'])} of {int(last['loans'])} loans defaulted.",
              charts.RED)
    _so_what("no single trait is damning, but together they are. A simple <b>sign count</b> sorts the loan book "
             "into a calm majority and a small group worth a call before the first missed payment.")
    _caveat("Signs are counted with equal weight and overlap; groups at the extremes are small. Descriptive, not a "
            "validated scorecard.")


def _payday_pulse(payday: pd.DataFrame) -> None:
    _story("Pattern 04 · we found", "Payday pulse: money arrives in a 10-day window, cash leaves at the same pace all month",
           "metric: share of money in by day")
    days = payday["day_of_month"].astype(int)
    window = payday[(days >= 5) & (days <= 14)]
    share = _pct(window["money_in"].sum(), payday["money_in"].sum())
    show_cash = st.toggle("Show cash withdrawals", value=True, key="hp_cash")
    series = [{"name": "Money in ($M)", "data": (payday["money_in"] / 1e6).round(1).tolist(), "color": charts.TEAL, "area": True},
              {"name": "Money out ($M)", "data": (payday["money_out"] / 1e6).round(1).tolist(), "color": charts.ORANGE}]
    if show_cash:
        series.append({"name": "Cash withdrawals ($M)", "data": (payday["cash_out"] / 1e6).round(1).tolist(),
                       "color": charts.BLUE, "dashed": True})
    left, right = st.columns([1.7, 1])
    with left:
        charts.line_chart(
            days.astype(str).tolist(), series, key="hp_payday", x_name="Day of the month", y_name="Amount ($ millions)", money=False, height=340, zoom=False,
            title="All transactions 2020–2025, summed by day of the month", subtitle="Shaded = days 5–14",
            mark_areas=[[{"xAxis": "5", "itemStyle": {"color": "rgba(46,196,182,0.08)"}}, {"xAxis": "14"}]])
    with right:
        _card(st, "Money in on days 5–14", f"{share:.0f}%", "of all money in lands in just ten days of the month.", charts.TEAL)
        cash = payday.loc[days <= 30, "cash_out"]
        _card(st, "Cash withdrawals", "flat all month", f"day-to-day variation only ±{cash.std() / cash.mean() * 100:.0f}%: "
              "spending doesn't wait for payday.", charts.BLUE)
    _so_what("the weeks <b>after</b> day 14 are when balances run down. Time savings sweeps for days 5–14 and "
             "time reminders and hardship outreach for the last week of the month.")
    _caveat("Portfolio totals across all accounts and months; individual pay dates vary. Same-day transaction order is "
            "not reliable, so no hours-level claims are made.")


def _spend_mix(spend: pd.DataFrame) -> None:
    _story("Pattern 05 · we found", "Three-quarters of spending is invisible cash", "metric: share of money out")
    row = spend.iloc[0]
    mode = st.segmented_control("Show", ["All spending", "Without cash"], default="All spending", key="hp_mix") or "All spending"
    parts = [p for p in OUT_PARTS if not (mode == "Without cash" and p[0] == "cash_withdrawals_genuine")]
    charts.donut_chart([{"name": label, "value": float(row[col]), "color": color} for col, label, color in parts],
                       key=f"hp_donut_{mode}", height=300)
    cash_share = _pct(row["cash_withdrawals_genuine"], row["money_out"])
    _card(st, "Cash withdrawals", f"{cash_share:.0f}% of money out",
          f"Household bills are {_pct(row['household_bills'], row['money_out']):.0f}%; everything else is small.", charts.BLUE)
    _so_what("the bank can't see where most money goes, so any 'cut discretionary spending' advice is guesswork. "
             "Moving customers to <b>card and digital payments</b> is what makes coaching possible.")
    _caveat("Cash withdrawals are not assumed to be discretionary or compressible; they may pay rent or essentials.")


def _shadow_obligations(off_book: pd.DataFrame, purposes: pd.DataFrame) -> None:
    _story("Pattern 06 · we found", "Shadow debt: loan payments to loans we don't hold", "metric: off-book monthly payments")
    bins = [0, 1000, 2000, 3000, 4000, 5000, float("inf")]
    labels = ["< $1k", "$1–2k", "$2–3k", "$3–4k", "$4–5k", "$5k+"]
    buckets = pd.cut(off_book["monthly_amount"], bins, labels=labels, right=False).value_counts().reindex(labels).fillna(0)
    charts.bar_chart(labels, [{"name": "Accounts", "data": buckets.astype(int).tolist(), "color": charts.YELLOW, "labels": True}],
                     key="hp_offbook", x_name="Monthly 'loan payment' amount", y_name="Accounts", height=250, title="Monthly 'loan payment' orders on accounts with no loan here")
    leasing = purposes.loc[purposes["purpose"] == "leasing", "accounts"]
    _card(st, "Off-book loan payments", f"{len(off_book)} accounts · {charts.money_text(off_book['monthly_amount'].sum())}/mo",
          f"median {charts.money_text(off_book['monthly_amount'].median())} a month leaving for a loan the bank can't see"
          + (f"; another <b>{int(leasing.iloc[0])}</b> accounts have leasing orders." if not leasing.empty else "."), charts.YELLOW)
    amounts = off_book.set_index("account_id")["monthly_amount"]
    st.selectbox("Open one of these accounts", off_book["account_id"].astype(int).tolist(),
                 format_func=lambda a: f"#{a} · {charts.money_text(amounts.at[a])}/mo",
                 key="hp_offbook_pick", index=None, placeholder="Pick an account…",
                 on_change=_jump_from, args=("hp_offbook_pick",))
    _so_what("these customers already carry debt elsewhere. It's a <b>refinancing</b> conversation and an affordability "
             "fact the runway formula doesn't see.")
    _caveat("Standing orders are an undated snapshot; a 'loan payment' label doesn't confirm an outstanding external loan.")


# ---------------------------------------------------------------------------------------------- Act 2
def _top_insights(drivers) -> None:
    _story("Pattern 07 · Snowflake ML TOP_INSIGHTS", "Why the portfolio cracks: it's spending habits, not income",
           "metric: extra accounts under 6 months")
    if drivers is None or drivers.empty:
        st.caption("Top Insights output (ML.EI55_VULNERABILITY_DRIVERS) is not available.")
        return
    overall = drivers[drivers["segment"] == "Overall"]
    top = drivers[drivers["segment"] != "Overall"].copy()
    top["label"] = top["segment"].map(humanize_segment)
    top = top.drop_duplicates("label").head(8).reset_index(drop=True)
    left, right = st.columns([1.6, 1])
    with left:
        event = charts.bar_chart(
            top["label"].tolist()[::-1],
            [{"name": "Extra accounts under 6 months", "data": top["contribution"].round(0).astype(int).tolist()[::-1],
              "color": charts.ORANGE, "labels": True}],
            key="hp_ti", x_name="Segment", y_name="Extra accounts under 6 months", horizontal=True, height=430, clickable=True,
            highlight=st.session_state.get("hp_ti_pick"),
            title="Segments behind the jump (click a bar)",
            subtitle="Control = today, test = 55% money in · gender and age deliberately excluded")
    clicked = new_click(event, "hp_ti")
    if clicked:
        st.session_state["hp_ti_pick"] = clicked["name"]
        st.rerun()
    pick = st.session_state.get("hp_ti_pick") or top.iloc[0]["label"]
    row = top[top["label"] == pick].iloc[0] if (top["label"] == pick).any() else top.iloc[0]
    with right:
        if not overall.empty:
            o = overall.iloc[0]
            _card(st, "Whole portfolio", f"{int(o['accounts_under_6m_baseline'])} → {int(o['accounts_under_6m_ei55']):,}",
                  "accounts under 6 months, today vs 55% money in.", charts.GREY)
        before, after = int(row["accounts_under_6m_baseline"]), int(row["accounts_under_6m_ei55"])
        _card(st, "Selected segment", f"{before} → {after:,} accounts",
              f"{escape(row['label'])} · explains <b>{row['relative_contribution'] * 100:.0f}%</b> of the jump"
              + (" · <b>nobody</b> in it is at risk today." if before == 0 else f" · {_times(after, before)} growth."),
              charts.YELLOW if before == 0 else charts.ORANGE)
    _so_what("the ML didn't pick income groups; it picked <b>spend-to-income ratios</b>. One ratio explains almost all of the "
             "jump, and it's already computable from the core system.")
    _caveat("TOP_INSIGHTS compares the baseline (control) with the simulated 55% money-in scenario (test). Segments "
            "overlap and explain a simulated change, not a cause.")


def _stress_model(model_metrics, calibration, scores, metrics) -> None:
    _story("Pattern 08 · Snowflake ML · XGBoost on Snowpark", "The model finds 3-month stress far better than a rule",
           "metric: precision in top 5%")
    if model_metrics is None or model_metrics.empty:
        st.caption("Model metrics (ML.MODEL_EVALUATION_METRICS) are not available.")
        return
    mm = model_metrics.set_index("model_name").reindex(MODEL_ORDER).dropna(how="all")
    base_rate = float(mm["positive_count"].iloc[0] / mm["sample_count"].iloc[0] * 100)
    xgb = mm.loc["XGBoost (calibrated)"]
    c1, c2 = st.columns([1.3, 1])
    with c1:
        charts.bar_chart(
            [MODEL_SHORT[m] for m in mm.index],
            [{"name": "PR-AUC (×100)", "data": (mm["pr_auc"] * 100).round(1).tolist(), "color": charts.BLUE, "labels": True},
             {"name": "Precision in top 5% (%)", "data": (mm["precision_at_5pct"] * 100).round(1).tolist(), "color": charts.ORANGE,
              "labels": True}],
            key="hp_ladder", x_name="Model", y_name="Score (%)", height=330, title="Model ladder on 2025 data it never saw",
            subtitle=f"{int(xgb['sample_count']):,} account-months · {int(xgb['positive_count'])} had stress · base rate {base_rate:.1f}%",
            mark_lines=[charts.mark_line(base_rate, f"base rate {base_rate:.1f}%", charts.RED)])
    with c2:
        _card(st, "Calls that hit", f"{xgb['precision_at_5pct'] * 100:.0f}% of the top 5%",
              f"{_times(xgb['precision_at_5pct'] * 100, base_rate)} the base rate of {base_rate:.1f}%; catches "
              f"{xgb['recall_at_5pct'] * 100:.0f}% of all stress months.", charts.ORANGE)
        if calibration is not None and not calibration.empty:
            charts.line_chart(
                [f"Bin {int(b)}" for b in calibration["bin"]],
                [{"name": "Predicted %", "data": (calibration["mean_predicted"] * 100).round(2).tolist(), "color": charts.BLUE, "dashed": True},
                 {"name": "Observed %", "data": (calibration["observed_rate"] * 100).round(2).tolist(), "color": charts.TEAL}],
                key="hp_calib", x_name="Model-score group (lowest → highest)", y_name="Share stressed (%)", money=False, height=230, zoom=False,
                title="Calibration: predicted vs what happened")
    if scores is not None and not scores.empty:
        flagged = scores[scores["risk_tier"] != "Standard"].join(metrics[["B"]])
        groups = []
        for tier, color, size in (("Watch (top 5%)", charts.YELLOW, 8), ("Priority outreach (top 2%)", charts.RED, 11)):
            sub = flagged[flagged["risk_tier"] == tier]
            groups.append({"name": f"{tier} ({len(sub)})", "color": color, "size": size, "opacity": 0.9,
                           "data": [[round(r.stress_probability * 100, 1), round(r.B, 2), int(i),
                                     f"Main driver: {FEATURE_LABELS.get(r.primary_risk_driver, r.primary_risk_driver)}"]
                                    for i, r in sub.iterrows()]})
        d1, d2 = st.columns([1.6, 1])
        with d1:
            event = charts.scatter_chart(groups, key="hp_tiers", x_name="Stress estimate, next 3 months (%)", y_name="Buffer: 6-month average balance ($)",
                                         x_money=False, height=360, title="Every flagged account: click a dot to open it",
                                         subtitle="Hover shows the model's main driver for that account")
            clicked = new_click(event, "hp_tiers")
            if clicked and isinstance(clicked.get("data"), list) and len(clicked["data"]) > 2:
                open_account(int(clicked["data"][2]))
        with d2:
            top_drivers = flagged["primary_risk_driver"].map(lambda f: FEATURE_LABELS.get(f, f)).value_counts().head(5)
            charts.bar_chart(top_drivers.index.tolist()[::-1], [{"name": "Flagged accounts", "data": top_drivers.tolist()[::-1],
                                                                 "color": charts.RED, "labels": True}],
                             key="hp_tier_drivers", x_name="Main driver", y_name="Flagged accounts", horizontal=True, height=360, title="What drives the flags")
    _so_what("with outreach capacity for 5% of customers, the model makes roughly <b>1 in 3 calls count</b>, against "
             "fewer than 1 in 50 at random. Every flag comes with its reason.")
    _caveat("Target: a negative-balance day in the next 3 months. Trained to 2023, calibrated on 2024, tested on 2025 "
            "(out of time). Tiers are capacity bands, not credit decisions.")


def _anomaly_radar(anomalies, follow_up, scores) -> None:
    _story("Pattern 09 · Snowflake ML ANOMALY_DETECTION", "A second pair of eyes: anomalies catch people the risk model calls 'standard'",
           "metric: flagged accounts · follow-up stress")
    if anomalies is None or anomalies.empty:
        st.caption("Anomaly output (ML.ACCOUNT_MONTH_ANOMALIES) is not available.")
        return
    flagged = anomalies[anomalies["story"].notna()]
    by_month = flagged.groupby(["month", "story"]).size().unstack(fill_value=0).sort_index()
    left, right = st.columns([1.6, 1])
    with left:
        series = [{"name": col, "data": by_month[col].astype(int).tolist(),
                   "color": charts.RED if "low money" in col else charts.YELLOW} for col in by_month.columns]
        event = charts.bar_chart(by_month.index.tolist(), series, key="hp_anom", x_name="Month (2025)", y_name="Months flagged", stacked=True, height=330, clickable=True,
                                 title="Flagged months in 2025 (click a month)", subtitle="Outside the 99.8% range and at least $500 / 25% off expected")
    clicked = new_click(event, "hp_anom")
    if clicked:
        st.session_state["hp_anom_month"] = clicked["name"]
    with right:
        drop_accounts = set(flagged.loc[flagged["story"] == "Unusually low money in", "account_id"])
        overlap = 0
        if scores is not None:
            overlap = int(scores.loc[scores.index.isin(drop_accounts), "risk_tier"].ne("Standard").sum())
        _card(st, "Unusual money-in drops", f"{len(drop_accounts):,} accounts",
              f"only <b>{overlap}</b> of them are on the stress model's watch lists: the two signals see different people.",
              charts.RED)
        fu = follow_up.set_index(["measure", "flagged"])
        if ("MONEY_IN", True) in fu.index and ("MONEY_IN", False) in fu.index:
            yes, no = fu.loc[("MONEY_IN", True)], fu.loc[("MONEY_IN", False)]
            ry, rn = _pct(yes["followed_by_negative"], yes["months"]), _pct(no["followed_by_negative"], no["months"])
            _card(st, "Negative day in the next 3 months", f"{ry}% vs {rn}%",
                  f"after a flagged money-in drop vs other months ({_times(ry, rn)}; only {int(yes['followed_by_negative'])} cases).",
                  charts.YELLOW)
    month = st.session_state.get("hp_anom_month")
    if month:
        rows = flagged[flagged["month"] == month][["account_id", "story", "observed", "expected"]].sort_values("observed")
        st.caption(f"Accounts flagged in {month}: pick one to open it")
        st.dataframe(rows, hide_index=True, use_container_width=True, height=180,
                     column_config={"observed": st.column_config.NumberColumn("Observed", format="dollar"),
                                    "expected": st.column_config.NumberColumn("Expected", format="dollar")})
        st.selectbox("Open account", rows["account_id"].astype(int).unique().tolist(), index=None,
                     format_func=lambda a: f"#{a}", key="hp_anom_pick", placeholder="Pick an account…",
                     on_change=_jump_from, args=("hp_anom_pick",))
    _so_what("the risk model watches <b>levels</b>; anomaly detection watches <b>change</b>. Together they cover "
             "customers whose income just broke pattern before their balance shows it.")
    _caveat("One series per account, trained on months up to 2024-12 (12+ months needed). The follow-up lift is small "
            "and based on few cases; treat it as a prompt to check in, not a prediction.")


def _forecast_honesty(backtest) -> None:
    _story("Pattern 10 · Snowflake ML FORECAST", "The model we didn't ship, and why that matters", "metric: forecast error (MAE)")
    if backtest is None or backtest.empty:
        st.caption("Forecast backtest (ML.FORECAST_BACKTEST_METRICS) is not available.")
        return
    left, right = st.columns([1.6, 1])
    with left:
        charts.line_chart(
            [f"+{int(h)} mo" for h in backtest["horizon"]],
            [{"name": "ML FORECAST", "data": backtest["mae_forecast"].round(0).tolist(), "color": charts.BLUE},
             {"name": "Flat balance (naive)", "data": backtest["mae_naive"].round(0).tolist(), "color": charts.TEAL},
             {"name": "Challenge formula", "data": backtest["mae_constant_gap"].round(0).tolist(), "color": charts.GREY, "dashed": True}],
            key="hp_fc", x_name="Forecast horizon", y_name="Average error ($)", height=300, zoom=False,
            title="Balance forecast error by horizon, 2025 backtest (lower is better)")
    with right:
        wins = int((backtest["mae_forecast"] < backtest["mae_naive"]).sum())
        _card(st, "Horizons where ML beat 'flat'", f"{wins} of {len(backtest)}",
              f"{int(backtest['accounts'].iloc[0]):,} accounts backtested · 80% range held the truth "
              f"{backtest['interval_80_coverage'].mean() * 100:.0f}% of the time.", charts.BLUE)
    _so_what("we only put a model in front of customers when it beats a simple baseline. This one didn't, so the app "
             "hides balance projections. That discipline is what makes the other flags <b>trustworthy</b>.")
    _caveat("Trained on months up to 2024-12, forecasting 2025-01..06 for accounts with full actuals.")


# ---------------------------------------------------------------------------------------------- close
def _monday_actions(hidden_risk, loans, scores) -> None:
    st.markdown("### Monday-morning actions")
    cols = st.columns(3)
    actions = []
    if not hidden_risk.empty:
        h = hidden_risk.iloc[0]
        actions.append(("Coach the hidden-risk high earners",
                        f"{len(hidden_risk)} top earners spend 90–100% of money in; {int((hidden_risk['runway_under_ei_55'] < 6).sum())} "
                        "fall under 6 months if money in drops. Offer an automatic savings sweep on days 5–14.",
                        int(h["account_id"]), charts.YELLOW))
    count = sum(WARNING_SIGNS[s](loans).astype(int) for s in list(WARNING_SIGNS)[:4])
    current = loans.assign(signs=count)[(loans["loan_status"] == "C")].sort_values("signs", ascending=False)
    if not current.empty:
        c = current.iloc[0]
        actions.append(("Call current borrowers with 3+ signs",
                        f"{int((current['signs'] >= 3).sum())} running loans are still current but carry 3+ warning signs. "
                        "A check-in now is cheaper than a collection later.", int(c["account_id"]), charts.RED))
    if scores is not None and not scores.empty:
        p = scores[scores["risk_tier"] == "Priority outreach (top 2%)"]
        actions.append(("Work the priority outreach list",
                        f"{len(p)} accounts in the model's top 2%, each with its main driver. Start with the highest score.",
                        int(scores["stress_probability"].idxmax()), charts.ORANGE))
    for col, (title, body, account, color) in zip(cols, actions):
        _card(col, title, f"#{account}", body, color)
        if col.button("Open example account", key=f"hp_action_{account}", use_container_width=True):
            open_account(account)
    st.caption("Examples are chosen by rule (lowest simulated runway, most signs, highest score), not hand-picked.")
