"""
Resilience Rewired: Snowflake-powered financial resilience intelligence.
Sheridan Datathon 2026 — Tangerine Track · Team CTRL + ALT + WIN
"""

import streamlit as st

st.set_page_config(page_title="Resilience Rewired · Tangerine", page_icon="🛡️", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
  .block-container { max-width: 1480px; padding-top: 1.2rem; padding-bottom: 3rem; }
  h2 { font-weight: 750 !important; letter-spacing: -0.02em; }
  h3 { font-weight: 650 !important; letter-spacing: -0.01em; margin-top: .4rem !important; }
  [data-testid="stSidebar"] { background: #111316; border-right: 1px solid #262A30; }
  [data-testid="stMetric"] { background: #1C1F24; border: 1px solid #2B3037; border-radius: 12px; padding: 12px 14px;
                             transition: border-color .15s ease, transform .15s ease; }
  [data-testid="stMetric"]:hover { border-color: #FF6A13; transform: translateY(-1px); }
  [data-testid="stMetricValue"] { font-size: 1.45rem !important; font-weight: 700 !important; }
  [data-testid="stMetricLabel"] p { color: #9AA3AD !important; font-size: .8rem !important; }
  .stTabs [data-baseweb="tab-list"] { gap: 4px; border-bottom: 1px solid #2B3037; }
  .stTabs [data-baseweb="tab"] { border-radius: 8px 8px 0 0; padding: 8px 14px; }
  .stTabs [aria-selected="true"] { color: #FF6A13 !important; }
  div.stButton > button { border-radius: 10px; border: 1px solid #343A42; transition: all .15s ease; }
  div.stButton > button:hover { border-color: #FF6A13; color: #FF6A13; transform: translateY(-1px); }
  .rr-card { background: #1C1F24; border: 1px solid #2B3037; border-left: 4px solid #FF6A13; border-radius: 12px;
             padding: 14px 16px; margin-bottom: 12px; }
  .rr-card-title { color: #9AA3AD; font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }
  .rr-card-value { font-size: 1.6rem; font-weight: 750; margin: 2px 0 4px; }
  .rr-card-body { color: #C9CED4; font-size: .85rem; line-height: 1.4; }
  .rr-hero { background: linear-gradient(135deg, #22252B 0%, #1A1C20 60%, #2A1A10 100%); border: 1px solid #2B3037;
             border-radius: 16px; padding: 18px 22px; margin: 6px 0 14px; }
  .rr-hero-title { font-size: 1.7rem; font-weight: 800; color: #FFFFFF; }
  .rr-hero-sub { color: #9AA3AD; font-size: .86rem; margin: 4px 0 10px; }
  .rr-badge { display: inline-block; border: 1px solid #3A4149; border-radius: 999px; padding: 4px 12px;
              font-size: .8rem; font-weight: 600; color: #C9CED4; background: rgba(255,255,255,.03); }
  .rr-verdict { background: #1C1F24; border: 1px solid #2B3037; border-left: 5px solid #FF6A13; border-radius: 12px;
                padding: 12px 16px; margin: 8px 0 12px; color: #C9CED4; }
  .rr-verdict span { display: block; color: #9AA3AD; font-size: .72rem; text-transform: uppercase; letter-spacing: .08em; }
  .rr-verdict b { color: #FFFFFF; font-size: 1.15rem; }
  .rr-brand { text-align: center; padding: 4px 0 10px; }
  .rr-brand h2 { color: #FF6A13 !important; margin: 0; font-size: 1.6rem; }
  .rr-status { border-radius: 8px; padding: 6px 10px; font-size: .75rem; text-align: center; margin-bottom: 8px; }
  .tang-hero { background: linear-gradient(135deg, #2A1A10 0%, #1C1F24 70%); border: 1px solid #FF6A13; border-radius: 16px;
               padding: 14px 20px; margin: 4px 0 12px; display: flex; align-items: center; gap: 14px; }
  .tang-hero .tang-logo { font-size: 2.4rem; line-height: 1; }
  .tang-hero .tang-name { color: #FF6A13; font-size: 1.9rem; font-weight: 850; letter-spacing: .04em; line-height: 1.05; }
  .tang-hero .tang-sub { color: #C9CED4; font-size: .85rem; }
  .rr-q { color: #FF6A13; font-size: .74rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; margin-top: 6px; }
  .rr-qtitle { color: #FFFFFF; font-size: 1.12rem; font-weight: 700; margin: 0 0 2px; }
  .rr-answer { background: rgba(255,106,19,.08); border-left: 3px solid #FF6A13; border-radius: 6px; padding: 6px 10px;
               color: #E8EAED; font-size: .88rem; margin: 2px 0 6px; }
  .rr-answer b { color: #FFB37A; }
  .rr-nav-h { color: #6B747F; font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .12em;
              margin: 14px 0 2px 6px; }
  [data-testid="stSidebar"] div.stButton { margin-bottom: -10px; }
  [data-testid="stSidebar"] div.stButton > button { justify-content: flex-start; border: 1px solid transparent;
              border-left: 3px solid transparent; border-radius: 8px; padding: 6px 12px; min-height: 2.3rem;
              background: transparent; color: #C9CED4; font-weight: 500; }
  [data-testid="stSidebar"] div.stButton > button:hover { background: rgba(255,255,255,.04); color: #FFFFFF;
              border-left-color: #3A4149; transform: none; }
  [data-testid="stSidebar"] div.stButton > button[kind="primary"],
  [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] { background: rgba(255,106,19,.12);
              border-left: 3px solid #FF6A13; color: #FFFFFF; font-weight: 700; }
  [data-testid="stSidebar"] div.stButton > button p { text-align: left; }
</style>
""", unsafe_allow_html=True)

from src.data.snowflake_repository import SnowflakeDataRepository  # noqa: E402
from src.ui.ai_advisor import render_ai_advisor  # noqa: E402
from src.ui.customer_explorer import render_customer_explorer  # noqa: E402
from src.ui.discoveries import render_discoveries  # noqa: E402
from src.ui.hidden_patterns import render_hidden_patterns  # noqa: E402
from src.ui.methodology import render_methodology  # noqa: E402
from src.ui.overview import render_overview  # noqa: E402
from src.ui.recovery_planner import render_recovery_planner  # noqa: E402
from src.ui.shock_simulator import render_shock_simulator  # noqa: E402

PAGES = [
    ("portfolio", "Portfolio snapshot", render_overview),
    ("patterns", "Hidden patterns", render_hidden_patterns),
    ("account", "Customer case", render_customer_explorer),
    ("what-if", "Live twist solver", render_shock_simulator),
    ("plan", "Recovery plan & brief", render_recovery_planner),
    ("advisor", "🍊 :orange[**Ask TANG**]", render_ai_advisor),
    ("evidence", "Evidence & model", render_discoveries),
    ("method", "How we calculate", lambda repo: render_methodology()),
]
LABELS = [p[1] for p in PAGES]
BY_SLUG = {p[0]: p[1] for p in PAGES}
SLUG_BY_LABEL = {p[1]: p[0] for p in PAGES}
RENDER = {p[1]: p[2] for p in PAGES}
NAV_SECTIONS = [
    ("The story", ["portfolio", "patterns"]),
    ("Customer", ["account", "what-if", "plan"]),
    ("AI assistant", ["advisor"]),
    ("Proof", ["evidence", "method"]),
]
NAV_ICONS = {
    "portfolio": ":material/dashboard:", "patterns": ":material/insights:", "account": ":material/person_search:",
    "what-if": ":material/tune:", "plan": ":material/flag:", "evidence": ":material/fact_check:",
    "method": ":material/functions:",
}


@st.cache_resource(show_spinner="Loading the nine tables from Snowflake…")
def load_repo() -> SnowflakeDataRepository:
    return SnowflakeDataRepository.get_instance()


def _go(slug: str) -> None:
    st.session_state["main_navigation"] = BY_SLUG[slug]
    st.query_params["page"] = slug


def _nav_menu() -> str:
    """Grouped sidebar menu: one button per page; the active page is the primary (highlighted) button."""
    current = st.session_state["main_navigation"]
    for section, slugs in NAV_SECTIONS:
        st.markdown(f"<div class='rr-nav-h'>{section}</div>", unsafe_allow_html=True)
        for slug in slugs:
            label = BY_SLUG[slug]
            st.button(label, key=f"nav_{slug}", icon=NAV_ICONS.get(slug), use_container_width=True,
                      type="primary" if label == current else "tertiary", on_click=_go, args=(slug,))
    return current


def main():
    repo = load_repo()
    accounts = repo.get_all_accounts()
    requested_account = st.query_params.get("account")
    if requested_account and requested_account != st.session_state.get("_applied_account_param"):
        st.session_state["_applied_account_param"] = requested_account
        if requested_account.isdigit() and int(requested_account) in accounts:
            st.session_state["active_account_id"] = int(requested_account)
    if st.session_state.get("active_account_id") not in accounts:
        st.session_state["active_account_id"] = accounts[0]

    requested = BY_SLUG.get(st.query_params.get("page", ""))
    if requested:
        st.session_state["main_navigation"] = requested
    st.session_state.setdefault("main_navigation", LABELS[0])

    with st.sidebar:
        st.markdown("<div class='rr-brand'><h2>🛡️ Tangerine</h2><b>Resilience Rewired</b><br/>"
                    "<span style='color:#9AA3AD;font-size:.75rem'>Sheridan Datathon 2026 · CTRL+ALT+WIN</span></div>",
                    unsafe_allow_html=True)
        if repo.is_connected:
            st.markdown("<div class='rr-status' style='background:#12302B;color:#5EEAD4;border:1px solid #1F6F63'>"
                        "● Snowflake · RESILIENCE_REWIRED_DB · RR_WH</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='rr-status' style='background:#33240F;color:#FFD166;border:1px solid #7A5A1E'>"
                        "● Local CSV fallback — Snowflake unavailable</div>", unsafe_allow_html=True)
            if repo.connection_error:
                st.caption(repo.connection_error[:200])
        page = _nav_menu()
        st.markdown("---")
        st.session_state["sidebar_account"] = st.session_state["active_account_id"]
        st.selectbox("Active account", accounts, format_func=lambda v: f"#{v}", key="sidebar_account",
                              on_change=lambda: st.session_state.update(active_account_id=int(st.session_state["sidebar_account"])))
        st.caption("Click any dot or bar on a chart to drill in. The active account follows you across pages.")

    RENDER[page](repo)


main()
