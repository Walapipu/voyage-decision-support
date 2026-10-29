"""Reusable chat panel for the dashboard and full assistant view."""
import streamlit as st
from html import escape
from voyage.ui import render_evidence


def clear_chat():
    st.session_state.chat_generation = st.session_state.get('chat_generation', 0) + 1
    st.session_state.messages = []
    st.session_state.pending = None
    st.session_state.chat_error = None
    st.session_state.force_comparison = False


def start_new_chat():
    clear_chat()
    for key in ('selected_vessel', 'selected_cargo', 'selected_lift'):
        st.session_state[key] = None


def render_chat(case, compact=False):
    from voyage.chat import chat_reply

    for key, value in {"messages": [], "pending": None, "chat_error": None}.items():
        if key not in st.session_state:
            st.session_state[key] = value
    generation = st.session_state.get('chat_generation', 0)
    # Remount the scrolling panel as well as the composer on New chat.
    with st.container(height=400, border=False, key=f"chat_scroll_{generation}"):
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
            progress = st.empty()
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
        selection = {key: st.session_state.get(key) for key in
                     ('selected_vessel', 'selected_cargo', 'selected_lift', 'price_period')}
        context = {"role": "system", "content": f'Current UI selections: {selection}. None means unselected; no complete voyage is selected unless vessel, cargo and lift are all present. Do not invent missing selections. Answer conceptual voyage and freight questions normally; redirect unrelated questions to OceanFlow support. Ask for any missing inputs needed for a calculation unless the user supplies them in their message. Run tools for numeric answers; UI selections are not calculation results.'}
        try:
            with progress, st.spinner("Shipping…"):
                answer = chat_reply(history + [context, question], force_comparison=st.session_state.get("force_comparison", False))
            if generation == st.session_state.get('chat_generation', 0):
                st.session_state.messages.extend([question, {"role": "assistant", **answer}])
                st.session_state.pending = None
                st.session_state.chat_error = None
                st.session_state.force_comparison = False
        except ValueError as exc:
            if generation == st.session_state.get('chat_generation', 0):
                st.session_state.chat_error = str(exc)
        st.rerun()
