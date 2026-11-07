"""
Screen 5: Forensic Early Warning & Population Discovery
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from src.data.local_repository import LocalDataRepository
from src.services.discovery_engine import get_preloan_early_warning_data
from config.settings import THEME

def render_discoveries(repo: LocalDataRepository):
    st.markdown("## 🔬 Forensic Intelligence & Pre-Loan Early Warning")
    st.caption("Deep behavioral discoveries and credit risk blindspots validated across 6 years of banking history.")

    tab1, tab2, tab3 = st.tabs([
        "🚨 Pre-Loan Underwriting Blindspot",
        "📉 Inverted Resilience (Phantom Wealth)",
        "📊 All 10 Forensic Discoveries"
    ])

    # -------------------------------------------------------------------------
    # TAB 1: PRE-LOAN EARLY WARNING COHORT
    # -------------------------------------------------------------------------
    with tab1:
        st.subheader("Credit Risk Lead Time: Pre-Origination Buffer & Overdraft Determinism")
        st.markdown(
            "We analyzed **615 loan accounts** with at least 6 complete monthly records prior to loan origination. "
            "Using strictly pre-loan data, we uncovered two major underwriting blindspots:"
        )

        pre_data = get_preloan_early_warning_data(repo)

        col_q, col_od = st.columns(2)

        with col_q:
            st.markdown("#### Default Rate by Pre-Loan Buffer Quartile")
            q_df = pre_data["quartile_summary"]
            fig_q = px.bar(
                q_df,
                x="buffer_quartile",
                y="default_rate",
                text="default_rate",
                title="Default Rate (%) by Pre-Origination Buffer",
                color="default_rate",
                color_continuous_scale=["#2A9D8F", "#E63946"]
            )
            fig_q.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_q.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="",
                yaxis_title="Observed Default Rate (%)",
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_q, use_container_width=True)

            st.caption(
                "Borrowers in the lowest pre-loan buffer quartile (Q1) defaulted at **22.7%** ($35/154$), "
                "compared to only **5.2%** ($8/154$) in the highest quartile (Q4)—a **4.4x risk disparity**."
            )

        with col_od:
            st.markdown("#### Pre-Loan Overdraft Determinism")
            od_df = pre_data["overdraft_summary"]
            od_df["Status Label"] = od_df["had_pre_overdraft"].map({
                True: "Experienced Pre-Loan Overdraft",
                False: "Clean Pre-Loan History"
            })
            fig_od = px.bar(
                od_df,
                x="Status Label",
                y="default_rate",
                text="default_rate",
                title="Default Rate (%) by Pre-Loan Overdraft Experience",
                color="default_rate",
                color_continuous_scale=["#2A9D8F", "#E63946"]
            )
            fig_od.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
            fig_od.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis_title="",
                yaxis_title="Observed Default Rate (%)",
                coloraxis_showscale=False
            )
            st.plotly_chart(fig_od, use_container_width=True)

            st.caption(
                "**100.0% of borrowers (21 out of 21)** who had negative-balance days in the 6 months prior to loan start "
                "subsequently defaulted! The bank approved these loans despite active overdrafts on its own ledger."
            )

    # -------------------------------------------------------------------------
    # TAB 2: INVERTED RESILIENCE PARADOX (PHANTOM WEALTH)
    # -------------------------------------------------------------------------
    with tab2:
        st.subheader("The Inverted Resilience Paradox: High Earners Crash Fastest")
        st.markdown(
            "Traditional banking assumes high income equals high financial resilience. "
            "Our data proves that under an Employment Insurance (EI) layoff shock, **top-decile earners crash into zero runway in 3.6 months**."
        )

        decile_data = pd.DataFrame({
            "Income Decile": ["D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10 (Top 10%)"],
            "Median Income": [1580, 2450, 3379, 4224, 6421, 8804, 11101, 13281, 15642, 25474],
            "Median Runway (EI 55%)": [38.1, 34.0, 26.3, 15.8, 7.1, 5.9, 5.4, 4.8, 4.4, 3.7],
            "% Below 6 Mos Runway": [5.3, 2.0, 3.6, 8.2, 37.8, 52.2, 59.6, 72.2, 79.3, 84.4]
        })

        fig_dec = go.Figure()
        fig_dec.add_trace(go.Bar(
            x=decile_data["Income Decile"],
            y=decile_data["% Below 6 Mos Runway"],
            name="% Below 6 Months Runway",
            marker_color=THEME["alert_red"]
        ))
        fig_dec.add_trace(go.Scatter(
            x=decile_data["Income Decile"],
            y=decile_data["Median Runway (EI 55%)"],
            name="Median Runway (Months)",
            mode="lines+markers",
            yaxis="y2",
            line=dict(color=THEME["accent_blue"], width=3)
        ))
        fig_dec.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="% of Customers Below 6 Mos Runway"),
            yaxis2=dict(title="Median Runway (Months)", overlaying="y", side="right", showgrid=False),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_dec, use_container_width=True)

        st.info(
            "💡 **Business Takeaway:** A 45% income reduction generates an **$8,992/month deficit** for top earners, "
            "burning through typical buffers in weeks. Low earners have modest dollar shortfalls ($458/mo) easily sustained by small buffers."
        )

    # -------------------------------------------------------------------------
    # TAB 3: ALL 10 FORENSIC DISCOVERIES
    # -------------------------------------------------------------------------
    with tab3:
        st.subheader("Directory of All 10 Verified Discoveries")
        discoveries_list = [
            ("1. The Spousal Shield", "0.00% default rate across all joint accounts vs 14.15% for solo accounts (p = 3.2e-6).", "Household Accountability"),
            ("2. The Statement Canary", "Requesting per-transaction statements predicts a 23.66% overdraft rate and double default risk (p = 4.5e-19).", "Administrative Early Warning"),
            ("3. Inverted Resilience", "Top 10% income earners crash in 3.6 months under EI while bottom 10% survive 38 months (p = 2.7e-15).", "Lifestyle Inflation Burn"),
            ("4. Cardholder Immunity", "Payment cardholders are 5x less likely to default than non-cardholders (2.94% vs 13.87%, p = 1.6e-4).", "Digital Bank Integration"),
            ("5. Cash Addiction Gradient", "Default rate scales monotonically from 3.88% (transfers) to 18.12% (>80% cash deposits, p = 1.2e-9).", "Inflow Quality Index"),
            ("6. Leasing Overextension", "341 vehicle leasers hold 0 bank loans, double the income, but 2.4x higher overdraft rate (p = 1.3e-8).", "Inflexible Contract Drain"),
            ("7. External Debt Shadow", "35 accounts pay external competitor bank loans via standing orders with zero internal loan book visibility.", "Off-Balance Sheet Debt"),
            ("8. Penalty Fee Death Spiral", "90.0% of penalty-hit borrowers default (72 out of 80). Penalties accelerate customer bankruptcy.", "Regressive Banking Friction"),
            ("9. Payday Evaporation", "Inflows arrive on Days 5-8 & 14, immediately drained by $52.7M in cash withdrawals within 72 hours.", "Intramonth Cash Velocity"),
            ("10. 76% Spend Cushion", "Fixed commitments are only 19.07% of spend; 76.37% is cash withdrawals, providing huge discretionary elasticity.", "Adaptive Survival Runway")
        ]

        for title, desc, tag in discoveries_list:
            st.markdown(f"""
            <div style="background-color: {THEME['card_bg']}; padding: 12px 16px; border-radius: 6px; margin-bottom: 8px; border-left: 3px solid {THEME['primary_orange']};">
                <div style="display: flex; justify-content: space-between;">
                    <span style="font-weight: bold; color: {THEME['text_main']};">{title}</span>
                    <span style="font-size: 11px; color: {THEME['accent_blue']};">{tag}</span>
                </div>
                <p style="font-size: 13px; color: {THEME['text_muted']}; margin: 3px 0 0 0;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)
