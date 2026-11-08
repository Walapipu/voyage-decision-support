"""Reusable chat panel for the dashboard and full assistant view."""
import re
from html import escape

import streamlit as st
from voyage.ui import render_evidence


def clear_chat():
    st.session_state.chat_generation = st.session_state.get('chat_generation', 0) + 1
    st.session_state.messages = []
    st.session_state.pending = None
    st.session_state.chat_error = None
    st.session_state.force_comparison = False
    st.session_state.pop("selection_from_chat", None)


def start_new_chat():
    clear_chat()
    st.session_state.close_voyage_selectors = True
    for key in ('selected_vessel', 'selected_cargo', 'selected_lift'):
        st.session_state[key] = None


def selection_from_evidence(evidence):
    """Choose the last calculated voyage or the lead vessel in its comparison."""
    for item in reversed(evidence):
        if item["tool"] not in {"compare_vessels", "calculate_voyage"}:
            continue
        rows = item["result"].get("rows")
        if not rows:
            continue
        # Comparisons already rank feasible voyages first, then contribution.
        row = rows[0]
        return {"selected_vessel": row["vessel_id"], "selected_cargo": row["cargo_id"],
                "selected_lift": float(row["selected_lift_tonnes"]),
                "price_period": row["bunker_price_period"]}
    return None


MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}


def selection_from_prompt(text, state):
    """Read cargo, vessel, lift and month straight from a typed question, so the KPIs and
    heat map follow the conversation even before (or without) a model tool call.
    Only explicit mentions are used; a missing vessel is filled by the engine's top
    feasible candidate for that cargo and lift."""
    from voyage.data import load_tables
    from voyage.decision import compare_vessels

    tables = load_tables()
    lowered = text.lower()
    cargoes = {c["cargo_id"]: c for c in tables["committed_cargoes"]}
    vessels = {v["vessel_id"] for v in tables["managed_vessels"]}
    periods = {r["period"] for r in tables["bunker_forward_curve"]}
    found = {}
    if match := re.search(r"\bcc[\s-]?0*(\d{1,2})\b", lowered):
        found["selected_cargo"] = f"CC-{int(match[1]):02d}"
    if match := re.search(r"\bmf[\s-]?0*(\d{1,2})\b", lowered):
        found["selected_vessel"] = f"MF-{int(match[1]):02d}"
    for match in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(k\b|kt\b|thousand\b)?\s*(t\b|mt\b|tonnes?\b|tons?\b)?", lowered):
        if not (match[2] or match[3] or "," in match[1]):
            continue
        amount = float(match[1].replace(",", "")) * (1000 if match[2] else 1)
        if 1000 <= amount <= 1_000_000:
            found["selected_lift"] = amount
            break
    if match := re.search(r"\b(20\d\d)-(\d{2})\b", lowered):
        month = f"{match[1]}-{match[2]}"
    elif match := re.search(r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?\s*(20\d\d)?", lowered):
        # "may" is only a month when a year follows it ("May 2026", not "may I").
        month = None if match[1] == "may" and not match[2] else f"{match[2] or '2026'}-{MONTHS[match[1][:3]]:02d}"
    else:
        month = None
    if month in periods:
        found["price_period"] = month
    found = {k: v for k, v in found.items() if (k != "selected_cargo" or v in cargoes) and (k != "selected_vessel" or v in vessels)}
    cargo = found.get("selected_cargo") or state.get("selected_cargo")
    if not found or cargo is None:
        return None
    lift = found.get("selected_lift") or state.get("selected_lift")
    if cargo != state.get("selected_cargo") and "selected_lift" not in found:
        lift = float(cargoes[cargo]["nominal_quantity_tonnes"])  # the contract quantity, not a guess
    if lift and "selected_vessel" not in found:
        rows = compare_vessels(cargo, lift, found.get("price_period") or state.get("price_period") or "2026-03")["rows"]
        found["selected_vessel"] = rows[0]["vessel_id"]
    return {**found, "selected_cargo": cargo, "selected_lift": lift}


def selection_label():
    state = st.session_state
    lift = state.get("selected_lift")
    parts = [state.get("selected_vessel"), state.get("selected_cargo"),
             f"{lift:,.0f} t" if lift else None, state.get("price_period")]
    chosen = [p for p in parts if p]
    return "Voyage inputs" + (" · " + " · ".join(chosen) if chosen else "")


def render_chat(controls=None):
    from voyage.chat import chat_reply

    for key, value in {"messages": [], "pending": None, "chat_error": None}.items():
        if key not in st.session_state:
            st.session_state[key] = value
    generation = st.session_state.get('chat_generation', 0)
    # Remount the scrolling panel as well as the composer on New chat.
    with st.container(height=400, border=False, key=f"chat_scroll_{generation}"):
        if not st.session_state.messages and not st.session_state.pending:
            name = escape(st.session_state.get('profile_name', 'Yi Heng'))
            st.html(f'<div class="chat-welcome"><h2>Hello, {name}.</h2><p>Ask about a voyage, cargo or fuel plan</p></div>')
        for message_index, message in enumerate(st.session_state.messages):
            with st.chat_message(message["role"]):
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
        if controls:
            # Collapsed by default and after every question, so answers keep the room.
            with st.expander(selection_label(), icon=":material/tune:", key="voyage_selectors", on_change="rerun"):
                controls()
        prompt = st.chat_input("Ask about a voyage, e.g. CC-02 at 164,000 t", key=f'chat_prompt_{st.session_state.get("chat_generation", 0)}', max_chars=4000, disabled=bool(st.session_state.pending))
    if prompt and prompt.strip():
        st.session_state.pending = prompt.strip()
        typed = selection_from_prompt(prompt, st.session_state)
        if typed:
            st.session_state.selection_from_chat = typed
        st.session_state.close_voyage_selectors = True
        st.session_state.chat_error = None
        st.session_state.force_comparison = False
        st.rerun()
    if st.session_state.pending and (not st.session_state.chat_error or retry):
        question = {"role": "user", "content": st.session_state.pending}
        history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
        # Explicit UI selection, not fabricated tool evidence. The model still runs tools.
        selection = {key: st.session_state.get(key) for key in
                     ('selected_vessel', 'selected_cargo', 'selected_lift', 'price_period')}
        context = {"role": "system", "content": f'Current UI selections: {selection}. None means unselected; no complete voyage is selected unless vessel, cargo and lift are all present. Do not invent missing selections. Answer conceptual voyage and freight questions normally; redirect unrelated questions to KingFish support. Ask for any missing inputs needed for a calculation unless the user supplies them in their message. Run tools for numeric answers; UI selections are not calculation results.'}
        try:
            with progress, st.spinner("Shipping…"):
                answer = chat_reply(history + [context, question], force_comparison=st.session_state.get("force_comparison", False))
            if generation == st.session_state.get('chat_generation', 0):
                st.session_state.messages.extend([question, {"role": "assistant", **answer}])
                selection = selection_from_evidence(answer.get("evidence", []))
                if selection:
                    st.session_state.selection_from_chat = selection
                st.session_state.pending = None
                st.session_state.chat_error = None
                st.session_state.force_comparison = False
        except ValueError as exc:
            if generation == st.session_state.get('chat_generation', 0):
                st.session_state.chat_error = str(exc)
        st.rerun()
