"""Screen 5: Reproducible, denominator-explicit portfolio observations."""

import streamlit as st
from src.ui.charting import axis_style, base_options, render_chart

from src.data.local_repository import LocalDataRepository
from src.services.discovery_engine import (
    get_behavioral_association_tables,
    get_income_decile_discovery,
    get_preloan_early_warning_data,
)


def render_discoveries(repo: LocalDataRepository):
    st.markdown("## 🔎 What the data shows")
    st.caption(
        "Use these comparisons to spot questions worth exploring. They do not explain why something happened "
        "or predict what will happen to a person."
    )

    tab1, tab2, tab3 = st.tabs(
        [
            "Before a loan",
            "Income what-if",
            "Other comparisons",
        ]
    )

    with tab1:
        pre_data = get_preloan_early_warning_data(repo)
        st.subheader("Savings before a loan and its recorded status")
        st.markdown(
            f"We can compare **{pre_data['cohort_size']:,} of "
            f"{pre_data.get('eligible_loan_count', 0):,} loans** because each has at least six "
            f"monthly records before the loan began. Records span "
            f"{pre_data.get('window_start', 'not available')} to "
            f"{pre_data.get('window_end', 'not available')}; the exact six-month window varies by loan."
        )
        st.markdown(
            "### What this comparison can tell us\n"
            "Among loans with enough earlier account history, we compare recorded outcomes for "
            "accounts with smaller and larger savings buffers. This can help start a customer-led "
            "conversation. It cannot show that the buffer caused the outcome or support an automated credit decision."
        )
        st.warning(
            "The source data marks some loans as defaulted (B or D). Other loans may still be active. "
            "This comparison does not show that a smaller buffer causes default."
        )

        q_df = pre_data["quartile_summary"]
        if not q_df.empty:
            q_df = q_df.copy()
            q_df["buffer_quartile"] = q_df["buffer_quartile"].astype(str).replace(
                {
                    "Q1 (Lowest Buffer)": "Smallest savings buffer",
                    "Q2": "Lower-middle savings buffer",
                    "Q3": "Upper-middle savings buffer",
                    "Q4 (Highest Buffer)": "Largest savings buffer",
                }
            )
            lowest_buffer = q_df.loc[
                q_df["buffer_quartile"] == "Smallest savings buffer"
            ]
            highest_buffer = q_df.loc[
                q_df["buffer_quartile"] == "Largest savings buffer"
            ]
            if not lowest_buffer.empty and not highest_buffer.empty:
                q1, q4 = lowest_buffer.iloc[0], highest_buffer.iloc[0]
                rate_cols = st.columns(2)
                rate_cols[0].metric(
                    "Smaller savings group · marked default",
                    f"{q1['default_rate']:.1f}%",
                    f"{int(q1['defaults'])} of {int(q1['loans'])} loans",
                )
                rate_cols[1].metric(
                    "Larger savings group · marked default",
                    f"{q4['default_rate']:.1f}%",
                    f"{int(q4['defaults'])} of {int(q4['loans'])} loans",
                )
            left, right = st.columns(2)
            with left:
                st.markdown("**Share marked as default by earlier savings level**")
                quartile_options = base_options()
                quartile_options.update(
                    {
                        "grid": {"left": 16, "right": 30, "top": 50, "bottom": 32, "containLabel": True},
                        "xAxis": {"type": "value", "name": "Recorded defaulted loans (%)", "min": 0, "max": 100, "axisLabel": {"color": "#8D99AE", "formatter": "{value}%"}, "splitLine": {"lineStyle": {"color": "rgba(141,153,174,.16)"}}},
                        "yAxis": {"type": "category", "data": q_df["buffer_quartile"].astype(str).tolist(), "axisLabel": {"color": "#8D99AE"}, **{k: v for k, v in axis_style().items() if k not in ("axisLabel", "splitLine")}},
                        "series": [{
                            "name": "Recorded default rate",
                            "type": "bar",
                            "barMaxWidth": 32,
                            "data": q_df["default_rate"].round(1).tolist(),
                            "itemStyle": {"color": "#FF5B00", "borderRadius": [0, 5, 5, 0]},
                            "label": {"show": True, "position": "right", "color": "#F8F9FA", "formatter": "{c}%"},
                            "emphasis": {"focus": "series"},
                        }],
                    }
                )
                quartile_options["tooltip"]["trigger"] = "item"
                render_chart(quartile_options, key="discovery-preloan-default-rate", height=380)
            with right:
                display_quartiles = q_df.rename(
                    columns={
                        "buffer_quartile": "Savings before loan began",
                        "loans": "Loans included",
                        "defaults": "Loans marked as default",
                        "default_rate": "Share marked as default",
                        "median_buffer": "Middle savings balance before loan",
                    }
                )
                st.dataframe(
                    display_quartiles.style.format(
                        {
                            "Share marked as default": "{:.1f}%",
                            "Middle savings balance before loan": "${:,.2f}",
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
            "Each group's totals show how many loans are included. We use the six latest available "
            "monthly records before the loan began; they may not be consecutive months."
        )

    with tab2:
        deciles = get_income_decile_discovery(repo).rename(
            columns={
                "Income Decile": "Money-in Group",
                "Median Income": "Middle monthly money in",
                "Median Runway (EI 55%)": "Middle estimated coverage (months)",
            }
        )
        decile_names = {
            f"D{i}": label
            for i, label in enumerate(
                [
                    "Lowest usual money-in group", "Group 2", "Group 3", "Group 4", "Group 5",
                    "Group 6", "Group 7", "Group 8", "Group 9", "Highest usual money-in group",
                ],
                start=1,
            )
        }
        deciles["Money-in Group"] = deciles["Money-in Group"].astype(str).replace(decile_names)
        st.subheader("What if recorded money-in fell to 55%?")
        st.markdown(
            "We sort accounts by their usual monthly money-in and split them into ten similarly sized groups. "
            "Then we recalculate each account with money-in set to 55% of usual. This is a what-if, "
            "not observed job-loss data or verified employment income."
        )
        if not deciles.empty:
            bottom, top = deciles.iloc[0], deciles.iloc[-1]
            st.markdown(
                "### What stands out\n"
                "The same money-in change gives different results across groups. Savings buffers "
                "and spending matter too, so income alone does not explain the result."
            )
            story_cols = st.columns(2)
            story_cols[0].metric(
                f"{bottom['Money-in Group']} · estimated coverage",
                f"{bottom['Middle estimated coverage (months)']:.1f} months",
                f"{int(bottom['Accounts Below 6 Months'])} of {int(bottom['Accounts'])} below 6 months",
            )
            story_cols[1].metric(
                f"{top['Money-in Group']} · estimated coverage",
                f"{top['Middle estimated coverage (months)']:.1f} months",
                f"{int(top['Accounts Below 6 Months'])} of {int(top['Accounts'])} below 6 months",
            )
            st.info(
                "Business opportunity to explore: offer customers a clear way to discuss savings buffers "
                "and spending under different what-ifs. This dataset does not measure customer interest "
                "or business impact, and these results are not for credit decisions."
            )
            if st.button(
                "Try a what-if with an account",
                key="discovery_try_whatif",
                type="primary",
            ):
                st.query_params["page"] = "what-if"
                st.rerun()
        decile_options = base_options(zoom=True)
        decile_options.update(
            {
                "grid": {"left": 20, "right": 20, "top": 48, "bottom": 76, "containLabel": True},
                "xAxis": {"type": "category", "name": "Usual monthly money coming in (group)", "nameLocation": "middle", "nameGap": 28, "data": deciles["Money-in Group"].astype(str).tolist(), "axisLabel": {"color": "#8D99AE", "interval": 0}, **{k: v for k, v in axis_style().items() if k != "axisLabel"}},
                "yAxis": {"type": "value", "name": "Below six months (%)", "min": 0, "max": 100, "axisLabel": {"color": "#8D99AE", "formatter": "{value}%"}, "splitLine": {"lineStyle": {"color": "rgba(141,153,174,.16)"}}},
                "series": [{
                    "name": "Below six months",
                    "type": "bar",
                    "barMaxWidth": 36,
                    "data": deciles["% Below 6 Months"].round(1).tolist(),
                    "itemStyle": {"color": "#FF5B00", "borderRadius": [5, 5, 0, 0]},
                    "label": {"show": True, "position": "top", "color": "#F8F9FA", "formatter": "{c}%"},
                    "emphasis": {"focus": "series", "itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(255,91,0,.3)"}},
                }],
            }
        )
        render_chart(decile_options, key="discovery-income-decile-runway", height=440)
        st.dataframe(
            deciles.style.format(
                {
                    "Middle monthly money in": "${:,.2f}",
                    "Middle estimated coverage (months)": "{:.1f}",
                    "% Below 6 Months": "{:.1f}%",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(
            f"This comparison includes {int(deciles['Accounts'].sum()):,} accounts, "
            f"about {int(deciles['Accounts'].iloc[0]):,} in each group. Account history spans "
            "available monthly records in 2020–2025. Money coming in is not verified employment pay."
        )
        with st.expander("🧾 How this chart is calculated"):
            st.markdown(
                """
                1. Find each account's middle monthly money-in amount.
                2. Split the accounts into ten similar-sized groups, from lowest to highest usual money in.
                3. For each account, multiply its median money in by **55%**; leave its typical spending and buffer unchanged.
                4. Recalculate estimated buffer coverage, round it to one decimal, and count accounts below six months.
                5. Divide that count by the accounts in the group to get the displayed percentage.

                This is a fixed scenario applied to recorded money in—not a measured job-loss or benefit outcome.
                """
            )

    with tab3:
        st.subheader("Other account comparisons")
        st.markdown(
            "These tables summarize the account, card, loan and payment records provided. Monthly history "
            "covers available records from 2020–2025. Payment instructions are an undated snapshot."
        )
        st.caption(
            "For each group, the tables show how many accounts or loans are included. A below-zero month means "
            "the record shows days when the balance was below zero. Loan statuses B/D are counted as marked defaults; "
            "some loans may still be active. Group differences do not establish cause."
        )
        tables = get_behavioral_association_tables(repo)

        title_by_key = {
            "authorized_user": "Accounts with an authorized user listed",
            "statement_frequency": "Statement frequency, below-zero balances and loan status",
            "card": "Card records and loan status",
            "cash_deposit_reliance": "Cash deposits and recorded loan status",
            "leasing_order": "Payment instructions labelled as leasing",
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
        cash["cash_deposit_reliance_quartile"] = cash["cash_deposit_reliance_quartile"].replace(
            {"Q1 (Lowest)": "Lowest cash-deposit share", "Q2": "Lower-middle share", "Q3": "Upper-middle share", "Q4 (Highest)": "Highest cash-deposit share"}
        )
        cash = cash.rename(
            columns={
                "cash_deposit_reliance_quartile": "Cash-deposit share group",
                "loans": "Loans included",
                "defaults": "Loans marked as default",
                "median_cash_deposit_share": "Middle cash-deposit share",
                "default_rate_pct": "Share marked as default",
            }
        )
        st.markdown(f"**{title_by_key['cash_deposit_reliance']}**")
        st.dataframe(
            cash.style.format(
                {
                    "Middle cash-deposit share": "{:.1%}",
                    "Share marked as default": "{:.1f}%",
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
        st.markdown("**Loan-payment instructions to another provider**")
        st.write(
            f"{int(external['standing_order_rows']):,} scheduled-payment instructions are labelled "
            f"loan payment, affecting {int(external['accounts_with_instruction']):,} accounts; "
            f"{int(external['accounts_without_internal_loan']):,} such accounts have no loan "
            "record in this dataset. These are instructions to external destinations, not "
            "confirmation of outstanding external debt."
        )
        st.caption(
            "Loan totals include all supplied loan records. The source marks B and D as defaults; "
            "some C/D loans may still be active. Differences between groups do not explain cause."
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
