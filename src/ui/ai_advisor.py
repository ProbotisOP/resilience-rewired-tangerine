"""
Screen 6: TANG, Tangerine's resilience assistant — help chatbot backed by the RESILIENCE_INTELLIGENCE_AGENT.
"""

from typing import Any

import streamlit as st

from src.services.baseline_metrics import compute_official_baseline

TOOL_LABELS = {
    "financial_analyst": "Cortex Analyst · semantic view",
    "system_execute_sql": "SQL execution",
    "shock_calculator": "Deterministic shock function",
    "documentation_search": "Cortex Search · evidence & guide",
}
SUGGESTIONS = [
    "Why is this account financially vulnerable?",
    "What changed in this account over its latest six months?",
    "Which observed factors contribute most to the future stress signal?",
    "What happens if the customer's monthly money-in falls by 45%?",
    "How much monthly improvement is needed for a six-month runway under EI at 55%?",
    "Compare this account with other accounts that have similar money in.",
    "What support conversation could an advisor start, and what can't be promised?",
    "How is runway calculated, and what are its limits?",
]


def render_ai_advisor(repo: Any):
    account_id = st.session_state.get("active_account_id")
    meta = repo.get_account_meta(account_id) or {}
    base = compute_official_baseline(account_id, repo.get_monthly_summary(account_id), meta)

    st.markdown("<div class='tang-hero'><div class='tang-logo'>🍊</div><div><div class='tang-name'>TANG</div>"
                "<div class='tang-sub'>Tangerine's resilience assistant · powered by Snowflake Cortex</div></div></div>",
                unsafe_allow_html=True)
    st.caption("TANG answers from Snowflake tools only: Cortex Analyst over the financial semantic view, the deterministic "
               "shock function, and Cortex Search over the project evidence and support guide. Every statement is labelled "
               "OBSERVED FACT, CALCULATED, SIMULATED, MODEL ESTIMATE or PROPOSED ACTION.")
    prob = meta.get("ml_stress_probability")
    st.markdown(
        f"<div class='rr-verdict'><span>Talking about</span><b>Account #{account_id}</b> · buffer ${base.B:,.2f} · "
        f"runway {base.baseline_runway_label}" + (f" · stress estimate {prob * 100:.1f}%" if prob is not None else "") + "</div>",
        unsafe_allow_html=True)

    if not getattr(repo, "is_connected", False):
        st.warning("TANG needs the Snowflake connection; the app is running on local CSVs.")
        return

    history_key = f"chat_{account_id}"
    history = st.session_state.setdefault(history_key, [])

    top = st.columns([5, 1])
    top[0].caption("Questions are scoped to the active account; change it from the sidebar or any chart.")
    if top[1].button("Clear chat", use_container_width=True, disabled=not history):
        st.session_state[history_key] = []
        st.rerun()

    queued = None
    if not history:
        cols = st.columns(2)
        for i, q in enumerate(SUGGESTIONS):
            if cols[i % 2].button(q, key=f"sugg_{i}", use_container_width=True):
                queued = q

    for msg in history:
        with st.chat_message(msg["role"], avatar="🧑‍💼" if msg["role"] == "user" else "🍊"):
            st.markdown(msg["content"])
            if msg.get("tools"):
                st.caption("Tools used: " + " → ".join(TOOL_LABELS.get(t["name"], t["name"]) for t in msg["tools"]))
            for sql in msg.get("sql", []):
                with st.expander("SQL evidence"):
                    st.code(sql, language="sql")

    prompt = st.chat_input(f"Ask TANG about account #{account_id}, a what-if, or the portfolio…") or queued
    if prompt:
        history.append({"role": "user", "content": prompt})
        with st.chat_message("user", avatar="🧑‍💼"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🍊"):
            with st.status("TANG is thinking…", expanded=False) as status:
                try:
                    reply = repo.ask_agent([{"role": m["role"], "content": m["content"]} for m in history[-10:]],
                                           account_id=account_id)
                except Exception as error:
                    reply = {"text": f"TANG could not answer: {type(error).__name__}: {error}", "tools": [], "sql": []}
                status.update(label="Done" if reply.get("tools") else "Answered", state="complete")
            st.markdown(reply["text"])
            if reply.get("tools"):
                st.caption("Tools used: " + " → ".join(TOOL_LABELS.get(t["name"], t["name"]) for t in reply["tools"]))
            for sql in reply.get("sql", []):
                with st.expander("SQL evidence"):
                    st.code(sql, language="sql")
        history.append({"role": "assistant", "content": reply["text"], "tools": reply.get("tools", []),
                        "sql": reply.get("sql", [])})
