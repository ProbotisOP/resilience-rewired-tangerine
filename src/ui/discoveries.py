"""Screen 5: Reproducible, denominator-explicit portfolio observations."""

import streamlit as st
import plotly.express as px

from src.data.local_repository import LocalDataRepository
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

    tab1, tab2, tab3 = st.tabs(
        [
            "Before a loan",
            "Income what-if",
            "Group comparisons",
        ]
    )

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
                st.markdown("**Recorded default rate by pre-loan buffer quartile**")
                fig_q = px.bar(
                    q_df,
                    x="buffer_quartile",
                    y="default_rate",
                    color="default_rate",
                    text="default_rate",
                    color_continuous_scale=["#2A9D8F", "#E63946"],
                )
                fig_q.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
                fig_q.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    xaxis_title="",
                    yaxis_title="Observed defaulted loans (%)",
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig_q, use_container_width=True)
            with right:
                display_quartiles = q_df.rename(
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
        deciles = get_income_decile_discovery(repo).rename(
            columns={
                "Income Decile": "Money-in Group",
                "Median Income": "Median Money-in",
                "Median Runway (EI 55%)": "Median Runway (55% money-in)",
            }
        )
        st.subheader("Runway in a 55% money-in what-if")
        st.markdown(
            "Accounts are split into ten groups using account-level median `money_in`. "
            "For each account, the deterministic Judge Match formula is recalculated with "
            "income set to 55% of median money-in; this is a simulation, not observed layoff data."
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
                f"{bottom['Money-in Group']} · median simulated runway",
                f"{bottom['Median Runway (55% money-in)']:.1f} months",
                f"{int(bottom['Accounts Below 6 Months'])} of {int(bottom['Accounts'])} below 6 months",
            )
            story_cols[1].metric(
                f"{top['Money-in Group']} · median simulated runway",
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
        fig = px.bar(
            deciles,
            x="Money-in Group",
            y="% Below 6 Months",
            color="% Below 6 Months",
            text="% Below 6 Months",
            color_continuous_scale=["#2A9D8F", "#E63946"],
        )
        fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis_title="Account-level median money-in decile",
            yaxis_title="Accounts below six months of runway (%)",
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(
            deciles.style.format(
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
            f"{int(deciles['Accounts'].iloc[0]):,} in each decile. Account history spans "
            "available monthly records in 2020–2025; money-in is not verified employment income. "
            "Runway threshold counts use one-decimal official values."
        )
        with st.expander("🧾 How this chart is calculated"):
            st.markdown(
                """
                1. Calculate each account's median monthly money in.
                2. Split the accounts into ten equal-sized groups, ordered from lowest to highest median money in.
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
