"""Run with: python -m streamlit run app.py"""

import streamlit as st

from voyage.openrouter import load_settings
from voyage.chat import chat_reply
from voyage.data import load_tables
from voyage.decision import compare_vessels
from voyage.ui import render_evidence

st.set_page_config(page_title="Voyage Assistant", page_icon="🚢", layout="centered")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None
if "chat_error" not in st.session_state:
    st.session_state.chat_error = None

with st.sidebar:
    st.title("Voyage Assistant")
    st.caption("Yi Heng · Project 3")
    page = st.radio("View", ["Chat", "Voyage calculator"])
    st.write("Ask about voyage planning or compare managed vessels for a committed cargo.")
    st.caption("Your messages are sent to OpenRouter and its model provider. Chat history stays in this browser session's server memory.")
    if st.button("New conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending = None
        st.session_state.chat_error = None
        st.rerun()
    with st.expander("Connection"):
        try:
            _, configured_model = load_settings()
            st.caption("API key configured locally.")
            st.code(configured_model, language=None)
            st.caption("Free models only. Availability and response speed can vary.")
        except ValueError as exc:
            st.error(str(exc))

if page == "Voyage calculator":
    st.title("Compare voyages")
    st.caption("This form calls the Python engine directly. No AI request is needed.")
    with st.form("voyage_calculator"):
        cargo = st.selectbox("Committed cargo", ["CC-01", "CC-02", "CC-03"], index=1)
        lift = st.number_input("Selected lift (tonnes)", min_value=1, max_value=1000000, value=164000, step=500)
        periods = sorted({r["period"] for r in load_tables()["bunker_forward_curve"]})
        period = st.selectbox("Bunker price month", periods, index=periods.index("2026-03"))
        run = st.form_submit_button("Compare four managed vessels")
    st.caption("CC = committed cargo; MF = managed vessel. Market vessels and cargoes need hire/freight quotes before economic comparisons.")
    if run:
        try:
            st.session_state.calculator_result = compare_vessels(cargo, lift, period)
        except ValueError as exc:
            st.session_state.pop("calculator_result", None)
            st.error(str(exc))
    if "calculator_result" in st.session_state:
        render_evidence([{"tool": "compare_vessels", "result": st.session_state.calculator_result}])
    st.stop()

st.title("Let's talk voyages")
st.caption("Understand the terms. Explore the decisions.")
st.info("Ask for a voyage calculation or comparison with a cargo lift in tonnes. Review the Python results and assumptions below the AI explanation.")

if not st.session_state.messages and not st.session_state.pending:
    st.markdown("Try **‘Compare the managed vessels for CC-02 at 164,000 tonnes’** or **‘What is the difference between TCE and contribution?’**")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("model"):
            st.caption("Answered by " + message["model"])
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

prompt = st.chat_input("Ask a shipping question…", max_chars=4000, disabled=bool(st.session_state.pending))
if prompt and prompt.strip():
    st.session_state.pending = prompt.strip()
    st.session_state.chat_error = None
    st.rerun()

if st.session_state.pending and (not st.session_state.chat_error or retry):
    question = {"role": "user", "content": st.session_state.pending}
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    try:
        with st.spinner("Waiting for the free model…"):
            answer = chat_reply(history + [question])
        st.session_state.messages.extend([question, {"role": "assistant", **answer}])
        st.session_state.pending = None
        st.session_state.chat_error = None
    except ValueError as exc:
        st.session_state.chat_error = str(exc)
    st.rerun()
