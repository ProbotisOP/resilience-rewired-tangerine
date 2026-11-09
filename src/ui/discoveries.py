"""Screen 5: Reproducible, denominator-explicit portfolio observations."""

from html import escape

import streamlit as st

from src.data.local_repository import LocalDataRepository
from src.ui import charts
from src.ui.presentation import (MONEY_IN_GROUP_NOTE, PRELOAN_BUFFER_LABEL, buffer_group_name, money_in_group_name,
                                 money_in_group_range_text, money_in_group_ranges, money_in_group_tick,
                                 money_in_ranges_caption, preloan_buffer_explainer,
                                 score_group_name)
from src.services.discovery_engine import (
    get_behavioral_association_tables,
    get_income_decile_discovery,
    get_preloan_early_warning_data,
)


def render_discoveries(repo: LocalDataRepository):
    st.markdown("## 🔎 What the data shows")
    st.caption(
        "Patterns in this dataset can raise useful questions. They do not prove causes "
        "or predict what will happen to an individual account."
    )

    tab0, tab1, tab2, tab3, tab4 = st.tabs(
        [
            "🧠 Models in plain language",
            "Before a loan",
            "Money-in what-if",
            "Group comparisons",
            "Models & validation",
        ]
    )

    with tab0:
        render_models_plain(repo)

    with tab1:
        pre_data = get_preloan_early_warning_data(repo)
        st.subheader("Buffer before a loan and the recorded outcome")
        st.markdown(
            f"The eligible cohort contains **{pre_data['cohort_size']:,} of "
            f"{pre_data.get('eligible_loan_count', 0):,} loans**, each with six available "
            f"monthly records before the loan-start month. Records span "
            f"{pre_data.get('window_start', 'not available')} to "
            f"{pre_data.get('window_end', 'not available')}; the exact six-month window varies by loan."
        )
        st.markdown(
            "### The story in plain language\n"
            "Among loans with enough earlier account history, compare the recorded outcome "
            "rates for the lowest and highest pre-loan buffer groups. This can motivate a "
            "customer-controlled resilience conversation—but it is not evidence that a buffer "
            "causes a loan outcome or a basis for an automated credit decision."
        )
        st.warning(
            "This is an association with the supplied default flag (B or D). Running loans "
            "are not completed outcomes; the analysis does not show that low buffers cause default."
        )
        with st.expander(PRELOAN_BUFFER_LABEL, icon=":material/help:"):
            st.markdown(preloan_buffer_explainer(pre_data))

        q_df = pre_data["quartile_summary"]
        if not q_df.empty:
            lowest_buffer = q_df.loc[
                q_df["buffer_quartile"] == "Q1 (Lowest Buffer)"
            ]
            highest_buffer = q_df.loc[
                q_df["buffer_quartile"] == "Q4 (Highest Buffer)"
            ]
            if not lowest_buffer.empty and not highest_buffer.empty:
                q1, q4 = lowest_buffer.iloc[0], highest_buffer.iloc[0]
                rate_cols = st.columns(2)
                rate_cols[0].metric(
                    "Lowest-buffer group · recorded default flag",
                    f"{q1['default_rate']:.1f}%",
                    f"{int(q1['defaults'])} of {int(q1['loans'])} loans",
                )
                rate_cols[1].metric(
                    "Highest-buffer group · recorded default flag",
                    f"{q4['default_rate']:.1f}%",
                    f"{int(q4['defaults'])} of {int(q4['loans'])} loans",
                )
            left, right = st.columns(2)
            with left:
                st.markdown("**Recorded default rate by pre-loan buffer group**")
                st.caption("Loans split into 4 equal groups by the account's buffer in the 6 months before the loan.")
                charts.bar_chart(
                    [buffer_group_name(v) for v in q_df["buffer_quartile"]],
                    [{"name": "Recorded default rate", "data": q_df["default_rate"].round(1).tolist(),
                      "color": charts.RED, "labels": True},
                     {"name": "Median pre-loan buffer", "data": q_df["median_buffer"].round(2).tolist(),
                      "color": charts.TEAL, "line": True, "axis": 1, "axis_name": "Median pre-loan buffer ($)", "money": True}],
                    key="disc_preloan_q", x_name="Pre-loan buffer group (4 equal groups of loans)",
                    y_name="Default rate (%)", value_suffix="%", height=340,
                    subtitle="Bars = default rate · line = median pre-loan buffer (right axis)",
                )
            with right:
                display_quartiles = q_df.assign(buffer_quartile=q_df["buffer_quartile"].map(buffer_group_name)).rename(
                    columns={
                        "buffer_quartile": "Pre-loan buffer group",
                        "loans": "Loans in group",
                        "defaults": "Recorded defaults (B/D)",
                        "default_rate": "Recorded default rate",
                        "median_buffer": "Median pre-loan buffer",
                    }
                )
                st.dataframe(
                    display_quartiles.style.format(
                        {
                            "Recorded default rate": "{:.1f}%",
                            "Median pre-loan buffer": "${:,.2f}",
                        }
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

        od_df = pre_data["overdraft_summary"]
        if not od_df.empty:
            od_df = od_df.copy()
            od_df["Negative-balance days before loan"] = od_df["had_pre_overdraft"].map(
                {True: "At least one month", False: "None recorded"}
            )
            display_overdraft = od_df.rename(
                columns={
                    "loans": "Loans in group",
                    "defaults": "Recorded defaults (B/D)",
                    "default_rate": "Recorded default rate",
                }
            )
            st.markdown("**Separate comparison: months with below-zero days in the same pre-loan window**")
            st.dataframe(
                display_overdraft[
                    [
                        "Negative-balance days before loan",
                        "Loans in group",
                        "Recorded defaults (B/D)",
                        "Recorded default rate",
                    ]
                ].style.format({"Recorded default rate": "{:.1f}%"}),
                use_container_width=True,
                hide_index=True,
            )
        st.caption(
            "Denominators are loans in each displayed group. The six records are the latest "
            "available monthly rows before loan start; month continuity is not independently asserted."
        )

    with tab2:
        ranges = money_in_group_ranges(repo.get_portfolio_account_metrics()["I"])
        deciles = get_income_decile_discovery(repo)
        codes = deciles["Income Decile"].astype(str).tolist()
        deciles = deciles.assign(**{"Income Decile": [money_in_group_name(c) for c in codes],
                                    "Money-in range": [money_in_group_range_text(c, ranges) for c in codes]}).rename(
            columns={
                "Income Decile": "Money-in Group",
                "Median Income": "Median Money-in",
                "Median Runway (EI 55%)": "Median Runway (55% money-in)",
            }
        )
        st.subheader("Runway in a 55% money-in what-if")
        st.markdown(
            f"{MONEY_IN_GROUP_NOTE} (450 accounts each). "
            "For each account, the runway formula is recalculated with money in set to 55% of its "
            "usual level; this is a simulation, not observed layoff data."
        )
        if not deciles.empty:
            bottom, top = deciles.iloc[0], deciles.iloc[-1]
            st.markdown(
                "### The story in plain language\n"
                "The same simulated money-in change does not produce the same runway across "
                "groups. Recorded buffers and spending also differ, so money-in alone does not "
                "explain the result."
            )
            story_cols = st.columns(2)
            story_cols[0].metric(
                f"{bottom['Money-in Group']} money-in ({bottom['Money-in range']}) · median simulated runway",
                f"{bottom['Median Runway (55% money-in)']:.1f} months",
                f"{int(bottom['Accounts Below 6 Months'])} of {int(bottom['Accounts'])} below 6 months",
            )
            story_cols[1].metric(
                f"{top['Money-in Group']} money-in ({top['Money-in range']}) · median simulated runway",
                f"{top['Median Runway (55% money-in)']:.1f} months",
                f"{int(top['Accounts Below 6 Months'])} of {int(top['Accounts'])} below 6 months",
            )
            st.info(
                "Business idea to test: use this kind of transparent, customer-selected "
                "stress conversation to explore buffer and spending context—not to score, "
                "approve or price credit. This dataset does not measure customer uptake or "
                "business impact."
            )
            if st.button(
                "Try a what-if with an account",
                key="discovery_try_whatif",
                type="primary",
            ):
                st.query_params["page"] = "what-if"
                st.rerun()
        charts.bar_chart(
            [money_in_group_tick(c) for c in codes],
            [{"name": "% below 6 months", "data": deciles["% Below 6 Months"].round(1).tolist(), "color": charts.ORANGE,
              "labels": True},
             {"name": "Median runway (months)", "data": deciles["Median Runway (55% money-in)"].round(1).tolist(),
              "color": charts.TEAL, "line": True, "axis": 1, "axis_name": "months", "suffix": " mo"}],
            key="disc_deciles", x_name="Money-in group (lowest → highest)", y_name="Share of group under 6 months (%)", value_suffix="%", height=380,
            title="If money in drops to 55%, which money-in groups fall under 6 months?",
            subtitle="Lowest money in on the left, highest on the right · bars = share under 6 months · line = median runway",
        )
        st.caption(money_in_ranges_caption(ranges))
        st.dataframe(
            deciles[["Money-in Group", "Money-in range"] + [c for c in deciles.columns
                                                           if c not in ("Money-in Group", "Money-in range")]].style.format(
                {
                    "Median Money-in": "${:,.2f}",
                    "Median Runway (55% money-in)": "{:.1f}",
                    "% Below 6 Months": "{:.1f}%",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"Denominator: {int(deciles['Accounts'].sum()):,} accounts, "
            f"{int(deciles['Accounts'].iloc[0]):,} in each money-in group. Account history spans "
            "available monthly records in 2020–2025; money-in is not verified employment income. "
            "Runway threshold counts use one-decimal official values."
        )
        with st.expander("🧾 How this chart is calculated"):
            st.markdown(
                """
                1. Calculate each account's median monthly money in.
                2. Split the accounts into ten equal-sized groups, ordered from lowest to highest median money in
                   ("Bottom 10%" is the lowest-money-in group, "Top 10%" the highest).
                3. For each account, multiply its median money in by **55%**; leave its typical spending and buffer unchanged.
                4. Recalculate the challenge runway, round it to one decimal, and count accounts below six months.
                5. Divide that count by the accounts in the group to get the displayed percentage.

                This is a fixed scenario applied to recorded money in—not a measured job-loss or benefit outcome.
                """
            )

    with tab3:
        st.subheader("How account groups compare")
        st.markdown(
            "The tables report raw group denominators and outcomes from accounts, dispositions, "
            "cards, loans, monthly summaries and standing orders. Account-history measures use "
            "each account's available monthly rows (2020–2025); the standing-order file is an "
            "undated snapshot."
        )
        st.caption(
            "For grouped tables, negative-balance account rates are accounts with at least one "
            "recorded month containing below-zero days divided by accounts in that group. "
            "Loan-default rates are recorded B/D loans divided by supplied loans in that group; "
            "running C/D loans are not completed outcomes. Sample sizes are shown in each table."
        )
        tables = get_behavioral_association_tables(repo)
        group_rows = []
        for key, flag, label in (("authorized_user", "has_authorized_user", "Authorized user listed"),
                                 ("card", "has_card", "Owner card recorded"),
                                 ("leasing_order", "has_leasing_order", "Leasing-labelled order")):
            t = tables[key].set_index(flag)
            for value in (True, False):
                if value in t.index:
                    group_rows.append((f"{label}: {'yes' if value else 'no'} ({int(t.loc[value, 'accounts']):,})",
                                       round(float(t.loc[value, "negative_balance_account_rate_pct"]), 1)))
        freq = tables["statement_frequency"]
        for _, r in freq.iterrows():
            group_rows.append((f"{r['frequency']} ({int(r['accounts']):,})", round(float(r["negative_balance_account_rate_pct"]), 1)))
        charts.bar_chart([g[0] for g in group_rows][::-1],
                         [{"name": "% of accounts with any below-zero month", "data": [g[1] for g in group_rows][::-1],
                           "color": charts.ORANGE, "labels": True}],
                         key="disc_groups", x_name="Account group", y_name="Accounts with a below-zero month (%)", horizontal=True, value_suffix="%", height=420,
                         title="Share of accounts with at least one negative-balance month, by group",
                         subtitle="Group size in brackets · descriptive and unadjusted, not causal")

        title_by_key = {
            "authorized_user": "Authorized-user account association (not a spouse/partner label)",
            "statement_frequency": "Statement frequency: negative-balance association and loan outcomes shown separately",
            "card": "Card on owner disposition: loan outcome association",
            "cash_deposit_reliance": "Cash Deposit Reliance among loan accounts",
            "leasing_order": "Leasing-labelled standing order vs. negative-balance days",
        }
        for key in ("authorized_user", "statement_frequency", "card"):
            table = tables[key].copy()
            if key == "authorized_user":
                table = table.rename(columns={"has_authorized_user": "authorized_user_listed"})
            elif key == "card":
                table = table.rename(columns={"has_card": "owner_card_recorded"})
            table = table.rename(
                columns={
                    "accounts": "Accounts in group",
                    "accounts_with_negative_balance_days": "Accounts with a below-zero month",
                    "loans": "Loans in data",
                    "defaults": "Recorded defaults (B/D)",
                    "negative_balance_account_rate_pct": "% with below-zero month",
                    "loan_default_rate_pct": "% recorded defaults",
                }
            )
            st.markdown(f"**{title_by_key[key]}**")
            st.dataframe(
                table.style.format(
                    {
                        "% with below-zero month": "{:.1f}%",
                        "% recorded defaults": "{:.1f}%",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

        cash = tables["cash_deposit_reliance"].copy()
        cash = cash.rename(
            columns={
                "cash_deposit_reliance_quartile": "Cash-deposit share group",
                "loans": "Loans in group",
                "defaults": "Recorded defaults (B/D)",
                "median_cash_deposit_share": "Median cash-deposit share",
                "default_rate_pct": "Recorded default rate",
            }
        )
        st.markdown(f"**{title_by_key['cash_deposit_reliance']}**")
        st.dataframe(
            cash.style.format(
                {
                    "Median cash-deposit share": "{:.1%}",
                    "Recorded default rate": "{:.1f}%",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )

        lease = tables["leasing_order"].rename(
            columns={
                "has_leasing_order": "Leasing label in snapshot",
                "accounts": "Accounts in group",
                "accounts_with_negative_balance_days": "Accounts with a below-zero month",
                "loans": "Loans in data",
                "defaults": "Recorded defaults (B/D)",
                "negative_balance_account_rate_pct": "% with below-zero month",
                "loan_default_rate_pct": "% recorded defaults",
            }
        )
        st.markdown(f"**{title_by_key['leasing_order']}**")
        st.dataframe(
            lease.style.format({"% with below-zero month": "{:.1f}%"}),
            use_container_width=True,
            hide_index=True,
        )

        external = tables["external_destination_instructions"].iloc[0]
        st.markdown("**External-destination loan-payment instructions**")
        st.write(
            f"{int(external['standing_order_rows']):,} standing-order rows are labelled "
            f"loan payment, affecting {int(external['accounts_with_instruction']):,} accounts; "
            f"{int(external['accounts_without_internal_loan']):,} such accounts have no loan "
            "record in this dataset. These are instructions to external destinations, not "
            "confirmation of outstanding external debt."
        )
        st.caption(
            "Loan denominators include all supplied loan records; B and D contribute to the "
            "defaulted flag, and C/D loans may still be running. Group differences are descriptive, "
            "unadjusted and non-causal."
        )

        with st.expander("Claims removed from the judging narrative"):
            st.markdown(
                "- **Spousal Shield** is replaced by **Authorized-User Account Association**; "
                "the relationship type does not establish a spouse or partnership.\n"
                "- **Statement Canary** separates negative-balance association from loan outcomes.\n"
                "- **Inverted Resilience** is explicitly a simulated shock result.\n"
                "- **Cardholder Immunity** is a descriptive association, not a protective effect.\n"
                "- **Cash Addiction** is renamed **Cash Deposit Reliance**; cash inflows do not establish income quality.\n"
                "- Leasing orders are not confirmed contracts or monthly obligations; external loan-payment instructions "
                "do not prove external debt.\n"
                "- Penalty fees are not claimed to cause or precede default without verified sequencing.\n"
                "- The 48–72-hour payday assertion is removed; no account-level date-sequence analysis supports it.\n"
                "- Cash withdrawals are not classified as discretionary."
            )

    with tab4:
        render_model_evidence(repo)


MODEL_NAMES = {
    "Majority Class Baseline": "Guess the average (no model)",
    "Rule-Based Heuristic": "Simple rule",
    "Logistic Regression (calibrated)": "Logistic regression (statistics)",
    "XGBoost (calibrated)": "XGBoost (machine learning)",
}


def _qa(question: str, answer_html: str) -> None:
    """Question-led header with a computed one-line answer (same look as the Recovery plan page)."""
    st.markdown(f"<div class='rr-qtitle'>{escape(question)}</div>"
                f"<div class='rr-answer'><b>Answer:</b> {answer_html}</div>", unsafe_allow_html=True)


def _d(v: float, digits: int = 0) -> str:
    """Dollar text for HTML/markdown that Streamlit will not read as LaTeX."""
    return f"&#36;{v:,.{digits}f}"


def _model_rows(repo):
    m = getattr(repo, "model_metrics", None)
    if m is None or m.empty:
        return None
    m = m.copy()
    m.columns = [c.upper() for c in m.columns]
    rows = {r["MODEL_NAME"]: r for _, r in m.iterrows()}
    return m, rows.get("XGBoost (calibrated)"), rows.get("Rule-Based Heuristic"), \
        rows.get("Logistic Regression (calibrated)"), rows.get("Majority Class Baseline")


def _method_card(icon: str, title: str, kind: str, status: str, what: str, how: str, tells: str, cannot: str,
                 where: str) -> None:
    with st.container(border=True):
        st.markdown(f"<div class='rr-q'>{escape(kind)} · {escape(status)}</div>"
                    f"<div class='rr-qtitle'>{icon} {escape(title)}</div>", unsafe_allow_html=True)
        c = st.columns(2)
        c[0].markdown(f"**What it is**  \n{what}")
        c[0].markdown(f"**How we built it**  \n{how}")
        c[1].markdown(f"**What it tells you**  \n{tells}")
        c[1].markdown(f"**What it can't tell you**  \n{cannot}")
        st.caption(f"Where you see it: {where}")


def render_models_plain(repo):
    st.subheader("What methods sit behind this app, in plain language")
    st.markdown(
        "The app uses three kinds of method. **Calculations** are exact arithmetic on the customer's own records "
        "(labelled CALCULATED). **Statistics** describe groups of customers and how often something happened "
        "(OBSERVED). **Machine learning (ML)** learns patterns from past months and gives an estimate for the future "
        "(MODEL ESTIMATE). Every ML model was tested on months it never saw, and one that failed the test is not shown."
    )

    parts = _model_rows(repo)
    xg = rule = lr = None
    if parts:
        _, xg, rule, lr, _ = parts
    an = getattr(repo, "anomalies", None)
    bt = getattr(repo, "forecast_backtest", None)
    drivers = getattr(repo, "vulnerability_drivers", None)

    summary = [
        ("Runway calculation", "Calculation", "How many months can the savings cover the monthly shortfall?", "Used everywhere"),
        ("Group comparisons", "Statistics", "Do some customer groups run into trouble more often?", "Evidence tabs"),
        ("Stress model (XGBoost)", "Machine learning", "Who is likely to hit a negative balance in the next 3 months?", "Used"),
        ("Unusual-month detection", "Machine learning (Snowflake ML)", "Which months were unusual for this customer?", "Used"),
        ("Balance forecast", "Machine learning (Snowflake ML)", "Where is the balance heading?",
         "Tested, failed, hidden" if bt is not None and not bt.empty and not getattr(repo, "forecast_validated", False) else "Tested"),
        ("Top Insights", "Machine learning (Snowflake ML)", "Which segments explain the jump in at-risk accounts?", "Used"),
        ("TANG / Cortex AI", "Generative AI", "Can you explain this in words?", "Used, numbers checked"),
    ]
    st.dataframe([{"Method": a, "Type": b, "Business question it answers": c, "Status": d} for a, b, c, d in summary],
                 hide_index=True, use_container_width=True)

    _method_card(
        "🧮", "Runway calculation", "Calculation", "Used everywhere",
        "Simple arithmetic: **buffer ÷ monthly shortfall**. The buffer is the account's average balance over the "
        "last 6 months; the shortfall is typical spending minus typical money in.",
        "Each what-if (job loss, repair bill, higher bills) changes money in, spending or the buffer, and the same "
        "formula is re-run. Python and Snowflake SQL versions were checked against each other for all 4,500 accounts.",
        "How many months the savings would last if the shortfall stayed the same. It is a fair, transparent "
        "stress test that anyone can recompute by hand.",
        "It is not a forecast. Real balances move around; the straight line assumes nothing else changes.",
        "Portfolio snapshot, Customer case, Live twist solver, Recovery plan.")

    _method_card(
        "📊", "Group comparisons", "Statistics", "Evidence tabs",
        "Counting and comparing rates between groups, for example 'loans whose account had a small savings cushion "
        "before the loan' vs 'a large cushion'.",
        "Customers are split into equal-sized groups (for example 10 money-in groups, 4 buffer groups), then we count "
        "how many in each group had a negative-balance month or a recorded loan default. Sample sizes are always shown.",
        "Where problems are more common, which helps decide where a support conversation is most useful.",
        "Why it happens. These are associations, not causes, and they are not adjusted for other differences.",
        "Portfolio snapshot (pre-loan chart), Evidence & model tabs.")

    if xg is not None and rule is not None:
        tells = (f"A 0–100% chance that the account has at least one day below \\$0 in the next 3 months. On 2025 data it "
                 f"had never seen: if the team called the **5% of account-months the model ranks riskiest**, it would "
                 f"reach **{xg['RECALL_AT_5PCT'] * 100:.1f}%** of the customers who really went negative, vs "
                 f"**{rule['RECALL_AT_5PCT'] * 100:.1f}%** with the simple rule. Of the riskiest **2%**, about "
                 f"**{xg['PRECISION_AT_2PCT'] * 100:.0f} in 100** really did go negative.")
    else:
        tells = "A 0–100% chance of at least one day below \\$0 in the next 3 months (scores need the Snowflake connection)."
    _method_card(
        "🌳", "Stress model: XGBoost", "Machine learning", "Used",
        "**XGBoost** combines 200 small decision trees (each asks yes/no questions such as 'was the lowest "
        "balance below \\$0?') and adds up their votes. We compared it with a **simple rule** and with **logistic "
        "regression**, a classic statistical model that weighs each signal in a straight line.",
        "Signals = only the account's own last 6 months (money in and out, how steady they are, balances, days below "
        "zero, fees, fixed costs). No age, gender, district, loan status or default flag. Trained on months up to "
        "Sept 2023, **calibrated** on 2024 so that '20%' really means about 20 in 100, and **tested on 2025**, with "
        "3-month gaps so the answer never leaks into the question.",
        tells,
        "It is not a credit decision and does not say why. Its 'top drivers' show what pushed a score up, which is "
        "an association. It predicts a cash-flow dip, not loan default.",
        "Customer case (stress estimate and drivers), Portfolio map (colour by stress tier), TANG facts.")

    if an is not None and not an.empty:
        scored = an["account_id"].nunique()
        flagged = an[an["story"].notna()]
        low = flagged.loc[flagged["story"].str.contains("money in"), "account_id"].nunique()
        high = flagged.loc[flagged["story"].str.contains("spending"), "account_id"].nunique()
        an_tells = (f"Which 2025 months were far outside **that customer's own** normal pattern: {low:,} of {scored:,} "
                    f"accounts had an unusually low money-in month and {high:,} an unusually high spending month.")
    else:
        an_tells = "Which 2025 months were far outside that customer's own normal pattern."
    _method_card(
        "🚨", "Unusual-month detection", "Machine learning · Snowflake ML ANOMALY_DETECTION", "Used",
        "Snowflake's built-in anomaly detector. It learns each account's normal monthly money in and spending "
        "(Snowflake uses a gradient-boosting time-series model for this) and draws an expected range.",
        "One model per account, trained on its months up to Dec 2024 (accounts with at least 12 months). A 2025 month "
        "is flagged only if it is in the extreme 0.2% tail **and** at least \\$500 and 25% away from expected, so normal "
        "lumpy months are not flagged.",
        an_tells,
        "Whether the change is good or bad, or what caused it. A flag means 'different from usual', nothing more.",
        "Customer case (What changed), TANG case story.")

    if bt is not None and not bt.empty:
        fc_tells = (f"We tested it honestly on Jan–Jun 2025. Average miss: **{_d(bt['mae_forecast'].mean())}** vs "
                    f"**{_d(bt['mae_naive'].mean())}** for simply assuming the balance stays flat. "
                    + ("It lost, so the app **does not show** forecasts." if not getattr(repo, "forecast_validated", False)
                       else "It won, so the app shows it."))
    else:
        fc_tells = "Backtest results are not available."
    _method_card(
        "📈", "Balance forecast", "Machine learning · Snowflake ML FORECAST", "Tested",
        "Snowflake's built-in forecaster. By default it blends several time-series methods (Prophet, ARIMA, "
        "exponential smoothing and gradient boosting) to project the next months.",
        "Trained per account on balances up to Dec 2024, then compared with real 2025 balances and with two simple "
        "baselines: 'balance stays flat' and the challenge's straight-line 'buffer minus shortfall × months'.",
        fc_tells,
        "The future for an individual customer: monthly balances in this data are too irregular for a reliable "
        "6-month projection. Reporting this failure is part of the evidence.",
        "Evidence & model only (and the finding that the straight-line runway is a stress test, not a countdown).")

    if drivers is not None and not drivers.empty:
        total = drivers.loc[drivers["segment"] == "Overall"]
        ti_tells = (f"Which customer segments explain the jump in accounts under 6 months when money in drops to 55%"
                    + (f" ({int(total['accounts_under_6m_baseline'].iloc[0]):,} → {int(total['accounts_under_6m_ei55'].iloc[0]):,} accounts)."
                       if not total.empty else "."))
    else:
        ti_tells = "Which customer segments explain the jump in accounts under 6 months when money in drops to 55%."
    _method_card(
        "🔍", "Top Insights", "Machine learning · Snowflake ML TOP_INSIGHTS", "Used",
        "Snowflake's built-in 'why did this number change?' tool. A decision-tree model splits customers into segments "
        "and measures how much each segment contributes to a change.",
        "We compared 'today' with the 55% money-in what-if, using only financial attributes (money-in group, spending "
        "share, fixed-cost share, buffer, loan, card, statements). Gender and age are deliberately excluded.",
        ti_tells,
        "Causes. Segments overlap and describe where the change shows up, not why it happens.",
        "Portfolio snapshot ('Why the portfolio cracks at 55% money-in').")

    _method_card(
        "🍊", "TANG and the case story", "Generative AI · Snowflake Cortex", "Used",
        "A large language model (Claude via Snowflake Cortex AI_COMPLETE, and a Cortex Agent for the Ask TANG page) "
        "that turns the verified numbers into plain explanations.",
        "It receives only the facts shown on screen and must answer in a fixed format with each statement labelled "
        "(OBSERVED, CALCULATED, SIMULATED, MODEL ESTIMATE, PROPOSED ACTION). Every number it writes is then checked "
        "against those facts automatically.",
        "A readable story and conversation ideas for the advisor, consistent with the numbers on the page.",
        "It never makes risk decisions, approves products or adds new numbers; anything it cannot trace is flagged.",
        "Recovery plan (Ask TANG tab and case story), Ask TANG page.")

    with st.expander("📖 Glossary: the model words in plain language"):
        st.markdown(
            "- **Account-month**: one customer in one month. The model is scored once per account-month.\n"
            "- **Precision (hit rate)**: of the customers we flag, how many really had the problem.\n"
            "- **Recall (coverage)**: of the customers who really had the problem, how many we flagged.\n"
            "- **PR-AUC**: one 0–1 score for how well a model ranks real cases above the rest across every cut-off; "
            "higher is better, and guessing scores about the share of real cases (here under 0.02).\n"
            "- **Brier score**: the average squared gap between the estimated chance and what happened; lower is better.\n"
            "- **Calibration**: making sure '20%' really means about 20 out of 100 such customers.\n"
            "- **Out-of-time test**: train on older years, test on a later year, as if predicting the future.\n"
            "- **Embargo gap**: a few months left out between training and testing so the answer can't leak in.\n"
            "- **Driver / contribution**: how much a signal pushed one customer's score up or down; an association, not a cause.\n"
            "- **Money-in group**: customers ranked by typical monthly money in and split into 10 equal groups "
            "(Bottom 10% … Top 10%). Analysts call these deciles.\n"
            "- **Buffer group**: the same idea with 4 groups by savings cushion (Lowest 25% … Highest 25%)."
        )


def render_model_evidence(repo):
    parts = _model_rows(repo)
    calibration = getattr(repo, "model_calibration", None)
    if parts is None:
        st.info("Model evaluation tables live in Snowflake (ML.MODEL_EVALUATION_METRICS); connect to view them.")
        return
    m, best, rule, lr, major = parts
    st.subheader("Stress model: can account history flag a negative-balance day 3 months ahead?")
    st.markdown(
        "**Question the model answers:** will this account have at least one day below zero in the next 3 months? "
        "**Signals used:** only the account's own last 6 months (no loan status, default flag, demographics or "
        "district). **Fair test:** trained on months up to Sept 2023, calibrated on Jan–Sept 2024, tested on "
        "Jan–Sept 2025, with 3-month gaps between them so answers never leak into the questions."
    )
    n, pos = int(m["SAMPLE_COUNT"].iloc[0]), int(m["POSITIVE_COUNT"].iloc[0])
    _qa("Is the machine-learning model better than a simple rule?",
        f"Yes. Calling the riskiest <b>5%</b> of {n:,} account-months in 2025 would reach "
        f"<b>{best['RECALL_AT_5PCT'] * 100:.1f}%</b> of the {pos:,} real cases with XGBoost, vs "
        f"<b>{rule['RECALL_AT_5PCT'] * 100:.1f}%</b> with the simple rule ('a negative day in the last 3 months or a "
        f"negative low balance in the last 6') and <b>{lr['RECALL_AT_5PCT'] * 100:.1f}%</b> with logistic regression."
        if best is not None and rule is not None and lr is not None and bool(best["BEATS_RULE_BASELINE"]) else
        "See the table below; XGBoost did not clear the rule-based gate.")
    names = [MODEL_NAMES.get(x, x) for x in m["MODEL_NAME"]]
    c1, c2 = st.columns([1.3, 1])
    with c1:
        charts.bar_chart(names, [
            {"name": "Share of real cases found when calling the riskiest 5%", "data": (m["RECALL_AT_5PCT"] * 100).round(1).tolist(),
             "color": charts.TEAL, "labels": True},
            {"name": "Hit rate in the riskiest 2%", "data": (m["PRECISION_AT_2PCT"] * 100).round(1).tolist(), "color": charts.BLUE},
            {"name": "Overall ranking quality (PR-AUC × 100)", "data": (m["PR_AUC"] * 100).round(1).tolist(), "color": charts.ORANGE},
        ], key="disc_model_bars", x_name="Model", y_name="Score (%)", height=380, value_suffix="%", title="2025 test on months the models never saw",
            subtitle=f"{n:,} account-months, {pos:,} had a negative-balance day ({pos / n * 100:.1f}%) · higher is better")
    with c2:
        if calibration is not None and not calibration.empty:
            cal = calibration.copy()
            cal.columns = [c.upper() for c in cal.columns]
            top = cal.iloc[-1]
            gap_pts = abs(top["MEAN_PREDICTED"] - top["OBSERVED_RATE"]) * 100
            close = gap_pts <= max(2.0, 0.25 * top["OBSERVED_RATE"] * 100)
            direction = ("" if gap_pts < 1 else " (the model slightly under-estimates)" if top["OBSERVED_RATE"] > top["MEAN_PREDICTED"]
                         else " (the model slightly over-estimates)")
            _qa("When the model says X%, does about X% really happen?",
                f"{'Roughly, yes' if close else 'Not closely'}{direction}. In the highest-scoring 10% the average estimate was "
                f"<b>{top['MEAN_PREDICTED'] * 100:.1f}%</b> and <b>{top['OBSERVED_RATE'] * 100:.1f}%</b> really went negative.")
            charts.line_chart([score_group_name(b) for b in cal["BIN"]], [
                {"name": "Model's average estimate", "data": (cal["MEAN_PREDICTED"] * 100).round(2).tolist(), "color": charts.ORANGE},
                {"name": "What really happened", "data": (cal["OBSERVED_RATE"] * 100).round(2).tolist(), "color": charts.TEAL, "bar": True},
            ], key="disc_calibration", x_name="Model-score group (lowest → highest)", y_name="Share with a negative day (%)", money=False, zoom=False, height=330,
                title="Estimate vs reality, 2025 test", subtitle="Account-months grouped into 10 equal groups by model score")
    table = m.drop(columns=["SPLIT"], errors="ignore").assign(MODEL_NAME=names).rename(columns={
        "MODEL_NAME": "Model", "SAMPLE_COUNT": "Account-months tested", "POSITIVE_COUNT": "Real cases",
        "PR_AUC": "Ranking quality (PR-AUC)", "ROC_AUC": "ROC-AUC", "BRIER_SCORE": "Brier score (lower = better)",
        "PRECISION_AT_2PCT": "Hit rate, riskiest 2%", "RECALL_AT_2PCT": "Cases found, riskiest 2%",
        "PRECISION_AT_5PCT": "Hit rate, riskiest 5%", "RECALL_AT_5PCT": "Cases found, riskiest 5%",
        "BEATS_RULE_BASELINE": "Beats simple rule"})
    st.dataframe(table, hide_index=True, use_container_width=True)
    st.caption(
        "Limits: real cases are concentrated in a few hundred accounts and recent negative days are a strong signal; "
        "the target is a cash-flow dip, not default. This is a support-outreach research signal, never a credit or "
        "underwriting decision. Driver contributions are associations, not causes. Words like PR-AUC and Brier are "
        "explained in the glossary on the first tab."
    )

    st.markdown("---")
    st.subheader("Balance forecast (Snowflake ML FORECAST)")
    bt = getattr(repo, "forecast_backtest", None)
    if bt is None or bt.empty:
        st.info("Forecast backtest table not available yet.")
    else:
        b = bt.copy()
        shown = repo.forecast_validated
        _qa("Can Snowflake ML predict the next 6 months of balance better than 'it stays flat'?",
            f"{'Yes' if shown else 'No'}. Average miss <b>{_d(b['mae_forecast'].mean())}</b> vs "
            f"<b>{_d(b['mae_naive'].mean())}</b> for 'stays flat' and <b>{_d(b['mae_constant_gap'].mean())}</b> for the "
            f"straight-line runway; the 80% range held the real value only <b>{b['interval_80_coverage'].mean() * 100:.0f}%</b> "
            f"of the time. So the forecast is <b>{'shown' if shown else 'hidden'}</b> in the app.")
        charts.bar_chart([f"{int(h)} month{'s' if int(h) > 1 else ''} ahead" for h in b["horizon"]], [
            {"name": "Snowflake ML forecast", "data": b["mae_forecast"].round(0).tolist(), "color": charts.BLUE},
            {"name": "Balance stays flat", "data": b["mae_naive"].round(0).tolist(), "color": charts.GREY},
            {"name": "Straight-line runway (buffer − shortfall × months)", "data": b["mae_constant_gap"].round(0).tolist(), "color": charts.ORANGE},
        ], key="disc_fc_bt", x_name="Forecast horizon", y_name="Average miss ($)", money=True, height=340, title="Average miss in dollars (lower is better)",
            subtitle=f"Trained to Dec 2024, checked against real Jan–Jun 2025 balances, {int(b['accounts'].iloc[0]):,} accounts")

    st.subheader("Unusual-month detection (Snowflake ML ANOMALY_DETECTION)")
    an = getattr(repo, "anomalies", None)
    if an is None or an.empty:
        st.info("Anomaly table not available yet.")
    else:
        flagged = an[an["story"].notna()]
        _qa("How many customers had a month that was unusual for them in 2025?",
            f"<b>{flagged['account_id'].nunique():,}</b> of <b>{an['account_id'].nunique():,}</b> accounts checked had at "
            "least one flagged month. Each is compared with its own history, not with other customers.")
        by_month = flagged.groupby(["month", "story"]).size().unstack(fill_value=0).reindex(sorted(an["month"].unique()), fill_value=0)
        charts.bar_chart(by_month.index.tolist(), [
            {"name": c, "data": by_month[c].astype(int).tolist(), "color": charts.RED if "spending" in c else charts.YELLOW}
            for c in by_month.columns], key="disc_anom", x_name="Month (2025)", y_name="Accounts flagged", stacked=True, height=320,
            title="Accounts with an unusual month, by month of 2025",
            subtitle="Accounts with 12+ months of history · flagged only if far outside its own usual range and at least $500 / 25% off")
        st.caption("A flag means 'outside this account's usual range', not 'bad' and not a cause.")
