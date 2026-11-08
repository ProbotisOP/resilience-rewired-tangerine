"""
Resilience Rewired: Financial Resilience Intelligence Platform
Sheridan Datathon 2026 — Tangerine Track
Team: CTRL + ALT + WIN (Satnam Singh & Antigravity)
"""
 
import streamlit as st
from pathlib import Path
 
# Streamlit Page Setup
st.set_page_config(
    page_title="Resilience Rewired · Tangerine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)
 
# Custom High-Contrast Fintech Styling (Tangerine Navy & Orange)
st.markdown("""
<style>
    /* Global Page Styling */
    .stApp {
        background-color: #0B132B;
        color: #F8F9FA;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }
    .block-container {
        max-width: 1500px;
        padding: 1.5rem clamp(1rem, 3vw, 2.75rem) 3rem;
    }
    
    /* Top Header & Accents */
    h1, h2, h3, h4 {
        color: #FFFFFF !important;
        font-weight: 700 !important;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #121B36;
        border-right: 1px solid #202D52;
    }
    
    /* Metric Card Styling */
    [data-testid="stMetricValue"] {
        color: #FF5B00 !important;
        font-size: 26px !important;
        font-weight: 700 !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
        overflow-wrap: anywhere;
    }
    [data-testid="stMetricLabel"] {
        color: #8D99AE !important;
        font-size: 13px !important;
        font-weight: 500 !important;
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    [data-testid="stMetric"] {
        background: linear-gradient(145deg, rgba(28, 37, 65, .96), rgba(18, 27, 54, .96));
        border: 1px solid #263557;
        border-radius: 14px;
        padding: 16px 18px;
        min-height: 116px;
        box-shadow: 0 8px 24px rgba(0, 0, 0, .12);
    }

    [data-testid="stMetricLabel"] *, [data-testid="stMetricValue"] * {
        white-space: normal !important;
        overflow: visible !important;
        text-overflow: clip !important;
    }
    [data-testid="stMetricLabel"] p { line-height: 1.4; }
    [data-testid="stPlotlyChart"] {
        border: 1px solid rgba(58, 79, 122, .55);
        border-radius: 14px;
        overflow: hidden;
        background: rgba(18, 27, 54, .35);
    }
    .stMarkdown p, [data-testid="stCaptionContainer"] { line-height: 1.6; }
    @media (max-width: 900px) {
        .block-container { padding-top: 1rem; }
        [data-testid="stMetric"] { min-height: 104px; padding: 13px 14px; }
        [data-testid="stMetricValue"] { font-size: 22px !important; }
    }
    @media (max-width: 600px) {
        .block-container { padding-left: .75rem; padding-right: .75rem; }
        [data-testid="stMetric"] { min-height: 92px; padding: 11px 12px; }
        [data-testid="stMetricValue"] { font-size: 19px !important; }
        h1 { font-size: 1.75rem !important; }
        h2 { font-size: 1.45rem !important; }
    }
    [data-testid="stAlert"] {
        border-radius: 10px;
    }
    [data-testid="stExpander"] {
        border: 1px solid #263557;
        border-radius: 10px;
        background-color: rgba(18, 27, 54, 0.55);
    }
    
    /* Custom Button Styling */
    div.stButton > button:first-child {
        background-color: #FF5B00;
        color: white;
        border: none;
        border-radius: 9px;
        padding: 10px 16px;
        font-weight: 600;
        transition: all 0.2s ease-in-out;
    }
    div.stButton > button:first-child:hover {
        background-color: #FF7A29;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(255, 91, 0, 0.3);
    }
    
    /* Tabs & Expander */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        background-color: #16203D;
        border-radius: 4px;
        color: #8D99AE;
        padding: 8px 16px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #FF5B00 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)
 
from src.data.local_repository import LocalDataRepository
from src.ui.overview import render_overview
from src.ui.customer_explorer import render_customer_explorer
from src.ui.shock_simulator import render_shock_simulator
from src.ui.recovery_planner import render_recovery_planner
from src.ui.discoveries import render_discoveries
from src.ui.ai_advisor import render_ai_advisor
from src.ui.methodology import render_methodology
from overdraft_risk.ui import render_overdraft_risk
from config.settings import THEME
 
PAGE_OPTIONS = [
    "🏠 Portfolio overview",
    "👤 Explore an account",
<<<<<<< HEAD
    "🎲 Test a what-if",
    "🧭 Savings & shock plan",
    "🔎 Explore portfolio patterns",
    "💬 Ask about the data",
    "🧮 How the figures are worked out",
=======
    "🎲 Try a what-if",
    "🧭 Build a resilience plan",
    "🔎 What the data shows",
    "💬 Ask the data",
    "🧮 How we calculate it",
    "⚠️ Overdraft risk",
>>>>>>> 14df8198bdda52f121b270788ff0eef71c3c6fbc
]
PAGE_SLUGS = {
    PAGE_OPTIONS[0]: "portfolio",
    PAGE_OPTIONS[1]: "account",
    PAGE_OPTIONS[2]: "what-if",
    PAGE_OPTIONS[3]: "plan",
    PAGE_OPTIONS[4]: "evidence",
    PAGE_OPTIONS[5]: "ask",
    PAGE_OPTIONS[6]: "method",
    PAGE_OPTIONS[7]: "overdraft-risk",
}
PAGES_BY_SLUG = {slug: page for page, slug in PAGE_SLUGS.items()}
 
 
def _sync_navigation_query_param():
    selected_page = st.session_state["main_navigation"]
    st.query_params["page"] = PAGE_SLUGS[selected_page]
 
 
@st.cache_resource(show_spinner="Loading Tangerine financial intelligence repository...")
def load_data_engine():
    repo = LocalDataRepository.get_instance()
    repo.load_all()
    return repo
 
def main():
    try:
        repo = load_data_engine()
    except FileNotFoundError as error:
        st.error(f"Required source data is missing. {error}")
        st.stop()
 
    valid_accounts = repo.get_all_accounts()
    if not valid_accounts:
        st.error("No valid account IDs are available in the loaded account directory.")
        st.stop()
    if st.session_state.get("active_account_id") not in valid_accounts:
        st.session_state["active_account_id"] = valid_accounts[0]
 
    # Sidebar Branding & Navigation
    with st.sidebar:
        requested_page = PAGES_BY_SLUG.get(st.query_params.get("page", ""))
        if requested_page is not None:
            st.session_state["main_navigation"] = requested_page
        elif "main_navigation" not in st.session_state:
            st.session_state["main_navigation"] = PAGE_OPTIONS[0]
 
        st.markdown(f"""
        <div style="text-align: center; padding: 10px 0 15px 0;">
            <h2 style="color: {THEME['primary_orange']} !important; margin: 0; font-size: 28px;">🛡️ Tangerine</h2>
            <p style="color: {THEME['text_main']}; margin: 0; font-weight: 600; font-size: 15px;">Resilience Rewired</p>
            <span style="font-size: 11px; color: {THEME['text_muted']};">Sheridan Datathon 2026 · Team CTRL+ALT+WIN</span>
        </div>
        """, unsafe_allow_html=True)
 
        st.markdown("---")
 
        page = st.radio(
            "Where would you like to go?",
            options=PAGE_OPTIONS,
            key="main_navigation",
            on_change=_sync_navigation_query_param,
        )
 
        st.markdown("---")
        st.markdown("### Account selected")
        active_id = st.session_state["active_account_id"]
        st.info(f"**Selected Account:** #{active_id}")
        
<<<<<<< HEAD
        st.caption("Change the selected account from “Explore an account” or “Test a what-if.”")

=======
        st.caption("You can switch accounts from “Explore an account” or “Try a what-if.”")
 
>>>>>>> 14df8198bdda52f121b270788ff0eef71c3c6fbc
    # Page Routing
    if page == "🏠 Portfolio overview":
        render_overview(repo)
    elif page == "👤 Explore an account":
        render_customer_explorer(repo)
    elif page == "🎲 Test a what-if":
        render_shock_simulator(repo)
    elif page == "🧭 Savings & shock plan":
        render_recovery_planner(repo)
    elif page == "🔎 Explore portfolio patterns":
        render_discoveries(repo)
    elif page == "💬 Ask about the data":
        render_ai_advisor(repo)
    elif page == "🧮 How the figures are worked out":
        render_methodology()
    elif page == "⚠️ Overdraft risk":
        render_overdraft_risk(repo)
 
if __name__ == "__main__":
    main()
