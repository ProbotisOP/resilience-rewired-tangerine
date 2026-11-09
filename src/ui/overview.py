"""
Screen 1: Portfolio snapshot — interactive portfolio map, scenario thresholds and live what-if.
"""

from typing import Any

import numpy as np
import pandas as pd
import streamlit as st

from src.services.discovery_engine import (
    get_income_decile_discovery,
    get_population_scenario_distributions,
    get_population_summary,
    get_portfolio_scenario_runways,
    get_preloan_early_warning_data,
)
from src.services.insight_language import humanize_segment
from src.ui import charts
from src.ui.nav import new_click, open_account
from src.ui.presentation import (MONEY_IN_GROUP_NOTE, PRELOAN_BUFFER_LABEL, buffer_group_name, money_in_group_range_text,
                                 money_in_group_ranges, money_in_group_tick, money_in_ranges_caption,
                                 preloan_buffer_explainer)

SCENARIO_LABELS = {
    "Baseline (Status Quo)": "Baseline",
    "Job Loss (EI @ 55%)": "Money-in 55%",
    "Emergency Repair (Cost = S)": "Repair = 1 mo spend",
    "Combined Shock (EI 55% + Bills +15%)": "55% + bills +15%",
}
RUNWAY_BANDS = [(0, 3, "< 3 mo", charts.RED), (3, 6, "3–6 mo", charts.ORANGE), (6, 12, "6–12 mo", charts.YELLOW),
                (12, 120, "12–120 mo", charts.BLUE), (120, 1e9, "No shortfall", charts.TEAL)]


def _band(runway: pd.Series) -> pd.Series:
    labels = pd.Series("No shortfall", index=runway.index)
    for lo, hi, name, _ in RUNWAY_BANDS[:-1]:
        labels[(runway >= lo) & (runway < hi)] = name
    return labels


def _card(col, title: str, value: str, body: str, color: str) -> None:
    col.markdown(
        f"""<div class="rr-card" style="border-left-color:{color}">
        <div class="rr-card-title">{title}</div>
        <div class="rr-card-value" style="color:{color}">{value}</div>
        <div class="rr-card-body">{body}</div></div>""",
        unsafe_allow_html=True,
    )


def render_overview(repo: Any):
    st.markdown("## Portfolio snapshot")
    st.caption(
        f"Data source: **{getattr(repo, 'source_label', 'Local CSV')}** · one value per account first, "
        "then medians across accounts. Scenario results are simulations, not forecasts."
    )
    summary = get_population_summary(repo)
    metrics = repo.get_portfolio_account_metrics()

    k = st.columns(6)
    k[0].metric("Accounts", f"{summary.total_accounts:,}")
    k[1].metric("Median money in (I)", f"${summary.median_I:,.0f}")
    k[2].metric("Median spending (S)", f"${summary.median_S:,.0f}")
    k[3].metric("Median buffer (B)", f"${summary.median_B:,.0f}")
    k[4].metric("In deficit (S > I)", f"{summary.accounts_in_deficit:,}", f"{summary.pct_in_deficit}%",
                delta_color="off")
    k[5].metric("Median fixed costs (F)", f"${summary.median_F:,.0f}")

    # ---------------------------------------------------------------- headline finding
    deciles = get_income_decile_discovery(repo)
    ranges = money_in_group_ranges(metrics["I"])
    st.markdown("### Biggest finding: higher money-in does not mean more resilience")
    st.caption(f"{MONEY_IN_GROUP_NOTE} (450 accounts each). Each bar shows what happens to one group if money in "
               "drops to 55%.")
    left, right = st.columns([1.6, 1])
    with left:
        charts.bar_chart(
            [money_in_group_tick(c) for c in deciles["Income Decile"]],
            [
                {"name": "Median runway, money-in at 55% (months)", "data": deciles["Median Runway (EI 55%)"].round(1).tolist(),
                 "color": charts.TEAL, "labels": True},
                {"name": "% of group under 6 months", "data": deciles["% Below 6 Months"].tolist(), "color": charts.ORANGE,
                 "line": True, "axis": 1, "axis_name": "% under 6 mo", "suffix": "%"},
            ],
            key="ov_deciles", x_name="Money-in group (lowest → highest)", y_name="Median runway (months)",
            title="If money in drops to 55%, how long does each money-in group last?",
            subtitle="Groups run from the lowest money in (left) to the highest (right) · hover any bar",
            value_suffix=" mo",
            height=380,
        )
        st.caption(money_in_ranges_caption(ranges))
    with right:
        d1, d10 = deciles.iloc[0], deciles.iloc[-1]
        _card(st, f"Lowest money-in group · bottom 10% ({money_in_group_range_text('D1', ranges)})", f"{d1['Median Runway (EI 55%)']:.1f} months",
              f"Median simulated runway; {int(d1['Accounts Below 6 Months'])} of {int(d1['Accounts'])} accounts "
              f"({d1['% Below 6 Months']:.1f}%) fall under 6 months.", charts.TEAL)
        _card(st, f"Highest money-in group · top 10% ({money_in_group_range_text('D10', ranges)})", f"{d10['Median Runway (EI 55%)']:.1f} months",
              f"{int(d10['Accounts Below 6 Months'])} of {int(d10['Accounts'])} accounts ({d10['% Below 6 Months']:.1f}%) "
              "fall under 6 months: spending scales with money-in, so a 45% cut opens a larger gap.", charts.ORANGE)
        st.caption("Simulation on recorded money-in (not verified payroll or EI eligibility). Association, not cause.")

    drivers = getattr(repo, "vulnerability_drivers", None)
    if drivers is not None and not drivers.empty:
        st.markdown("#### Why the portfolio cracks at 55% money-in — Snowflake ML Top Insights")
        total = drivers.loc[drivers["segment"] == "Overall"]
        jump = int(total["contribution"].iloc[0]) if not total.empty else int(drivers["contribution"].max())
        top = drivers[drivers["segment"] != "Overall"].head(8).copy()
        top["label"] = top["segment"].map(humanize_segment)
        top = top.drop_duplicates("label")
        a, b = st.columns([1.6, 1])
        with a:
            charts.bar_chart(
                top["label"].tolist()[::-1],
                [{"name": "Extra accounts under 6 months (baseline → 55% money-in)",
                  "data": top["contribution"].round(0).astype(int).tolist()[::-1], "color": charts.ORANGE, "labels": True}],
                key="ov_drivers", x_name="Segment", y_name="Extra accounts under 6 months", horizontal=True, height=460,
                title=f"Segments behind the jump of {jump:,} accounts under 6 months",
                subtitle="TOP_INSIGHTS · \"spends 90%+\" = typical spending ≥ 90% of typical money in · \"top 10% money-in\" = highest money-in group · no gender/age")
        with b:
            lead = top.iloc[0]
            _card(st, "Largest driver", f"{lead['relative_contribution'] * 100:.0f}% of the jump", f"{lead['label']}: "
                  f"{int(lead['accounts_under_6m_baseline'])} → {int(lead['accounts_under_6m_ei55'])} accounts under 6 months.",
                  charts.ORANGE)
            hidden = drivers[(drivers["accounts_under_6m_baseline"] == 0) & (drivers["segment"] != "Overall")]
            if not hidden.empty:
                h = hidden.iloc[0]
                _card(st, "Hidden risk: fine today, exposed tomorrow", f"0 → {int(h['accounts_under_6m_ei55'])} accounts",
                      f"{humanize_segment(h['segment'])}. None of them is under 6 months today.", charts.YELLOW)
            st.caption("Segments are descriptive and overlap; they explain the simulated change, not a cause.")

    st.markdown("---")

    # ---------------------------------------------------------------- portfolio map
    st.markdown("### Portfolio map — click any dot to open that account")
    scenario_runway = get_portfolio_scenario_runways(repo, income_multiplier=0.55).set_index("account_id")["runway_months"]
    frame = metrics[["I", "S", "B", "baseline_runway"]].join(scenario_runway.rename("ei_runway"))
    frame["band"] = _band(frame["ei_runway"])
    scores = getattr(repo, "stress_scores", None)
    colour_by = st.radio("Colour accounts by", ["Simulated runway at 55% money-in", "Stress model tier"],
                         horizontal=True, key="ov_colour", disabled=scores is None,
                         help=None if scores is not None else "Model scores need the Snowflake connection.")
    active = st.session_state.get("active_account_id")
    groups = []
    if colour_by == "Stress model tier" and scores is not None:
        frame = frame.join(scores[["risk_tier", "stress_probability"]])
        tiers = [("Standard", charts.GREY, 5, 0.45), ("Watch (top 5%)", charts.YELLOW, 8, 0.9),
                 ("Priority outreach (top 2%)", charts.RED, 10, 0.95)]
        for name, color, size, opacity in tiers:
            sub = frame[frame["risk_tier"] == name]
            groups.append({"name": f"{name} ({len(sub):,})", "color": color, "size": size, "opacity": opacity,
                           "data": [[round(r.I, 2), round(r.B, 2), int(i), f"Stress estimate: {r.stress_probability * 100:.1f}%"]
                                    for i, r in sub.iterrows()]})
    else:
        for _, _, name, color in RUNWAY_BANDS:
            sub = frame[frame["band"] == name]
            groups.append({"name": f"{name} ({len(sub):,})", "color": color, "size": 6,
                           "data": [[round(r.I, 2), round(r.B, 2), int(i),
                                     f"Runway at 55% money-in: {'120+' if r.ei_runway >= 120 else f'{r.ei_runway:.1f}'} mo"]
                                    for i, r in sub.iterrows()]})
    highlight = None
    if active in frame.index:
        highlight = [round(frame.at[active, "I"], 2), round(frame.at[active, "B"], 2), int(active), "Active account"]
    event = charts.scatter_chart(
        groups, key="ov_map", x_name="Typical money in per month ($)", y_name="Buffer: 6-month average balance ($)",
        title="Money in vs buffer, all 4,500 accounts",
        subtitle="Scroll to zoom · drag to pan · click legend items to hide groups · white ring = active account",
        highlight_point=highlight, height=500,
    )
    clicked = new_click(event, "ov_map")
    if clicked and isinstance(clicked.get("data"), list) and len(clicked["data"]) > 2:
        open_account(int(clicked["data"][2]))

    st.markdown("---")

    # ---------------------------------------------------------------- scenario thresholds
    st.markdown("### How the challenge scenarios move the portfolio")
    scen = get_population_scenario_distributions(repo)
    cats = [SCENARIO_LABELS.get(s, s) for s in scen["Scenario"]]
    c1, c2 = st.columns([1.3, 1])
    with c1:
        charts.bar_chart(
            cats,
            [{"name": "Under 3 months", "data": scen["Below 3M (%)"].tolist(), "color": charts.RED},
             {"name": "Under 6 months", "data": scen["Below 6M (%)"].tolist(), "color": charts.ORANGE},
             {"name": "Under 12 months", "data": scen["Below 12M (%)"].tolist(), "color": charts.BLUE}],
            key="ov_scen", x_name="Scenario", y_name="Share of accounts (%)", title="Share of accounts below each runway marker", value_suffix="%", height=360,
            subtitle="Toggle thresholds in the legend · hover a bar for exact counts",
        )
    with c2:
        st.dataframe(
            scen.assign(Scenario=cats).style.format(
                {"Below 3M": "{:,}", "Below 6M": "{:,}", "Below 12M": "{:,}",
                 "Below 3M (%)": "{:.1f}%", "Below 6M (%)": "{:.1f}%", "Below 12M (%)": "{:.1f}%"}),
            hide_index=True, use_container_width=True, height=200,
        )
        st.caption("Runway is rounded to one decimal before the strict < 3 / < 6 / < 12 counts, matching the judges' method.")

    # ---------------------------------------------------------------- live what-if
    st.markdown("### Live portfolio what-if")
    st.caption("Starts at the baseline (no change), so both bars match. Drag a slider or pick a twist to see how the "
               "portfolio moves away from today.")
    presets = [("↺ Reset to baseline", 100, 0, 0.0), ("Job loss: money-in 55%", 55, 0, 0.0),
               ("Repair = 1 month of spending", 100, 0, 1.0), ("55% money-in + bills +15%", 55, 15, 0.0)]
    pc = st.columns(len(presets))
    for col, (label, inc, bil, one) in zip(pc, presets):
        col.button(label, key=f"ov_preset_{label}", use_container_width=True, on_click=st.session_state.update,
                   kwargs={"ov_income": inc, "ov_bills": bil, "ov_oneoff": one})
    d1c, d2c, d3c = st.columns(3)
    income_level = d1c.slider("Money-in kept", 0, 150, 100, 5, format="%d%%", key="ov_income")
    bills = d2c.slider("Household bills change", -30, 100, 0, 5, format="%d%%", key="ov_bills")
    one_off = d3c.slider("One-off cost (months of spending)", 0.0, 3.0, 0.0, 0.25, key="ov_oneoff")
    runs = get_portfolio_scenario_runways(repo, income_multiplier=income_level / 100,
                                          household_bill_change=bills / 100, one_off_spend_multiplier=one_off)
    base_runs = metrics["baseline_runway"]
    edges = [0, 1, 3, 6, 12, 24, 60, 120, np.inf]
    names = ["< 1", "1–3", "3–6", "6–12", "12–24", "24–60", "60–120", "120+"]
    base_counts = pd.cut(base_runs, edges, right=False, labels=names).value_counts().reindex(names)
    scen_counts = pd.cut(runs["runway_months"], edges, right=False, labels=names).value_counts().reindex(names)
    m = st.columns(4)
    for col, t in zip(m[:3], (3, 6, 12)):
        n, nb = int((runs["runway_months"] < t).sum()), int((base_runs < t).sum())
        col.metric(f"Under {t} months", f"{n:,}", f"{n - nb:+,} vs baseline", delta_color="inverse")
    m[3].metric("Median runway", f"{runs['runway_months'].median():.1f} mo", f"baseline {base_runs.median():.1f} mo",
                delta_color="off")
    charts.bar_chart(
        names,
        [{"name": "Baseline", "data": base_counts.fillna(0).astype(int).tolist(), "color": charts.GREY},
         {"name": "Your what-if", "data": scen_counts.fillna(0).astype(int).tolist(), "color": charts.ORANGE, "labels": True}],
        key="ov_whatif_hist", x_name="Runway (months)", y_name="Accounts", title="Runway distribution: baseline vs your what-if",
        subtitle="Months of runway (120+ = no monthly shortfall) · moves as you drag the sliders", height=360,
    )

    # ---------------------------------------------------------------- pre-loan association
    pre = get_preloan_early_warning_data(repo)
    q = pre["quartile_summary"]
    st.markdown("### Pre-loan buffer and supplied loan outcome")
    with st.expander(PRELOAN_BUFFER_LABEL, icon=":material/help:"):
        st.markdown(preloan_buffer_explainer(pre))
    a, b = st.columns([1.4, 1])
    with a:
        charts.bar_chart(
            [buffer_group_name(v) for v in q["buffer_quartile"]],
            [{"name": "Default rate", "data": (q["default_rate"] * (100 if q["default_rate"].max() <= 1 else 1)).round(1).tolist(),
              "color": charts.RED, "labels": True}],
            key="ov_preloan", x_name="Pre-loan buffer group (4 equal groups of loans)", y_name="Default rate (%)", title="Do loans default more when the savings cushion before the loan was small?", value_suffix="%",
            subtitle=(f"Loans split into 4 equal groups by buffer in the 6 months before the loan · {pre['cohort_size']} of "
                      f"{pre['eligible_loan_count']} loans had enough history"),
            height=320,
        )
    with b:
        od = pre["overdraft_summary"].set_index("had_pre_overdraft")
        if True in od.index and False in od.index:
            yes, no = od.loc[True], od.loc[False]
            _card(st, "Negative-balance day in the 6 months before the loan",
                  f"{int(yes['defaults'])} of {int(yes['loans'])} defaulted",
                  f"vs {int(no['defaults'])} of {int(no['loans'])} ({no['default_rate']:.1f}%) without one. Small group "
                  "(supplied flag includes running status D).", charts.RED)
        st.dataframe(q.assign(buffer_quartile=q["buffer_quartile"].map(buffer_group_name)).rename(columns={"buffer_quartile": "Pre-loan buffer", "loans": "Loans", "defaults": "Defaults",
                                       "default_rate": "Default rate", "median_buffer": "Median buffer"}),
                     hide_index=True, use_container_width=True,
                     column_config={"Default rate": st.column_config.NumberColumn(format="%.1f%%"),
                                    "Median buffer": st.column_config.NumberColumn(format="dollar")})
        st.caption("Unadjusted observational association; running C/D loans may still change. Not used to score anyone.")
