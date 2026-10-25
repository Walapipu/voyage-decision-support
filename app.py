"""OceanFlow dashboard. Run: python -m streamlit run app.py"""
from pathlib import Path
import pandas as pd
import streamlit as st

from voyage.data import load_tables
from voyage.dashboard_data import dashboard_case
from voyage.dashboard import (apply_theme, heading, summary_cards, fleet_panel,
    route_map, freight_panel, voyage_summary, comparison_table, economics, timeline,
    requirements_notice, result_frame)
from voyage.chat_view import render_chat, clear_chat
from voyage.decision import CONVENTIONS
from voyage.openrouter import load_settings
from voyage.ui import render_evidence
from voyage.profile import toggle_theme, profile_menu

st.set_page_config(page_title="OceanFlow · Voyage Decision Support", page_icon="🌊", layout="wide", initial_sidebar_state="expanded")
if st.session_state.get("logged_out"):
    st.title("Session ended")
    st.write("Your local profile and conversation were cleared. This prototype has no account authentication.")
    if st.button("Start a new local session"):
        st.session_state.logged_out = False
        st.rerun()
    st.stop()
for key, value in {"dark_mode":True, "selected_vessel":"MF-02", "selected_cargo":"CC-02", "selected_lift":164000, "price_period":"2026-03"}.items():
    if key not in st.session_state:
        st.session_state[key] = value

def reset_lift():
    row = next(c for c in load_tables()["committed_cargoes"] if c["cargo_id"] == st.session_state.selected_cargo)
    st.session_state.selected_lift = int(row["nominal_quantity_tonnes"])

with st.sidebar:
    st.html('<div class="brand"><div class="brandmark">≈</div><div><b>OceanFlow</b><small>Voyage Decision Support</small></div></div>')
    page = st.radio("Navigation", ["Dashboard", "AI Assistant", "Voyages", "Fleet", "Freight", "Ports", "Analytics", "Reports", "Documents", "Settings"], label_visibility="collapsed")
    st.caption("Project 3 · Frozen synthetic case")

tables = load_tables()
with st.container(key="topbar"):
    search_col, period_col, user_col, theme_col = st.columns([6, 2, 1.7, .5], vertical_alignment="center")
    with search_col:
        query = st.text_input("Search vessels, ports or cargoes", placeholder="Search vessels, ports or cargoes…", label_visibility="collapsed").strip().lower()
    with period_col:
        st.selectbox("Bunker price month", sorted({r["period"] for r in tables["bunker_forward_curve"]}), key="price_period", label_visibility="collapsed")
    with theme_col:
        st.button("", icon=":material/dark_mode:", key="theme_button", help="Switch between dark and light mode", on_click=toggle_theme)
    with user_col:
        profile_menu()
apply_theme(st.session_state.dark_mode)

with st.container(key="workspace"):
    vessel_col, cargo_col, lift_col, note_col = st.columns([1.2, 1.2, 1.4, 3], vertical_alignment="bottom")
    with vessel_col:
        st.selectbox("Selected vessel", [v["vessel_id"] for v in tables["managed_vessels"]], key="selected_vessel")
    with cargo_col:
        st.selectbox("Committed cargo", [c["cargo_id"] for c in tables["committed_cargoes"]], key="selected_cargo", on_change=reset_lift)
    with lift_col:
        st.number_input("Selected lift (tonnes)", min_value=1, max_value=1000000, step=500, key="selected_lift")
    with note_col:
        st.caption("Frozen case · economical speeds · USD · all panels follow this selection")

case = dashboard_case(st.session_state.selected_cargo, st.session_state.selected_lift, st.session_state.price_period, st.session_state.selected_vessel)

if page == "Dashboard":
    summary_cards(case)
    with st.container(key="dashboard_grid"):
        fleet, assistant, planning = st.columns([1.05, 2.65, 1.4], gap="small")
        with fleet, st.container(border=True, key="fleet_panel"):
            fleet_panel(case, query)
        with assistant, st.container(border=True, key="assistant_panel"):
            title, new = st.columns([3,1])
            with title:
                heading("AI Voyage Assistant", "Python engine + OpenRouter")
            with new:
                st.button("New conversation", on_click=clear_chat)
            def dashboard_intro():
                voyage_summary(case, compact=True)
                with st.expander("Compare managed vessels", expanded=True):
                    comparison_table(case, compact=True)
                with st.expander("Revenue, costs and bunker consumption"):
                    economics(case)
            render_chat(case, compact=True, intro=dashboard_intro)
        with planning:
            route_map(case)
            with st.container(border=True, key="freight_panel"):
                freight_panel(case, query)
    with st.container(border=True, key="timeline_panel"):
        timeline(case)

elif page == "AI Assistant":
    with st.container(key="assistant_full"):
        title, new = st.columns([5,1])
        with title:
            heading("AI Voyage Assistant", "Grounded in Python tool results")
        with new:
            st.button("New conversation", on_click=clear_chat)
        render_chat(case)

elif page == "Voyages":
    heading("Voyage economics", "Selected voyage and managed alternatives")
    voyage_summary(case)
    comparison_table(case)
    with st.container(border=True):
        economics(case)
    with st.container(border=True, key="timeline_panel"):
        timeline(case)
    with st.expander("Full engine output and methodology"):
        st.json({"result":case["row"], "conventions": CONVENTIONS})

elif page in ("Fleet", "Freight", "Ports"):
    heading(page + " data", "Original frozen source records")
    table_names = {"Fleet":["managed_vessels","market_vessels"], "Freight":["committed_cargoes","market_cargoes"], "Ports":["ports"]}[page]
    if page == "Freight":
        st.info("Market freight rates of zero are unquoted inputs, not free freight. No booking or completion statuses are supplied.")
    for name in table_names:
        st.subheader(name.replace("_", " ").title())
        frame = pd.DataFrame(tables[name])
        if name == "market_cargoes":
            frame["contract_freight_rate_usd_per_tonne"] = "Quote needed"
        if query:
            frame = frame[frame.astype(str).apply(lambda row: query in " ".join(row).lower(), axis=1)]
        st.html('<div class="table-wrap" style="max-height:550px;overflow:auto">'+frame.to_html(index=False, escape=True, classes="ocean-table", border=0)+'</div>')

elif page == "Analytics":
    heading("Voyage comparisons", "Current cargo, lift and price month")
    render_evidence([{"tool":"compare_vessels", "result":case["comparison"]}])
    requirements_notice()
    st.warning("Bunker-price shocks, port-delay scenarios and recommendation-switch thresholds are required by the brief and remain to be built. The month selector changes frozen forward prices; it is not a substitute for scenario analysis.")

elif page == "Reports":
    heading("Export calculated results", "Includes feasibility flags and pricing period")
    comparison_table(case)
    st.download_button("Download voyage comparison CSV", result_frame(case).to_csv(index=False).encode("utf-8"), file_name=f'{st.session_state.selected_cargo}_{st.session_state.price_period}_comparison.csv', mime="text/csv")
    st.download_button("Download methodology", "\n".join(f'{k}: {v}' for k,v in CONVENTIONS.items()), file_name="voyage_methodology.txt")

elif page == "Documents":
    heading("Project documentation", "Requirements and calculation conventions")
    doc = st.selectbox("Document", ["Metric coverage", "Architecture", "Source dictionary", "Image and map credits"])
    paths = {"Metric coverage":"docs/metric_coverage.md", "Architecture":"docs/architecture.md", "Source dictionary":"data/raw/DATA_DICTIONARY.md", "Image and map credits":"docs/asset_credits.md"}
    st.markdown((Path(__file__).resolve().parent / paths[doc]).read_text(encoding="utf-8"))

elif page == "Settings":
    heading("Settings and assumptions")
    st.write("Use the moon button at the right of the top bar to switch themes. Your selection persists for this browser session. Profile settings and local-session logout are in the name dropdown.")
    try:
        _, model = load_settings()
        st.success("OpenRouter key configured on the server.")
        st.code(model)
    except ValueError as exc:
        st.error(str(exc))
    st.json(CONVENTIONS)
    st.caption("The API key is excluded from Git and is not exposed by this screen. Market economics, sensitivity analysis and fleet allocation are not enabled yet.")
