"""
Screen 6: Methodology, Formula Standards & Dataset Provenance
"""

import streamlit as st
from config.settings import THEME

def render_methodology():
    st.markdown("## 📖 Methodology, Formal Standards & Ethics")
    st.caption("Complete transparency regarding metric definitions, mathematical integrity, and responsible data use.")

    # 1. Official Challenge Definitions
    st.subheader("📐 Official Tangerine Judging Formulas")
    st.markdown("""
    | Symbol | Official Metric | Precise Mathematical Definition | Notes / Nuances |
    |:---|:---|:---|:---|
    | **$I$** | Typical Monthly Money-In | `median(money_in)` across all account rows | Includes deposits and transfers |
    | **$F$** | Typical Fixed Costs | `median(household_bills + insurance + loan_payments)` | Row-wise monthly sum first, then median |
    | **$S$** | Typical Monthly Spending | `median(money_out)` across all account rows | Total monthly outflow |
    | **$B$** | Savings Buffer | `mean(avg_daily_balance)` over last 6 rows | Chronologically sorted by month |
    | **$H$** | Household Bills | `median(household_bills)` | Baseline for utility/rent shocks |
    | **$P$** | Active Loan Payment | `monthly_payment` if loan status in `['C', 'D']`, else 0 | Excludes finished loans (A, B) |
    """)

    st.markdown("#### Official Runway Formula:")
    st.code("""
buffer_left = B - one_off_costs
gap         = spending_after_shock - income_after_shock

if buffer_left <= 0:
    runway = 0.0
elif gap <= 0:
    runway = "no shortfall (120+)"
else:
    runway = round(min(buffer_left / gap, 120.0), 1)
    """, language="python")

    st.markdown("---")

    # 2. Responsible Data Science Declarations
    st.subheader("🛡️ Responsible AI & Ethical Declarations")
    st.markdown(f"""
    <div style="background-color: {THEME['card_bg']}; padding: 18px; border-radius: 8px;">
        <ul style="color: {THEME['text_muted']}; font-size: 14px; margin: 0; padding-left: 20px;">
            <li><b>Decision-Support, Not Automated Underwriting:</b> This platform is designed as a financial resilience simulator to assist human customer advisors. It is not an automated credit scoring or rejection engine.</li>
            <li><b>Association vs. Causation:</b> All statistical discoveries (e.g. joint accounts, statement frequency, cash inflow shares) represent empirical observational associations within this 6-year portfolio. They do not assert direct causation.</li>
            <li><b>Privacy & Security:</b> No personal identity information (PII), full dates of birth, or individual raw transaction histories are transmitted to external Large Language Models. AI services receive only verified, aggregated evidence JSON.</li>
            <li><b>Deterministic Priority:</b> All financial calculations are executed by deterministic, unit-tested Python services. LLMs are strictly restricted to narrative translation and explanation.</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # 3. Credits & Attribution
    st.subheader("📚 Dataset Attribution & Canadian Benchmarks")
    st.markdown("""
    - **Primary Dataset:** PKDD'99 Discovery Challenge Financial dataset (anonymized retail banking data), CTU Prague Relational Dataset Repository.
    - **Monetary Normalization:** All currency denominations are in Canadian Dollars (CAD) as specified in the track challenge.
    - **Macro Benchmarks (Canada):**
      - Statistics Canada Consumer Price Index (CPI): [Table 18-10-0004-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1810000401)
      - CMHC Average Rents: [Table 34-10-0133-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410013301)
      - Labour Force Survey: [Table 14-10-0287-01](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1410028701)
      - Employment Insurance Regular Benefits (55% earnings): [Canada.ca EI Guidelines](https://www.canada.ca/en/services/benefits/ei/ei-regular-benefit.html)
    """)
