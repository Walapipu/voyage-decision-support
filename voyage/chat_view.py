"""Reusable chat panel for the dashboard and full assistant view."""
import streamlit as st
from voyage.ui import render_evidence


def clear_chat():
    st.session_state.messages = []
    st.session_state.pending = None
    st.session_state.chat_error = None


def render_chat(case, compact=False):
    from voyage.chat import chat_reply

    for key, value in {"messages": [], "pending": None, "chat_error": None}.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if not st.session_state.messages and not st.session_state.pending:
        st.caption("Ask why one vessel performs better, or request a calculation with a lift in tonnes. No AI request runs until you send a question.")
    with st.container(height=230 if compact and st.session_state.messages else "content", border=False):
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if message.get("model"):
                    st.caption("AI explanation · " + message["model"])
                if message.get("truncated"):
                    st.warning("The answer reached its response limit and may be incomplete.")
                render_evidence(message.get("evidence", []))
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
    prompt = st.chat_input("Ask about voyages, freight, vessels or fuel…", max_chars=4000, disabled=bool(st.session_state.pending))
    if prompt and prompt.strip():
        st.session_state.pending = prompt.strip()
        st.session_state.chat_error = None
        st.rerun()
    if st.session_state.pending and (not st.session_state.chat_error or retry):
        question = {"role": "user", "content": st.session_state.pending}
        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        # Explicit UI selection, not fabricated tool evidence. The model still runs tools.
        r = case["row"]
        context = {"role": "system", "content": f'The user currently selected vessel {r["vessel_id"]}, cargo {r["cargo_id"]}, lift {r["selected_lift_tonnes"]} tonnes and bunker month {r["bunker_price_period"]}. Use these for references to this voyage. Run tools for numeric answers; this selection is not a calculation result.'}
        try:
            with st.spinner("Asking the free model and checking Python tools…"):
                answer = chat_reply(history + [context, question])
            st.session_state.messages.extend([question, {"role": "assistant", **answer}])
            st.session_state.pending = None
            st.session_state.chat_error = None
        except ValueError as exc:
            st.session_state.chat_error = str(exc)
        st.rerun()
    st.caption("AI explanations require review. Numeric tool results come from Python. Messages and requested results are sent to OpenRouter.")
