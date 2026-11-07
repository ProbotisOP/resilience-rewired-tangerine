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
    }
    [data-testid="stMetricLabel"] {
        color: #8D99AE !important;
        font-size: 13px !important;
        font-weight: 500 !important;
    }
    
    /* Custom Button Styling */
    div.stButton > button:first-child {
        background-color: #FF5B00;
        color: white;
        border: none;
        border-radius: 6px;
        padding: 8px 16px;
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
from config.settings import THEME

@st.cache_resource(show_spinner="Loading Tangerine financial intelligence repository...")
def load_data_engine():
    repo = LocalDataRepository.get_instance()
    repo.load_all()
    return repo

def main():
    repo = load_data_engine()

    # Sidebar Branding & Navigation
    with st.sidebar:
        st.markdown(f"""
        <div style="text-align: center; padding: 10px 0 15px 0;">
            <h2 style="color: {THEME['primary_orange']} !important; margin: 0; font-size: 28px;">🛡️ Tangerine</h2>
            <p style="color: {THEME['text_main']}; margin: 0; font-weight: 600; font-size: 15px;">Resilience Rewired</p>
            <span style="font-size: 11px; color: {THEME['text_muted']};">Sheridan Datathon 2026 · Team CTRL+ALT+WIN</span>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")

        page = st.radio(
            "Platform Navigation",
            options=[
                "🏛️ Portfolio Overview & Macro Insights",
                "👤 Customer Intelligence Explorer",
                "⚡ Financial Shock Simulator (Live Twist)",
                "🎯 Recovery & Emergency Planner",
                "🔬 Forensic Early Warning & Discoveries",
                "💬 AI Strategic Executive Advisor",
                "📖 Methodology & Challenge Formulas"
            ],
            index=0
        )

        st.markdown("---")
        st.markdown("### 🔍 Active Customer Context")
        active_id = st.session_state.get("active_account_id", 20111)
        st.info(f"**Selected Account:** #{active_id}")
        
        st.caption("Change account in the Customer Explorer tab at any time during judging demonstration.")

    # Page Routing
    if page == "🏛️ Portfolio Overview & Macro Insights":
        render_overview(repo)
    elif page == "👤 Customer Intelligence Explorer":
        render_customer_explorer(repo)
    elif page == "⚡ Financial Shock Simulator (Live Twist)":
        render_shock_simulator(repo)
    elif page == "🎯 Recovery & Emergency Planner":
        render_recovery_planner(repo)
    elif page == "🔬 Forensic Early Warning & Discoveries":
        render_discoveries(repo)
    elif page == "💬 AI Strategic Executive Advisor":
        render_ai_advisor(repo)
    elif page == "📖 Methodology & Challenge Formulas":
        render_methodology()

if __name__ == "__main__":
    main()
