"""KingFish dashboard. Run: python -m streamlit run app.py"""
import json
from pathlib import Path
import pandas as pd
import streamlit as st

from voyage.assets import brand_logo_uri
from voyage.data import load_tables, index
from voyage.dashboard_data import dashboard_case, candidates_case
from voyage.decision import OBJECTIVES
from voyage.voyages_view import voyages_page
from voyage.dashboard import (apply_theme, heading, voyage_summary, comparison_table, economics, timeline, result_frame)
from voyage.plan import build_plan, plan_summary
from voyage import overview
from voyage.chat_view import render_chat, start_new_chat
from voyage.commands import COMMANDS
from voyage.policy import load_policy, conventions
from voyage.openrouter import load_settings
from voyage.report import analytics_report
from voyage.ui import render_evidence
from voyage.analytics_view import analytics_page
from voyage.profile import toggle_theme, profile_menu

st.set_page_config(page_title="KingFish · Voyage Decision Support", page_icon=str(Path(__file__).resolve().parent / "assets/oceanflow-crown.png"), layout="wide", initial_sidebar_state="auto")
if st.session_state.get("logged_out"):
    st.title("Session ended")
    st.write("Your profile and conversation were cleared for this session.")
    if st.button("Start new session"):
        st.session_state.logged_out = False
        st.rerun()
    st.stop()
for key, value in {"dark_mode":True, "selected_vessel":None, "selected_cargo":None, "selected_lift":None, "price_period":None, "map_view":"All voyages"}.items():
    if key not in st.session_state:
        st.session_state[key] = value
# The Overview has no vessel, cargo or lift widgets; re-assigning keeps these values when
# their widgets are not drawn on a run instead of letting Streamlit discard them.
for key in ("selected_vessel", "selected_cargo", "selected_lift", "price_period", "map_view"):
    st.session_state[key] = st.session_state[key]

# Apply chat results before Streamlit instantiates the bound selector widgets.
selection_from_chat = st.session_state.pop("selection_from_chat", None)
if selection_from_chat:
    st.session_state.update(selection_from_chat)
    st.session_state.voyage_port = st.session_state.voyage_query = None
# A chat shortcut such as /voyages switches page; this must happen before the navigation radio exists.
if goto_page := st.session_state.pop("goto_page", None):
    st.session_state.page = goto_page
if st.session_state.pop("close_voyage_selectors", False):
    st.session_state.voyage_selectors = False


def reset_lift():
    st.session_state.selected_lift = None
    # A cargo picked in the top bar ends any Voyages search in progress.
    st.session_state.voyage_port = st.session_state.voyage_query = None

with st.sidebar:
    st.html(f'<div class="brand"><img class="brandmark" src="{brand_logo_uri()}" alt="KingFish crown"/><div><b>KingFish</b><small>Voyage planner</small></div></div>')
    page = st.radio("Navigation", ["Overview", "AI Assistant", "Voyages", "Fleet", "Freight", "Ports", "Analytics", "Reports", "Documents", "Settings"], label_visibility="collapsed", key="page")
    with st.container(key="sidebar_foot"):
        user_col, theme_col = st.columns([1, .22], vertical_alignment="center", gap="small")
        with user_col:
            profile_menu()
        with theme_col:
            st.button("", icon=":material/dark_mode:", key="theme_button", on_click=toggle_theme)

tables = load_tables()
apply_theme(st.session_state.dark_mode)
# The Voyages search accepts free text; Streamlit labels that option "Add: …", which
# reads as creating a record. Relabel it while the search box has focus.
st.html("""<script>(() => {
  if (window.__kingfishSearchLabel) return; window.__kingfishSearchLabel = true;
  const relabel = () => {
    if (!document.activeElement || !document.activeElement.closest('.st-key-voyage_search')) return;
    document.querySelectorAll('[data-testid="stSelectboxVirtualDropdown"] [role="option"]').forEach(option => {
      const walker = document.createTreeWalker(option, NodeFilter.SHOW_TEXT);
      for (let node = walker.nextNode(); node; node = walker.nextNode())
        if (node.nodeValue.startsWith('Add: ')) node.nodeValue = 'Search all: ' + node.nodeValue.slice(5);
    });
  };
  // No hover tooltips anywhere: drop native title attributes as elements appear.
  const untitle = () => document.querySelectorAll('[title]').forEach(el => el.removeAttribute('title'));
  // Ask Shippy drawer. Opening and closing stay in the browser, so the drawer remains mounted
  // and the conversation and any unsent draft survive while it is closed.
  const body = document.body, drawer = () => document.querySelector('.st-key-shippy');
  const openShippy = () => {
    body.classList.add('shippy-open');
    setTimeout(() => drawer()?.querySelector('textarea')?.focus(), 160);
  };
  const closeShippy = () => {
    if (!body.classList.contains('shippy-open')) return;
    body.classList.remove('shippy-open');
    document.querySelector('.ask-shippy')?.focus();
  };
  document.addEventListener('click', event => {
    if (event.target.closest('[data-shippy-open]')) openShippy();
    else if (event.target.closest('[data-shippy-close]')) closeShippy();
    else if (body.classList.contains('shippy-open') && event.target.closest('[data-testid="stSidebar"]')) {
      // A click on the dimmed rail closes the drawer instead of navigating.
      event.preventDefault(); event.stopPropagation(); closeShippy();
    }
  }, true);
  // Slash shortcuts: typing "/" in a chat box lists them above it; click or Tab fills one in.
  const COMMANDS = __COMMANDS__;
  let menu = null;
  const menuOpen = () => menu && !menu.hidden;
  const hideMenu = () => { if (menuOpen()) menu.hidden = true; };
  const fill = (box, text) => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(box, text);
    box.dispatchEvent(new Event('input', {bubbles: true}));
    box.focus(); box.setSelectionRange(text.length, text.length);
  };
  const showMenu = box => {
    const word = box.value.slice(1).toLowerCase();
    const typed = box.value[0] === '/' && /^[a-z]*$/.test(word);
    const matches = typed ? COMMANDS.filter(c => c[0].slice(1).startsWith(word)) : [];
    if (!matches.length) return hideMenu();
    if (!menu) {
      menu = document.createElement('div'); menu.className = 'slash-menu'; menu.setAttribute('role', 'listbox');
      menu.addEventListener('mousedown', event => {
        const item = event.target.closest('[data-cmd]');
        if (item) { event.preventDefault(); fill(menu.box, item.dataset.cmd + ' '); }
      });
      document.body.append(menu);
    }
    menu.box = box;
    menu.replaceChildren(...matches.map(([name, example, what]) => {
      const row = document.createElement('div'), b = document.createElement('b'), s = document.createElement('span'), ex = document.createElement('small');
      row.className = 'slash-item'; row.dataset.cmd = name; row.setAttribute('role', 'option');
      b.textContent = name; s.textContent = what; ex.textContent = example; row.append(b, s, ex); return row;
    }));
    const r = box.closest('[data-testid="stChatInput"]').getBoundingClientRect();
    Object.assign(menu.style, {left: r.left + 'px', width: r.width + 'px', bottom: (innerHeight - r.top + 6) + 'px'});
    menu.hidden = false;
  };
  const chatBox = el => el instanceof HTMLTextAreaElement && el.closest('[data-testid="stChatInput"]') ? el : null;
  document.addEventListener('input', event => { const box = chatBox(event.target); if (box) showMenu(box); });
  document.addEventListener('focusout', event => { if (chatBox(event.target)) hideMenu(); });
  document.addEventListener('keydown', event => {
    if (menuOpen() && event.key === 'Tab' && chatBox(event.target)) {
      event.preventDefault(); fill(event.target, menu.firstChild.dataset.cmd + ' '); return;
    }
    if (event.key === 'Escape') { if (menuOpen()) { hideMenu(); return; } closeShippy(); }
  }, true);
  const syncDrawer = () => {
    const panel = drawer();
    // Guarded: classList.remove rewrites the class attribute even when the class is absent, which
    // re-fires the class observer below and loops forever once the drawer has left the page.
    if (!panel) { if (body.classList.contains('shippy-open')) body.classList.remove('shippy-open'); return; }
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-labelledby', 'shippy-title');
    panel.toggleAttribute('inert', !body.classList.contains('shippy-open'));
  };
  // Chat panels: jump to the newest message when one is added, and otherwise leave the scroll alone.
  // Charts in an answer draw a moment later, so the jump repeats briefly unless the user scrolls first.
  const seen = new WeakMap(), touched = new WeakMap();
  const followChat = () => document.querySelectorAll('[class*="st-key-chat_scroll_"]').forEach(box => {
    const count = box.querySelectorAll('[data-testid="stChatMessage"]').length;
    if (count === seen.get(box)) return;
    if (!seen.has(box)) ['wheel', 'touchstart', 'pointerdown', 'keydown'].forEach(type =>
      box.addEventListener(type, () => touched.set(box, performance.now()), {passive: true}));
    seen.set(box, count);
    if (!count) return;
    const asked = performance.now();
    [0, 150, 500, 1000].forEach(delay => setTimeout(() => {
      if ((touched.get(box) || 0) < asked) box.scrollTop = box.scrollHeight;
    }, delay));
  });
  new MutationObserver(() => { relabel(); untitle(); syncDrawer(); followChat(); }).observe(body, {childList: true, subtree: true, characterData: true});
  new MutationObserver(syncDrawer).observe(body, {attributes: true, attributeFilter: ['class']});
  untitle(); syncDrawer();
})();</script>""".replace("__COMMANDS__", json.dumps(COMMANDS)), unsafe_allow_javascript=True)


def selection_controls():
    """Vessel, cargo, lift and price-month pickers. Rendered exactly once per run (in the
    assistant composer, or the workspace strip on result pages) so their state is never dropped."""
    with st.container(key="selection"):
        vessel_col, cargo_col, lift_col, period_col = st.columns(4, vertical_alignment="center", gap="small")
        with vessel_col:
            st.selectbox("Selected vessel", [None] + [v["vessel_id"] for v in tables["managed_vessels"]], format_func=lambda v: v or "Vessel", key="selected_vessel", label_visibility="collapsed", placeholder="Vessel")
        with cargo_col:
            st.selectbox("Committed cargo", [None] + [c["cargo_id"] for c in tables["committed_cargoes"]], format_func=lambda c: c or "Cargo", key="selected_cargo", on_change=reset_lift, label_visibility="collapsed", placeholder="Cargo")
        with lift_col:
            st.number_input("Selected lift (tonnes)", min_value=0.0, max_value=1000000.0, value=None, step=500.0, format="%.12g", key="selected_lift", label_visibility="collapsed", placeholder="Lift, tonnes")
        with period_col:
            st.selectbox("Bunker price month", [None] + sorted({r["period"] for r in tables["bunker_forward_curve"]}),
                         format_func=lambda month: month or "Laycan month", key="price_period", label_visibility="collapsed")


if page not in ("Overview", "AI Assistant"):
    with st.container(key="workspace"):
        selection_controls()

lift_selected = (st.session_state.selected_lift or 0) > 0
has_selection = lift_selected and all(st.session_state[k] is not None for k in ("selected_vessel", "selected_cargo"))
case = dashboard_case(st.session_state.selected_cargo, st.session_state.selected_lift, st.session_state.price_period, st.session_state.selected_vessel) if has_selection else None
catalog = {"tables": tables, "ports": index(tables["ports"], "port_code")}

plan = build_plan(st.session_state.price_period) if page == "Overview" else None
with st.container(key={"Overview": "home", "AI Assistant": "assistant_page"}.get(page, "page_content")):
    if page == "Overview":
        focus = overview.focus_voyage(plan)
        st.session_state.plan_context = plan_summary(plan)
        overview.header(plan, sorted({r["period"] for r in tables["bunker_forward_curve"]}))
        overview.banner(plan)
        overview.kpis(plan)
        with st.container(key="overview_main"):
            left, right = st.columns([1.5, 1], gap="small")
            with left:
                overview.plan_table(plan, focus)
            with right:
                overview.route_map(plan, focus, catalog["ports"])
        with st.container(key="overview_lower"):
            left, right = st.columns([1.5, 1], gap="small")
            with left:
                overview.fleet_timeline(plan, focus)
            with right:
                overview.next_availability(plan)

    elif page == "AI Assistant":
        with st.container(key="assistant_full"):
            title, new = st.columns([1, .06], vertical_alignment="center")
            with title:
                heading("AI voyage assistant", "Commercial analysis")
            with new:
                st.button("New chat", icon=":material/edit_square:", key="new_conversation", on_click=start_new_chat)
            render_chat(controls=selection_controls)

    elif page == "Voyages":
        cargo_id, lift = st.session_state.selected_cargo, st.session_state.selected_lift
        cc = candidates_case(cargo_id, lift, st.session_state.price_period) if cargo_id is not None and lift_selected else None
        voyages_page(cc)
        if cc and not (st.session_state.get("voyage_port") or st.session_state.get("voyage_query")):
            if case:
                heading("Selected voyage · " + case["vessel"]["vessel_id"], "Economics, checks and schedule")
                voyage_summary(case)
                with st.container(border=True):
                    economics(case)
                with st.container(border=True, key="timeline_panel"):
                    timeline(case)
                with st.expander("Full engine output and methodology"):
                    st.json({"result":case["row"], "conventions": case['comparison']['conventions']})
            else:
                st.caption("Select a vessel to see its economics, fuel and draft checks and voyage timeline here.")

    elif page == "Analytics":
        cargo_id = st.session_state.selected_cargo
        objective = st.session_state.get("ranking_objective", "contribution")
        optimise = not lift_selected or st.session_state.get("optimise_rank_lift", False)
        analytics = case
        if cargo_id and (analytics is None or optimise or objective != "contribution"):
            lift = None if optimise else st.session_state.selected_lift
            analytics = dashboard_case(cargo_id, lift, st.session_state.price_period,
                                       st.session_state.selected_vessel, objective=objective)

        def report_button():
            if analytics:
                month = analytics["row"]["bunker_price_period"]
                st.download_button("Download report", analytics_report(analytics),
                    file_name=f"kingfish_{cargo_id}_{month}_report.html",
                    mime="text/html", icon=":material/download:", key="analytics_report", on_click="ignore")
            else:
                st.download_button("Download report", data="", disabled=True, icon=":material/download:",
                    file_name="kingfish_analytics.html", mime="text/html", key="analytics_report")

        def ranking_panel():
            with st.expander("Rank the selected cargo", expanded=bool(analytics)):
                if analytics is None:
                    st.caption("Select a committed cargo to rank vessels.")
                    return
                objective_col, lift_col = st.columns(2)
                objective_col.selectbox("Ranking objective", list(OBJECTIVES),
                                        format_func=lambda key: OBJECTIVES[key][1], key="ranking_objective")
                if lift_selected:
                    lift_col.checkbox("Optimise lift within cargo tolerance", key="optimise_rank_lift")
                else:
                    lift_col.caption("No lift selected. The ranking searches the cargo tolerance.")
                render_evidence([{"tool": "compare_vessels", "result": analytics["comparison"]}],
                                key_prefix="cargo_ranking", compact=True)

        analytics_page(report_button, ranking_panel)

    elif page == "Reports" and not case:
        heading(page)
        st.info("Select a vessel, cargo and tonnage to view voyage results.")

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
            st.html('<div class="table-wrap" style="max-height:550px;overflow:auto">'+frame.to_html(index=False, escape=True, classes="ocean-table", border=0)+'</div>')

    elif page == "Reports":
        heading("Export calculated results", "Includes feasibility flags and pricing period")
        comparison_table(case)
        st.download_button("Download voyage comparison CSV", result_frame(case).to_csv(index=False).encode("utf-8"), file_name=f'{st.session_state.selected_cargo}_{case["row"]["bunker_price_period"]}_comparison.csv', mime="text/csv")
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
        st.write("Use the moon button at the bottom of the sidebar to switch themes. Your selection persists for this browser session. Profile settings and local-session logout are in the name dropdown.")
        try:
            _, model = load_settings()
            st.success("OpenRouter key configured on the server.")
            st.code(model)
        except ValueError as exc:
            st.error(str(exc))
        st.json(conventions(load_policy()))
        st.caption("The API key is excluded from Git and is not exposed by this screen. Market quotes and fleet allocation are outside the current ranking scope.")

if page == "Overview":
    overview.shippy_drawer(plan, focus, render_chat, start_new_chat)
