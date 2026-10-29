"""Reusable chat panel for the dashboard and full assistant view."""
import streamlit as st
from html import escape
from voyage.ui import render_evidence


def clear_chat():
    st.session_state.chat_generation = st.session_state.get('chat_generation', 0) + 1
    st.session_state.chat_reset_notice = True
    st.session_state.messages = []
    st.session_state.pending = None
    st.session_state.chat_error = None
    st.session_state.force_comparison = False


def request_review():
    st.session_state.pending = (f'Write an analyst review for cargo {st.session_state.selected_cargo} '
        f'at {st.session_state.selected_lift:,.0f} tonnes, using bunker month {st.session_state.price_period}. '
        f'Compare all managed vessels and discuss my selected vessel {st.session_state.selected_vessel}. '
        'Explain the earnings, cost drivers and main feasibility risk, then recommend the next action.')
    st.session_state.force_comparison = True
    st.session_state.chat_error = None


def render_chat(case, compact=False):
    from voyage.chat import chat_reply

    for key, value in {"messages": [], "pending": None, "chat_error": None}.items():
        if key not in st.session_state:
            st.session_state[key] = value
    with st.container(height=400, border=False, key="chat_scroll"):
        if st.session_state.pop('chat_reset_notice', False):
            st.success('New conversation started.')
        if not st.session_state.messages and not st.session_state.pending:
            name = escape(st.session_state.get('profile_name', 'Yi Heng'))
            st.html(f'<div class="chat-welcome"><h2>Hello, {name}.</h2><p>Ask me something.</p></div>')
        for message_index, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
                if message["role"] == "assistant" and message.get("evidence"):
                    st.markdown("**Analyst briefing**")
                st.markdown(message["content"])
                if message.get("notice"):
                    st.caption(message["notice"])
                if message.get("truncated"):
                    st.warning("The answer reached its response limit and may be incomplete.")
                render_evidence(message.get("evidence", []), key_prefix=f"reply_{message_index}")
        retry = False
        if st.session_state.pending:
            with st.chat_message("user"):
                st.markdown(st.session_state.pending)
            if st.session_state.chat_error:
                st.error(st.session_state.chat_error)
                retry = st.button("Retry question")
                if st.button("Discard question"):
                    st.session_state.pending = None
                    st.session_state.chat_error = None
                    st.rerun()
    with st.container(key="composer"):
        prompt = st.chat_input("Ask about voyages, freight, vessels or fuel…", key=f'chat_prompt_{st.session_state.get("chat_generation", 0)}', max_chars=4000, disabled=bool(st.session_state.pending))
    if prompt and prompt.strip():
        st.session_state.pending = prompt.strip()
        st.session_state.chat_error = None
        st.session_state.force_comparison = False
        st.rerun()
    if st.session_state.pending and (not st.session_state.chat_error or retry):
        question = {"role": "user", "content": st.session_state.pending}
        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        # Explicit UI selection, not fabricated tool evidence. The model still runs tools.
        r = case["row"]
        context = {"role": "system", "content": f'The user currently selected vessel {r["vessel_id"]}, cargo {r["cargo_id"]}, lift {r["selected_lift_tonnes"]} tonnes and bunker month {r["bunker_price_period"]}. Use these for references to this voyage. Run tools for numeric answers; this selection is not a calculation result.'}
        try:
            with st.spinner("Preparing your voyage analysis…"):
                answer = chat_reply(history + [context, question], force_comparison=st.session_state.get("force_comparison", False))
            st.session_state.messages.extend([question, {"role": "assistant", **answer}])
            st.session_state.pending = None
            st.session_state.chat_error = None
            st.session_state.force_comparison = False
        except ValueError as exc:
            st.session_state.chat_error = str(exc)
        st.rerun()
