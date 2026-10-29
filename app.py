"""OceanFlow dashboard. Run: python -m streamlit run app.py"""
from pathlib import Path
from contextlib import nullcontext
import pandas as pd
import streamlit as st

from voyage.assets import brand_logo_uri
from voyage.data import load_tables, index
from voyage.dashboard_data import dashboard_case
from voyage.dashboard import (apply_theme, heading, summary_cards, fleet_panel,
    route_map, freight_panel, voyage_summary, comparison_table, economics, timeline,
    requirements_notice, result_frame)
from voyage.chat_view import render_chat, start_new_chat
from voyage.policy import load_policy, conventions
from voyage.openrouter import load_settings
from voyage.ui import render_evidence
from voyage.profile import toggle_theme, profile_menu

st.set_page_config(page_title="OceanFlow · Voyage Decision Support", page_icon="🌊", layout="wide", initial_sidebar_state="expanded")
if st.session_state.get("logged_out"):
    st.title("Session ended")
    st.write("Your profile and conversation were cleared for this session.")
    if st.button("Start new session"):
        st.session_state.logged_out = False
        st.rerun()
    st.stop()
for key, value in {"dark_mode":True, "selected_vessel":None, "selected_cargo":None, "selected_lift":None, "price_period":"2026-03"}.items():
    if key not in st.session_state:
        st.session_state[key] = value

def reset_lift():
    st.session_state.selected_lift = None

with st.sidebar:
    st.html(f'<div class="brand"><img class="brandmark" src="{brand_logo_uri()}" alt="OceanFlow crown"/><div><b>OceanFlow</b><small>Voyage Decision Support</small></div></div>')
    page = st.radio("Navigation", ["Dashboard", "AI Assistant", "Voyages", "Fleet", "Freight", "Ports", "Analytics", "Reports", "Documents", "Settings"], label_visibility="collapsed")

tables = load_tables()
with st.container(key="topbar"):
    search_col, period_col, theme_col, user_col = st.columns([6, 1.8, .55, 1.8], vertical_alignment="center")
    with search_col:
        query = st.text_input("Search vessels, ports or cargoes", placeholder="Search vessels, ports or cargoes…", label_visibility="collapsed").strip().lower()
    with period_col:
        st.selectbox("Bunker price month", sorted({r["period"] for r in tables["bunker_forward_curve"]}), key="price_period", label_visibility="collapsed")
    with theme_col:
        st.button("", icon=":material/dark_mode:", key="theme_button", on_click=toggle_theme)
    with user_col:
        profile_menu()
apply_theme(st.session_state.dark_mode)

with st.container(key="workspace"):
    vessel_col, cargo_col, lift_col = st.columns([1, 1, 1], vertical_alignment="bottom")
    with vessel_col:
        st.selectbox("Selected vessel", [None] + [v["vessel_id"] for v in tables["managed_vessels"]], format_func=lambda v: v or "--", key="selected_vessel", label_visibility="collapsed", placeholder="--")
    with cargo_col:
        st.selectbox("Committed cargo", [None] + [c["cargo_id"] for c in tables["committed_cargoes"]], format_func=lambda c: c or "--", key="selected_cargo", on_change=reset_lift, label_visibility="collapsed", placeholder="--")
    with lift_col:
        st.number_input("Selected lift (tonnes)", min_value=1, max_value=1000000, value=None, step=500, key="selected_lift", label_visibility="collapsed", placeholder="--")

has_selection = all(st.session_state[k] is not None for k in ("selected_vessel", "selected_cargo", "selected_lift"))
case = dashboard_case(st.session_state.selected_cargo, st.session_state.selected_lift, st.session_state.price_period, st.session_state.selected_vessel) if has_selection else None
catalog = {"tables": tables, "ports": index(tables["ports"], "port_code")}

with st.container(key="page_content") if page not in ("Dashboard", "AI Assistant") else nullcontext():
    if page == "Dashboard":
        summary_cards(case)
        with st.container(key="dashboard_grid"):
            fleet, assistant, planning = st.columns([1.05, 2.65, 1.4], gap="small")
            with fleet, st.container(border=True, key="fleet_panel"):
                fleet_panel(catalog, query)
            with assistant, st.container(border=True, key="assistant_panel"):
                title, new = st.columns([1, .12], vertical_alignment="center")
                with title:
                    heading("AI Voyage Assistant")
                with new:
                    st.button("New chat", icon=":material/edit_square:", key="new_conversation", on_click=start_new_chat)
                render_chat(case, compact=True)
            with planning, st.container(key="planning_panel"):
                if case:
                    route_map(case)
                else:
                    with st.container(key="route_map"):
                        heading("Route Map")
                        st.caption("Select a vessel, cargo and tonnage to view a route.")
                with st.container(border=True, key="freight_panel"):
                    freight_panel(catalog, query)
        with st.container(border=True, key="timeline_panel"):
            if case:
                timeline(case)
            else:
                heading("Voyage Timeline")
                st.caption("No voyage selected.")

    elif page == "AI Assistant":
        with st.container(key="assistant_full"):
            title, new = st.columns([1, .06], vertical_alignment="center")
            with title:
                heading("AI Voyage Assistant", "Commercial analysis")
            with new:
                st.button("New chat", icon=":material/edit_square:", key="new_conversation", on_click=start_new_chat)
            render_chat(case)

    elif page in ("Voyages", "Analytics", "Reports") and not case:
        heading(page)
        st.info("Select a vessel, cargo and tonnage to view voyage results.")

    elif page == "Voyages":
        heading("Voyage economics", "Selected voyage and managed alternatives")
        voyage_summary(case)
        comparison_table(case)
        with st.container(border=True):
            economics(case)
        with st.container(border=True, key="timeline_panel"):
            timeline(case)
        with st.expander("Full engine output and methodology"):
            st.json({"result":case["row"], "conventions": case['comparison']['conventions']})

    elif page in ("Fleet", "Freight", "Ports"):
        heading(page + " data", "Vessels, cargoes and ports")
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
        st.warning("Scenario analysis and recommendation-switch thresholds are not available yet. The month selector chooses a pricing period.")

    elif page == "Reports":
        heading("Export calculated results", "Includes feasibility flags and pricing period")
        comparison_table(case)
        st.download_button("Download voyage comparison CSV", result_frame(case).to_csv(index=False).encode("utf-8"), file_name=f'{st.session_state.selected_cargo}_{st.session_state.price_period}_comparison.csv', mime="text/csv")
        st.download_button("Download methodology", "\n".join(f'{k}: {v}' for k,v in case['comparison']['conventions'].items()), file_name="voyage_methodology.txt")

    elif page == "Documents":
        heading("Documentation", "Methodology and references")
        doc = st.selectbox("Document", ["Modelling assumptions", "Metric coverage", "Architecture", "Source dictionary", "Image and map credits"])
        paths = {"Modelling assumptions":"docs/assumptions.md", "Metric coverage":"docs/metric_coverage.md", "Architecture":"docs/architecture.md", "Source dictionary":"data/raw/DATA_DICTIONARY.md", "Image and map credits":"docs/asset_credits.md"}
        st.markdown((Path(__file__).resolve().parent / paths[doc]).read_text(encoding="utf-8"))
        if doc == 'Modelling assumptions':
            st.write('Active engine policy')
            st.json(conventions(load_policy()))

    elif page == "Settings":
        heading("Settings and assumptions")
        st.write("Use the moon button at the right of the top bar to switch themes. Your selection persists for this browser session. Profile settings and local-session logout are in the name dropdown.")
        try:
            _, model = load_settings()
            st.success("OpenRouter key configured on the server.")
            st.code(model)
        except ValueError as exc:
            st.error(str(exc))
        st.json(conventions(load_policy()))
        st.caption("The API key is excluded from Git and is not exposed by this screen. Market economics, sensitivity analysis and fleet allocation are not enabled yet.")
