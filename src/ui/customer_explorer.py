"""
Screen 2: Customer case — the account's history, changes, peer position and model signal.
"""

from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import streamlit as st

from src.services.baseline_metrics import compute_official_baseline
from src.ui import charts
from src.ui.nav import new_click

OUT_PARTS = [("household_bills", "Household bills", charts.ORANGE), ("insurance", "Insurance", charts.YELLOW),
             ("loan_payments", "Loan payments", charts.RED), ("bank_fees", "Bank fees", "#B388EB"),
             ("cash_withdrawals_genuine", "Cash withdrawals", charts.BLUE), ("card_withdrawals", "Card withdrawals", charts.TEAL),
             ("transfers_out_other", "Other transfers out", charts.GREY)]
IN_PARTS = [("cash_deposits", "Cash deposits", charts.TEAL), ("transfers_in", "Transfers in", charts.BLUE),
            ("pension_in", "Pension", charts.YELLOW), ("interest_in", "Interest", charts.ORANGE_SOFT)]
FEATURE_LABELS = {
    "ROLL_6M_AVG_MONEY_IN": "6-mo average money in", "ROLL_6M_STD_MONEY_IN": "Money-in volatility (6 mo)",
    "ROLL_6M_AVG_MONEY_OUT": "6-mo average money out", "ROLL_6M_STD_MONEY_OUT": "Money-out volatility (6 mo)",
    "ROLL_6M_AVG_NET_FLOW": "6-mo average net cash flow", "ROLL_6M_STD_NET_FLOW": "Net-flow volatility (6 mo)",
    "ROLL_6M_BUFFER": "6-mo average balance", "ROLL_6M_MIN_BALANCE": "Lowest balance (6 mo)",
    "ROLL_6M_TOTAL_OVERDRAFT_DAYS": "Negative-balance days (6 mo)", "ROLL_6M_OVERDRAFT_MONTHS": "Months with negative days (6 mo)",
    "ROLL_3M_OVERDRAFT_MONTHS": "Months with negative days (3 mo)", "FIXED_COST_BURDEN_RATIO": "Fixed costs ÷ money in",
    "ROLL_6M_TOTAL_BANK_FEES": "Bank fees (6 mo)", "CURR_MONEY_IN": "This month's money in", "CURR_MONEY_OUT": "This month's money out",
    "CURR_NET_FLOW": "This month's net flow", "CURR_MONTH_END_BALANCE": "Month-end balance", "CURR_DAYS_BELOW_ZERO": "This month's negative days",
}


@st.cache_data(show_spinner=False)
def _quick_picks(metrics: pd.DataFrame, scores: Optional[pd.DataFrame]) -> Dict[str, int]:
    picks = {"Largest gap": int(metrics["gap"].idxmax()),
             "Lowest buffer": int(metrics["B"].idxmin()),
             "Typical": int((metrics["baseline_runway"] - metrics["baseline_runway"].median()).abs()
                                    .add((metrics["I"] - metrics["I"].median()).abs() / 1e4).idxmin())}
    if scores is not None and not scores.empty:
        picks = {"Top stress": int(scores["stress_probability"].idxmax()), **picks}
    return picks


def _decile_frame(metrics: pd.DataFrame) -> pd.Series:
    return pd.qcut(metrics["I"].rank(method="first"), 10, labels=[f"D{i}" for i in range(1, 11)])


def render_customer_explorer(repo: Any):
    metrics = repo.get_portfolio_account_metrics()
    accounts = repo.get_all_accounts()
    scores = getattr(repo, "stress_scores", None)
    current = st.session_state.get("active_account_id", accounts[0])
    if current not in accounts:
        current = accounts[0]

    st.markdown("## Customer case")
    pick_col, quick_col = st.columns([1, 2.2])
    with pick_col:
        st.session_state["case_picker"] = current
        st.selectbox("Open an account (type to search)", accounts, format_func=lambda v: f"Account #{v}", key="case_picker",
                     on_change=lambda: st.session_state.update(active_account_id=int(st.session_state["case_picker"])))
    with quick_col:
        st.caption("Jump to a case")
        picks = _quick_picks(metrics, scores)
        cols = st.columns(len(picks))
        for col, (label, acc) in zip(cols, picks.items()):
            if col.button(f"{label} · #{acc}", use_container_width=True, key=f"pick_{label}"):
                st.session_state["active_account_id"] = acc
                st.rerun()

    account_id = int(st.session_state["active_account_id"])
    meta = repo.get_account_meta(account_id) or {}
    monthly = repo.get_monthly_summary(account_id).sort_values("month").reset_index(drop=True)
    base = compute_official_baseline(account_id, monthly, meta)

    # ---------------------------------------------------------------- header
    prob = meta.get("ml_stress_probability")
    tier = meta.get("ml_risk_tier")
    tier_color = {"Priority outreach (top 2%)": charts.RED, "Watch (top 5%)": charts.YELLOW}.get(tier, charts.TEAL)
    shown = ">95%" if prob is not None and prob >= 0.95 else (f"{prob * 100:.1f}%" if prob is not None else None)
    record = repo.tier_track_record(tier) if hasattr(repo, "tier_track_record") else None
    badge = (f"<span class='rr-badge' style='color:{tier_color};border-color:{tier_color}'>MODEL ESTIMATE · {tier} · "
             f"{shown} chance of a negative-balance day in the next 3 months</span>"
             + (f"<div class='rr-hero-sub' style='margin:8px 0 0'>{record}</div>" if record else "")
             if prob is not None else "<span class='rr-badge'>Model estimate unavailable in local CSV mode</span>")
    loan_txt = (f"Loan status {meta.get('loan_status')} ({meta.get('loan_status_meaning')})" if meta.get("has_loan") else "No loan")
    st.markdown(
        f"""<div class="rr-hero"><div class="rr-hero-title">Account #{account_id}</div>
        <div class="rr-hero-sub">Opened {meta.get('account_opened', '–')} · branch {meta.get('branch_district_name', '–')}
        ({meta.get('branch_region', '–')}) · {meta.get('frequency', '–')} · card: {meta.get('card_type', 'No Card')} ·
        authorized users: {meta.get('authorized_user_count', 0)} · {loan_txt} · {base.history_months} monthly records</div>
        {badge}</div>""",
        unsafe_allow_html=True,
    )

    k = st.columns(4)
    k[0].metric("Money in (I)", f"${base.I:,.2f}", help="Median monthly money_in.")
    k[1].metric("Spending (S)", f"${base.S:,.2f}", help="Median monthly money_out.")
    k[2].metric("Fixed costs (F)", f"${base.F:,.2f}", help="Median of household bills + insurance + loan payments.")
    k[3].metric("Household bills (H)", f"${base.H:,.2f}", help="Median monthly household_bills.")
    k = st.columns(4)
    k[0].metric("Buffer (B)", f"${base.B:,.2f}", help="Mean avg_daily_balance, latest six rows.")
    k[1].metric("Loan payment (P)", f"${base.P:,.2f}", help="Only for loans with status C or D.")
    k[2].metric("Monthly gap (S − I)", charts.signed_money(base.gap).lstrip("+").replace("-", "−"),
                charts.signed_money(base.gap) + (" shortfall" if base.gap > 0 else " surplus"), delta_color="inverse")
    k[3].metric("Baseline runway", base.baseline_runway_label)

    g1, g2, g3 = st.columns([1, 1, 2])
    with g1:
        charts.gauge_chart(base.baseline_runway, key=f"g_run_{account_id}", title="Baseline runway",
                           display="120+ mo" if base.baseline_runway >= 120 else None)
    with g2:
        if prob is not None:
            charts.gauge_chart(min(prob, 0.95) * 100, key=f"g_ml_{account_id}", title="Stress estimate", max_value=100, suffix="%",
                               display=">95%" if prob >= 0.95 else None,
                               bands=((5, charts.TEAL), (20, charts.YELLOW), (100, charts.RED)))
        else:
            st.info("Stress estimate needs the Snowflake connection.")
    with g3:
        drivers = meta.get("ml_top_drivers") or []
        if drivers:
            charts.bar_chart([FEATURE_LABELS.get(d["feature"], d["feature"]) for d in drivers][::-1],
                             [{"name": "Push toward stress (model contribution)",
                               "data": [d["contribution"] for d in drivers][::-1], "color": charts.RED, "labels": True}],
                             key=f"drv_{account_id}", x_name="Model signal", y_name="Contribution to the estimate (log-odds)", horizontal=True, height=230,
                             title=f"What pushes this estimate up (as of {meta.get('ml_as_of_month')})",
                             subtitle="XGBoost contributions in log-odds · association, not cause")
        elif prob is not None:
            st.success("No feature pushes this account's estimate above the portfolio baseline.")

    # ---------------------------------------------------------------- tabs
    t_hist, t_mix, t_change, t_future, t_peer, t_ledger, t_loans = st.tabs(
        ["Cash-flow history", "Where money goes", "What changed", "Where it's heading", "Peers", "Transactions", "Loans & orders"])

    anomalies = repo.account_anomalies(account_id) if hasattr(repo, "account_anomalies") else pd.DataFrame()
    flagged = anomalies[anomalies["story"].notna()] if not anomalies.empty else anomalies
    pins = {"MONEY_IN": [], "MONEY_OUT": []}
    for r in flagged.itertuples():
        pins[r.measure].append({"coord": [r.month, round(float(r.observed), 2)], "value": "↓" if r.measure == "MONEY_IN" else "↑",
                                "itemStyle": {"color": charts.YELLOW}})

    with t_hist:
        neg_months = monthly.loc[monthly["days_below_zero"] > 0, "month"].tolist()
        areas = [[{"xAxis": m, "itemStyle": {"color": "rgba(239,71,111,0.16)"}}, {"xAxis": m}] for m in neg_months]
        charts.line_chart(
            monthly["month"].tolist(),
            [{"name": "Money in", "data": monthly["money_in"].round(2).tolist(), "color": charts.TEAL, "points": pins["MONEY_IN"]},
             {"name": "Money out", "data": monthly["money_out"].round(2).tolist(), "color": charts.RED, "points": pins["MONEY_OUT"]},
             {"name": "Average daily balance", "data": monthly["avg_daily_balance"].round(2).tolist(), "color": charts.BLUE,
              "area": True, "axis": 1, "width": 1.5}],
            key=f"hist_{account_id}", x_name="Month", y_name="Money in / out per month ($)", title="Monthly money in, money out and balance",
            subtitle="Red bands = negative-balance months · yellow pins = unusual 2025 months (Snowflake ML anomaly detection)",
            right_axis={"name": "Average daily balance ($)", "money": True},
            mark_lines=[charts.mark_line(base.I, f"I ${base.I:,.0f}", charts.TEAL),
                        charts.mark_line(base.S, f"S ${base.S:,.0f}", charts.RED)],
            mark_areas=areas, height=430,
        )
        net = (monthly["money_in"] - monthly["money_out"]).round(2)
        charts.line_chart(
            monthly["month"].tolist(),
            [{"name": "Net cash flow", "data": [{"value": v, "itemStyle": {"color": charts.TEAL if v >= 0 else charts.RED}}
                                               for v in net], "bar": True}],
            key=f"net_{account_id}", x_name="Month", y_name="Net cash flow ($)", title="Net cash flow by month", height=280,
            mark_lines=[charts.mark_line(0, "0", charts.GREY)],
        )

    with t_mix:
        st.caption("Click a month's bar to list that month's transactions below.")
        event = charts.bar_chart(
            monthly["month"].tolist(),
            [{"name": label, "data": monthly[col].round(2).tolist(), "color": color} for col, label, color in OUT_PARTS],
            key=f"mix_out_{account_id}", x_name="Month", y_name="Money out ($)", stacked=True, money=True, height=400, clickable=True,
            title="Money out by category", subtitle="Categories add up to money_out · toggle categories in the legend",
        )
        clicked = new_click(event, f"mix_out_{account_id}")
        if clicked and clicked.get("name"):
            st.session_state[f"month_focus_{account_id}"] = clicked["name"]
        c1, c2 = st.columns(2)
        with c1:
            last6 = monthly.tail(6)
            charts.donut_chart([{"name": label, "value": last6[col].sum(), "color": color}
                                for col, label, color in OUT_PARTS if last6[col].sum() > 0],
                               key=f"donut_out_{account_id}", title="Money out, latest 6 months")
        with c2:
            charts.bar_chart(
                monthly["month"].tolist(),
                [{"name": label, "data": monthly[col].round(2).tolist(), "color": color} for col, label, color in IN_PARTS],
                key=f"mix_in_{account_id}", x_name="Month", y_name="Money in ($)", stacked=True, money=True, height=300, title="Money in by source",
            )
        focus = st.session_state.get(f"month_focus_{account_id}")
        if focus:
            tx = repo.get_transactions(account_id)
            tx_m = tx[tx["date"].astype(str).str.startswith(focus)]
            st.markdown(f"**Transactions in {focus}** · {len(tx_m)} rows")
            st.dataframe(tx_m[["date", "direction", "operation", "purpose", "amount", "balance"]],
                         hide_index=True, use_container_width=True, height=260)

    with t_change:
        st.markdown("**Unusual months in 2025 · Snowflake ML anomaly detection (MODEL ESTIMATE)**")
        if anomalies.empty:
            st.caption("Not scored: anomaly detection needs at least 12 months of history before 2025.")
        elif flagged.empty:
            st.success("No 2025 month fell far outside this account's own usual pattern.")
        else:
            st.dataframe(flagged.assign(
                **{"What happened": flagged["story"], "Observed": flagged["observed"], "Expected for this account": flagged["expected"],
                   "Expected range": flagged.apply(lambda r: f"${r.lower_bound:,.0f} – ${r.upper_bound:,.0f}", axis=1)})
                [["month", "What happened", "Observed", "Expected for this account", "Expected range"]],
                hide_index=True, use_container_width=True,
                column_config={"Observed": st.column_config.NumberColumn(format="dollar"),
                               "Expected for this account": st.column_config.NumberColumn(format="dollar")})
            st.caption("Trained on this account's own months up to Dec 2024; a month is flagged when it falls outside the "
                       "model's 99.8% range and at least $500 and 25% away from what was expected. Unusual is not the same as bad, "
                       "and it does not say why.")
        if len(monthly) >= 12:
            recent, prior = monthly.tail(6), monthly.iloc[-12:-6]
            rows = [("Money in", "money_in"), ("Money out", "money_out"), ("Household bills", "household_bills"),
                    ("Loan payments", "loan_payments"), ("Cash withdrawals", "cash_withdrawals_genuine"),
                    ("Card withdrawals", "card_withdrawals"), ("Avg daily balance", "avg_daily_balance")]
            labels, changes, table = [], [], []
            for label, col in rows:
                a, b = prior[col].median(), recent[col].median()
                pct = (b - a) / abs(a) * 100 if abs(a) > 1e-9 else (0.0 if abs(b) < 1e-9 else np.nan)
                table.append({"Measure": label, "Prior 6 mo median": a, "Latest 6 mo median": b, "Change": b - a,
                              "Change %": pct})
                if not np.isnan(pct):
                    labels.append(label)
                    changes.append(round(float(np.clip(pct, -300, 300)), 1))
            charts.bar_chart(labels[::-1], [{"name": "Change in median", "data": [
                {"value": v, "itemStyle": {"color": charts.TEAL if v >= 0 else charts.RED}} for v in changes[::-1]],
                "labels": True}], key=f"chg_{account_id}", x_name="Measure", y_name="Change in monthly median (%)", horizontal=True, value_suffix="%", height=340,
                title=f"Latest 6 months ({recent['month'].iloc[0]}–{recent['month'].iloc[-1]}) vs the 6 before",
                subtitle="OBSERVED change in monthly medians · capped at ±300% for display")
            st.dataframe(pd.DataFrame(table).style.format({"Prior 6 mo median": "${:,.2f}", "Latest 6 mo median": "${:,.2f}",
                                                          "Change": charts.signed_money, "Change %": "{:+.1f}%"},
                                                         na_rep="n/a"),
                         hide_index=True, use_container_width=True)
        else:
            st.info("Fewer than 12 monthly records, so a 6-vs-6 comparison is not available.")

    with t_future:
        render_forecast_tab(repo, account_id, monthly, base)

    with t_peer:
        decile = _decile_frame(metrics)
        my_decile = decile.loc[account_id]
        peers = metrics[decile == my_decile]
        measures = [("Money in (I)", "I"), ("Spending (S)", "S"), ("Fixed costs (F)", "F"), ("Buffer (B)", "B")]
        charts.bar_chart([m[0] for m in measures],
                         [{"name": f"Account #{account_id}", "data": [round(float(metrics.at[account_id, c]), 2) for _, c in measures],
                           "color": charts.ORANGE},
                          {"name": f"{my_decile} median ({len(peers)} accounts)", "data": [round(float(peers[c].median()), 2) for _, c in measures],
                           "color": charts.GREY}],
                         key=f"peer_{account_id}", x_name="Measure", y_name="Monthly amount ($)", money=True, height=340,
                         title=f"Account vs its income decile ({my_decile})", subtitle="Decile of median money-in across 4,500 accounts")
        pct_rank = (peers["B"] < metrics.at[account_id, "B"]).mean() * 100
        st.caption(f"Buffer is higher than {pct_rank:.0f}% of {my_decile} accounts. "
                   f"{int((peers['gap'] > 0).sum())} of {len(peers)} accounts in this decile spend more than they bring in.")

    with t_ledger:
        tx = repo.get_transactions(account_id)
        if tx.empty:
            st.info("No transactions recorded.")
        else:
            daily = tx.groupby("date")["balance"].last().reset_index()
            charts.line_chart(daily["date"].astype(str).tolist(),
                              [{"name": "Balance after last transaction of the day", "data": daily["balance"].round(2).tolist(),
                                "color": charts.BLUE, "area": True, "step": True}],
                              key=f"bal_{account_id}", x_name="Date", y_name="Balance ($)", title="Transaction-level balance", height=400,
                              mark_lines=[charts.mark_line(0, "$0", charts.RED)],
                              subtitle="Within-day order is not reliable in the source, so the day's last listed balance is used")
            ops = st.multiselect("Filter by operation", sorted(tx["operation"].dropna().unique()), key=f"ops_{account_id}")
            view = tx[tx["operation"].isin(ops)] if ops else tx
            st.dataframe(view.sort_values("date", ascending=False)[["date", "direction", "operation", "purpose", "amount",
                                                                    "balance", "partner_bank"]],
                         hide_index=True, use_container_width=True, height=320)

    with t_loans:
        if meta.get("has_loan"):
            c = st.columns(4)
            c[0].metric("Loan amount", f"${meta.get('loan_amount', 0):,.2f}")
            c[1].metric("Monthly payment", f"${meta.get('loan_monthly_payment', 0):,.2f}")
            c[2].metric("Term", f"{meta.get('loan_duration_months', 0)} months")
            c[3].metric("Status", f"{meta.get('loan_status')}")
            st.caption(f"{meta.get('loan_status_meaning')}. The supplied status is used for P only; it is never a model input.")
        else:
            st.info("No loan on record.")
        orders = repo.standing_orders[repo.standing_orders["account_id"] == account_id]
        st.markdown(f"**Standing orders:** {len(orders)} (undated snapshot, frequency not recorded — not assumed monthly)")
        if not orders.empty:
            st.dataframe(orders[["to_bank", "to_account", "amount", "purpose"]], hide_index=True, use_container_width=True)


def render_forecast_tab(repo: Any, account_id: int, monthly: pd.DataFrame, base) -> None:
    bt = getattr(repo, "forecast_backtest", None)
    fc = repo.account_forecast(account_id) if hasattr(repo, "account_forecast") else pd.DataFrame()
    if bt is None or bt.empty:
        st.info("The balance forecast is not available (needs the Snowflake ML forecast tables).")
        return
    mae_f, mae_n, mae_g = bt["mae_forecast"].mean(), bt["mae_naive"].mean(), bt["mae_constant_gap"].mean()
    if not repo.forecast_validated:
        st.warning(f"Snowflake ML balance forecast not shown: in the Jan–Jun 2025 backtest ({int(bt['accounts'].iloc[0]):,} "
                   f"accounts) it did not beat simply holding the balance flat (average error ${mae_f:,.0f} vs ${mae_n:,.0f}), "
                   f"and its 80% range held the actual value only {bt['interval_80_coverage'].mean() * 100:.0f}% of the time.")
        g6, n6 = float(bt["mae_constant_gap"].iloc[-1]), float(bt["mae_naive"].iloc[-1])
        st.info(f"What the backtest did show: the challenge's straight-line assumption (buffer − monthly gap × months) "
                f"misses by ${g6:,.0f} on average at 6 months, versus ${n6:,.0f} for a flat balance. Balances here do not "
                "run down in a straight line, so treat the official runway as a stress test, not a countdown.")
        return
    if fc.empty:
        st.info("This account has under 12 months of history or ended before Dec 2025, so it was not forecast.")
        return
    hist = monthly.tail(18)
    months = hist["month"].tolist() + fc["month"].tolist()
    n_hist, n_fc = len(hist), len(fc)
    last = float(hist["avg_daily_balance"].iloc[-1])
    actual = hist["avg_daily_balance"].tolist() + [None] * n_fc
    forecast = [None] * (n_hist - 1) + [last] + fc["forecast"].tolist()
    lower = [None] * (n_hist - 1) + [last] + fc["lower_bound"].tolist()
    upper = [None] * (n_hist - 1) + [last] + fc["upper_bound"].tolist()
    convention = [None] * (n_hist - 1) + [round(base.B, 2)] + [round(base.B - base.gap * h, 2) for h in range(1, n_fc + 1)]
    charts.band_chart(months, actual, forecast, lower, upper, key=f"fc_{account_id}", split_label=hist["month"].iloc[-1],
                      title="Average daily balance: observed and projected", height=400,
                      subtitle="Snowflake ML FORECAST, 80% range · dotted = challenge convention (B − gap × months)",
                      extra=[{"name": "Challenge convention", "data": convention, "color": charts.ORANGE}])
    end = fc.iloc[-1]
    c = st.columns(3)
    c[0].metric(f"Projected balance {end['month']}", f"${end['forecast']:,.2f}", "MODEL ESTIMATE", delta_color="off")
    c[1].metric("80% range", f"${end['lower_bound']:,.0f} – ${end['upper_bound']:,.0f}")
    c[2].metric("Challenge convention at 6 months", f"${base.B - base.gap * 6:,.2f}")
    st.caption(f"Backtest (train to Dec 2024, predict Jan–Jun 2025 for {int(bt['accounts'].iloc[0]):,} accounts): average error "
               f"${mae_f:,.0f} vs ${mae_n:,.0f} for a flat balance and ${mae_g:,.0f} for buffer − gap × months; the 80% range "
               f"contained the actual value {bt['interval_80_coverage'].mean() * 100:.0f}% of the time. A projection, not a prediction "
               "of any individual's future; the official runway is unchanged.")
