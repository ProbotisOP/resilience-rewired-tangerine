"""Cross-page navigation driven by chart clicks."""

from typing import Any, Optional

import streamlit as st


def open_account(account_id: int, page_slug: str = "account") -> None:
    """Focus an account and jump to a page (the sidebar reads the page from the query string)."""
    st.session_state["active_account_id"] = int(account_id)
    st.query_params["page"] = page_slug
    st.rerun()


def new_click(event: Optional[Any], key: str) -> Optional[Any]:
    """Return a chart click only the first time it is seen (component values persist across reruns)."""
    if not event:
        return None
    marker = repr(event)
    seen_key = f"_seen_click_{key}"
    if st.session_state.get(seen_key) == marker:
        return None
    st.session_state[seen_key] = marker
    return event
