"""Patch notes: one entry for every commit pushed to the project branch, newest first.

Laid out like a game studio's patch notes: a date heading for each patch, upper-case product
sections (GLOBAL, OVERVIEW, VOYAGES …) with subsections such as Bug fixes, and bulleted changes
where a bold lead can carry indented detail. Pushes made on the same date are combined into one
note for that date, and the notes are paged five dates at a time inside their own scroll panel.

Adding a patch: put a new entry at the top of PATCHES with the next version and the push time.
An item is a string, or a (lead, [details]) pair. Text in `backticks` is set as code.
"""
import html
import re
from datetime import datetime

import streamlit as st

# (version, pushed at, title, intro, sections). sections: [(SECTION, [(subsection or None, [items])])]
PATCHES = [
    ("1.23", "2026-11-26 03:37", "Click to select, counting KPIs", "Whole cards and table rows select a vessel, and Overview KPIs count up", [
        ("GLOBAL", [("Bug fixes", [
            "Updating a page no longer blanks it for a moment; it stays in place while it updates",
        ])]),
        ("OVERVIEW", [("UI/UX", [
            "KPI values count up when they first show and count to the new figure when they change",
        ])]),
        ("VOYAGES", [("UI/UX", [
            ("Vessel selection", ["Clicking anywhere on a candidate card selects that vessel",
                                  "Clicking a row in the specifications and feasibility table selects that vessel"]),
        ])]),
    ]),
    ("1.22", "2026-11-26 00:18", "Steadier plan, vessel links", "Plan rows hold still while they update, and vessel codes on Voyages select the vessel", [
        ("OVERVIEW", [("Bug fixes", [
            "Picking a row in The plan no longer pushes the rows above and below while the page updates",
            "The map's view switcher stays in its corner while the map updates",
        ])]),
        ("VOYAGES", [("UI/UX", [
            ("Vessel links", ["Each vessel code in a candidate card is an underlined link that selects it, replacing Select vessel",
                              "Vessel codes in the specifications and feasibility table select the vessel too"]),
            "The line under Evaluated vessels is removed",
        ])]),
    ]),
    ("1.21", "2026-11-24 05:28", "Paged patch notes", "Patch notes are grouped by date and paged, five dates at a time", [
        ("DOCUMENTS", [("UI/UX", [
            ("Patch notes", ["Pushes made on the same date are combined into one note, with a row per push",
                             "Pages of five dates replace the version dropdown, with Newer and Older under the notes",
                             "Only the notes scroll; the back link, page range and pager stay in place",
                             "The back link is plain text instead of a button"]),
        ])]),
    ]),
    ("1.20", "2026-11-24 04:14", "Patch notes", "Every pushed change now has its own patch note, inside Documents", [
        ("DOCUMENTS", [(None, [
            ("Patch notes", ["A Patch notes button in Documents opens the full change history",
                             "Pick any version above the notes to read what changed in that push",
                             "Each patch lists its changes by page, with bug fixes called out separately"]),
        ])]),
    ]),
    ("1.19", "2026-11-23 20:14", "Native dialog and popover", "The tour and the Ask Shippy drawer now use the browser's own top layer", [
        ("GLOBAL", [("UI/UX", [
            ("Page tour", ["The tour panel is a dialog element, still non-modal so the page stays usable",
                           "It fades in from `@starting-style` and fades out before it is removed"]),
            ("Ask Shippy drawer", ["Opens in the top layer with a native backdrop instead of stacked layers",
                                   "Slides in and out with `allow-discrete` display and overlay transitions",
                                   "Clicking anywhere outside the drawer closes it"]),
            "The slash shortcut menu shows above the open drawer",
        ]), ("Stability", [
            "The separate backdrop element and sidebar veil are removed",
            "Browsers without popover support keep the previous slide-in drawer",
        ])]),
    ]),
    ("1.18", "2026-11-22 20:29", "Tours reset on restart", "Page tours show again every time the app restarts, but not on a browser refresh", [
        ("GLOBAL", [("UI/UX", [
            "Tour seen-state is tied to the current app run, so a refresh keeps tours dismissed",
            "Restarting the app shows every page tour again",
        ])]),
    ]),
    ("1.17", "2026-11-22 19:14", "Page tours and a clearer Voyages", "First-visit tours on four pages, explanations for every Voyages control and a cleaner Overview", [
        ("GLOBAL", [("UI/UX", [
            ("Page tours", ["Overview, Voyages, AI Assistant and Analytics each open a 3 to 5 step tour on first visit",
                            "Tour copy stays under 140 characters and says what you gain",
                            "Replay page tour in the profile menu shows it again"]),
        ]), ("Bug fixes", [
            "Fixed the profile Save button being unreadable in dark mode; it is now the primary button",
        ])]),
        ("OVERVIEW", [(None, [
            "Titled Recommended Plan, with the plan banner removed so every card moves up",
            "The voyage count now sits on the portfolio contribution tile",
            "The first voyage is focused on load, so the map shows one route; clearing it shows the whole plan",
        ])]),
        ("VOYAGES", [(None, [
            "The search card matches the width of the four selectors above it",
            "A What each control does guide sits beside it, and behind How this page works once a cargo is open",
            ("Search", ["Typos now find a match through fuzzy search",
                        "Exact codes and literal matches still rank first"]),
        ])]),
    ]),
    ("1.16", "2026-11-12 16:56", "Each vessel at its own best lift", "While the lift is the suggestion, every vessel is ranked at the lift that suits it best", [
        ("VOYAGES", [(None, [
            "Each vessel is ranked at its own best lift within the cargo tolerance, shown on its card and in the table",
            "A selected vessel's voyage uses that lift",
            "A typed lift still applies to every vessel",
            "The CSV export carries each row's lift",
        ])]),
    ]),
    ("1.15", "2026-11-12 16:18", "Suggested lift and rank method", "Pick a cargo and a rank method; the lift is filled in for you", [
        ("VOYAGES", [(None, [
            ("Suggested lift", ["Picking a cargo fills the lift box with the best lift within the cargo tolerance",
                                "The lift stays editable, and a typed lift is kept when the rank method or price month changes",
                                "Use suggested lift restores the suggestion"]),
            ("Rank by", ["Choose contribution after hire, TCE before hire or stressed contribution",
                         "Ranks, the top tag, the lead and the market strip follow the chosen objective",
                         "Shared with the Analytics ranking objective"]),
        ])]),
    ]),
    ("1.14", "2026-11-11 02:04", "Fleet allocation", "The plan now covers committed and market cargoes, chartering in where it pays", [
        ("ENGINE", [(None, [
            "Each owned vessel is planned onto a committed or market cargo",
            "Market vessels are chartered in where that covers a committed cargo more profitably",
            "Every combination is searched, ranking coverage of committed cargoes first and then total contribution",
        ])]),
        ("OVERVIEW", [(None, [
            ("Alternatives", ["A new view beside The plan prices dropping each pairing",
                              "It also prices swapping owned vessels and every other use of a focused voyage"]),
            "Days are spelled out, the plan header fill and timeline count are removed",
            "The heat map compacts when more than three cargoes show",
        ])]),
        ("GLOBAL", [(None, [
            "The top bar, Voyages, Analytics, search and Shippy's tools now cover all 15 vessels and 11 cargoes",
            "Map positions added for the market ports",
        ])]),
    ]),
    ("1.13", "2026-11-11 01:07", "Market hire and freight", "Market vessels and cargoes are priced from the data pack's FFA references", [
        ("ENGINE", [(None, [
            ("Market hire offers", ["5TC for the delivery month, adjusted for fuel use"]),
            ("Market freight quotes", ["The rate that pays a pack-average Capesize the C3, C5 or 5TC TCE"]),
            "The engine now prices every vessel and cargo pairing",
        ])]),
        ("DOCUMENTS", [(None, [
            "New Market rate assumptions document with the method, cross-checks and linked sources",
        ])]),
        ("ASK SHIPPY", [("Bug fixes", [
            "Engine briefings are no longer flagged as truncated when only the short commentary hit the token limit",
            "The response limit is raised to 8,192 tokens",
        ])]),
    ]),
    ("1.12", "2026-11-11 00:23", "Timeline card alignment", "The voyage timeline card lines up with the cards around it", [
        ("VOYAGES", [("UI/UX", [
            "The timeline card matches the width of the economics and expander cards",
            "The laycan track is inset so its first and last stops sit clear of the card edge",
        ])]),
    ]),
    ("1.11", "2026-11-10 21:35", "Sharper heat map focus", "Clearer focus on the heat map and a plainer computed stamp", [
        ("ANALYTICS", [("UI/UX", [
            "The focused heat map cell is ringed in the accent and its axis labels are coloured",
            "Failed-check notes wrap so they stay inside their cells",
        ])]),
        ("OVERVIEW", [("UI/UX", [
            "The bunker cost note names the pricing basis",
            "The computed time is plain text, with a Laycan month pricing placeholder",
        ])]),
    ]),
    ("1.10", "2026-11-10 20:20", "Analytics filter row", "All Analytics filters fit on one tidy row", [
        ("ANALYTICS", [("UI/UX", [
            "One 32px row holds lift basis, vessels, cargoes, Feasible only and Download report",
            "Download report stays greyed out until a cargo is chosen",
            "Lift basis is the only control using the accent; the other selections use a neutral surface",
            "Vessel and cargo codes stay in mono, as in the charts and table",
        ])]),
    ]),
    ("1.9", "2026-11-10 20:20", "One lift search everywhere", "Ranking and the Overview plan now agree on each vessel's largest lift", [
        ("ENGINE", [(None, [
            "The ranking adds each vessel's largest loadable lift to its 1,000 t grid",
            "Ranking and plan share one load-limit check, to the nearest 100 t",
        ]), ("Bug fixes", [
            "Fixed CC-01 ranking MF-01 first while the plan chose MF-04; MF-04 now ranks first at 169,100 t",
        ])]),
        ("DOCUMENTS", [(None, ["The 100 t rounding is recorded in Modelling assumptions"])]),
    ]),
    ("1.8", "2026-11-10 18:23", "Draft-limited lifts", "Draft headroom is shown beside the ranking status instead of replacing it", [
        ("ENGINE", [(None, [
            "Draft headroom is a qualifier next to the status, so Dominant, Trade-off and Objective-dependent reach you",
        ]), ("Bug fixes", [
            "Fixed every winner being labelled Qualified because the lift search fills each vessel to its draft limit",
        ]), ("Stability", [
            "New checks: ballast absorbed by laycan waiting, waiting fuel counted once, the runner-up dominance rule",
            "Every cargo and objective must return a recommendation",
        ])]),
    ]),
    ("1.7", "2026-11-10 18:12", "November voyage rules", "The engine follows the 2 November methodology and ranks by objective", [
        ("ENGINE", [(None, [
            ("Fuel plan", ["Buy the minimum by grade before ballast and at the loading port, with no added time or fees",
                           "Keep 300 t VLSFO and 25 t MGO on board through discharge"]),
            ("Timing", ["Arrival at or before laycan closing qualifies; loading can finish after it closes"]),
            ("Draft", ["0.30 m headroom against the summer limit and both port limits, at laden departure"]),
            ("Ranking", ["Compare a cargo by contribution, TCE or stressed contribution",
                         "Stress adds 20% to bunkers, 15% to port charges and three idle days at loading"]),
        ])]),
    ]),
    ("1.6", "2026-11-09 02:50", "Shippy shortcuts and fleet analytics", "Slash shortcuts for Shippy and a full fleet-by-cargo Analytics dashboard", [
        ("ASK SHIPPY", [(None, [
            ("Slash shortcuts", ["`/voyages` fills the inputs and opens Voyages",
                                 "`/compare` ranks the fleet on a cargo, or runs vessels across cargoes",
                                 "`/analytics` opens Analytics, `/help` lists them all",
                                 "Typing / shows the list above the chat box; Tab or click fills one in"]),
        ]), ("Bug fixes", [
            "Chat no longer rubber-bands when you scroll up",
            "The New chat label lines up with its icon",
        ])]),
        ("ANALYTICS", [(None, [
            "Rebuilt as a fleet-by-cargo dashboard with lift basis, vessel, cargo and feasibility filters",
            "KPI row, contribution heat map, TCE against laycan slack, revenue split and voyage time by stage",
            "Bunker-month and lift sensitivity, a focus waterfall and a sortable table with CSV export",
            "Colours checked for colour-vision deficiency in both themes",
        ])]),
        ("GLOBAL", [("Stability", [
            "A test now stops angle brackets in the stylesheet, which made the whole sheet disappear",
        ])]),
    ]),
    ("1.5", "2026-11-09 01:31", "Browser crash fix", "Leaving Overview after opening Ask Shippy no longer freezes the browser", [
        ("GLOBAL", [("Bug fixes", [
            "Fixed the browser freezing or crashing after leaving Overview with the Ask Shippy drawer used",
        ]), ("Performance", [
            "The Voyages ticker is a still strip that scrolls sideways instead of an endless animation",
            "The map's loading shimmer stops and is removed once the map is drawn",
        ])]),
    ]),
    ("1.4", "2026-11-08 23:45", "Faster pages and an English map", "Page changes are quicker and every map label is in English", [
        ("GLOBAL", [("Performance", [
            "Country outlines are served once as a cached file instead of 267 KB inside every map",
            "Data tables, the stylesheet and the map template are cached per process",
            "The outgoing page is removed as soon as the new one starts streaming",
        ]), ("UI/UX", [
            "Land is drawn from Natural Earth with no tile server, so every map label is English",
            "Loading shimmer for the map and for anything waiting on a slow rerun",
        ])]),
        ("OVERVIEW", [(None, [
            "Square highlights in the plan and timeline, with matching slack text",
            "Green KPI notes for met obligations and a TCE premium",
            "Plain month options under one Pricing label",
        ])]),
    ]),
    ("1.3", "2026-11-08 22:36", "Overview plan and Ask Shippy", "Overview is rebuilt around the fleet plan, and Shippy moves into a drawer", [
        ("OVERVIEW", [(None, [
            ("Fleet plan", ["Committed cargoes are assigned to owned vessels at the best feasible lift",
                            "KPIs, routes, timeline and availability all come from this plan"]),
            "Plan table with row focus and a route map showing Selected or All voyages",
            "Fleet timeline with laycan brackets and slack, plus next availability",
            "Amber marks a tight laycan or a draft at its limit",
        ])]),
        ("ASK SHIPPY", [(None, [
            "A right-side drawer over the dimmed dashboard; close it with X, Escape or the backdrop",
            "The conversation and any draft survive while it is closed",
            "Context chip, suggested questions and compact answer tables with Open in Voyages",
        ]), ("Bug fixes", ["Fixed collapsed user chat bubbles"])]),
        ("GLOBAL", [(None, ["Selections persist on pages without selector widgets"])]),
    ]),
    ("1.2", "2026-11-08 18:38", "TCE heat map", "A real heat map on Home, driven by the same engine as everything else", [
        ("OVERVIEW", [(None, [
            ("TCE heat map", ["A vessel-by-cargo grid coloured by engine TCE",
                              "Clicking a cell selects that voyage; failed checks are marked with a dot"]),
            "Fuzzy, ranked search for Track your ship",
        ])]),
        ("ASK SHIPPY", [(None, [
            "Typed questions set cargo, vessel, lift and month directly, so KPIs update even if the model call fails",
            "Voyage inputs collapse into one line above the prompt",
            "Chat reads like a document, with your messages as bubbles",
        ])]),
        ("GLOBAL", [("UI/UX", ["The dark sidebar uses the graphite tokens", "Hover tooltips are removed"])]),
    ]),
    ("1.1", "2026-11-08 18:00", "Home fits the desktop", "KingFish Home fills a desktop screen and chat results link through", [
        ("OVERVIEW", [("UI/UX", ["Home is laid out to fit a desktop screen without scrolling"])]),
        ("ASK SHIPPY", [(None, ["Voyage results in chat connect to Home and Voyages"])]),
    ]),
    ("1.0", "2026-11-08 17:40", "KingFish", "OceanFlow becomes KingFish, with a redesigned Home", [
        ("GLOBAL", [("UI/UX", [
            "The app is renamed KingFish",
            "Navigation stays visible as an icon rail when the sidebar is collapsed",
        ])]),
        ("OVERVIEW", [(None, ["Home is redesigned around the voyage map and fleet KPIs"])]),
    ]),
    ("0.20", "2026-11-03 05:18", "Voyages rebuilt", "Voyages becomes a candidate comparison for one cargo", [
        ("VOYAGES", [(None, [
            "Every managed vessel is evaluated for one cargo and lift; choosing a vessel is optional",
            ("Candidate cards", ["Ranked by TCE and contribution, with laycan slack, draft headroom and voyage-stage bars",
                                 "Select vessel sets it across the app"]),
            "Specification and feasibility table with CSV export and a feasible filter",
            "Market strip: contract freight, the matching Baltic route, bunker prices and the lead over the runner-up",
            "Load-port and cargo search",
        ])]),
        ("GLOBAL", [("UI/UX", [
            "Shared map with curved routes, ringed port pins, mono labels and a re-centre control",
        ])]),
    ]),
    ("0.19", "2026-11-01 08:16", "Graphite restyle", "A calmer graphite look, with the voyage pickers moved next to the assistant", [
        ("GLOBAL", [("UI/UX", [
            "Neutral graphite palette with one sea-blue accent in both themes, on a 4px grid",
            "The top bar is removed; profile and theme toggle move to the sidebar footer",
            "Fixed-height KPI cards, aligned panel headers and a taller route map",
        ])]),
        ("ASK SHIPPY", [(None, [
            "Vessel, cargo, lift and price-month pickers sit above the chat box and open upwards",
        ])]),
        ("VOYAGES", [(None, [
            "The voyage timeline draws the laycan window to scale, with slack to close",
            "Profit margin reads Feasible or Infeasible, and an infeasible margin is greyed",
        ])]),
    ]),
    ("0.18", "2026-10-30 01:37", "Report download", "Download an Analytics report, and a smoother sidebar", [
        ("ANALYTICS", [(None, ["Download a report of the current analysis"])]),
        ("GLOBAL", [("UI/UX", ["The sidebar collapses smoothly"])]),
    ]),
    ("0.17", "2026-10-30 01:15", "New logo", "The supplied crown replaces the sidebar logo", [
        ("GLOBAL", [("UI/UX", ["Sidebar logo replaced with the supplied crown"])]),
        ("DOCUMENTS", [(None, ["Image and map credits list the new logo"])]),
    ]),
    ("0.16", "2026-10-30 00:51", "Assistant stays on topic", "Off-topic questions are declined before any engine call", [
        ("ASK SHIPPY", [(None, [
            "A scope check runs before every answer and declines questions outside freight planning",
            "At most three model calls per question",
        ])]),
        ("GLOBAL", [("UI/UX", ["Smoother chat and map interaction"])]),
    ]),
    ("0.15", "2026-10-29 23:24", "Empty selections on start", "Nothing is pre-selected, so no vessel or cargo is assumed", [
        ("GLOBAL", [(None, ["Voyage selections start empty"])]),
        ("ASK SHIPPY", [("Bug fixes", ["The assistant stays available while nothing is selected"])]),
    ]),
    ("0.14", "2026-10-29 23:15", "New chat welcome", "Starting a new chat brings back the welcome screen", [
        ("ASK SHIPPY", [("Bug fixes", ["New chat returns to the empty welcome state"])]),
    ]),
    ("0.13", "2026-10-29 23:07", "Personal welcome", "The empty assistant greets you by name", [
        ("ASK SHIPPY", [(None, ["The empty assistant shows a personal welcome and a short prompt"])]),
    ]),
    ("0.12", "2026-10-29 22:18", "Chat drafts and captions", "Fixes for drafts carrying across pages and overlapping captions", [
        ("GLOBAL", [("Bug fixes", [
            "Chat drafts no longer carry over between pages",
            "Captions no longer overlap content",
        ]), ("Stability", ["A test checks that no API key is committed or logged"])]),
    ]),
    ("0.11", "2026-10-28 18:05", "Clarified planning assumptions", "The engine applies the clarified fuel purchase and draft rules", [
        ("ENGINE", [(None, [
            "Planning purchases cover fuel shortfalls without adding days or cost",
            "Draft margin of 0.3 m below summer draft; port draft limits are a separate report-only check",
            "Working policy lives in `config/modelling.toml`",
        ])]),
        ("DOCUMENTS", [(None, ["Assumption log with confirmed arithmetic and questions awaiting Cargill"])]),
    ]),
    ("0.10", "2026-10-28 05:40", "Fuel audit by stage", "Fuel is audited stage by stage, and late laycans are documented", [
        ("ENGINE", [(None, [
            "Fuel inventory is audited through each voyage stage, separately for VLSFO and MGO",
            "Purchase requirements are reported as needs, not as scheduled deliveries",
            "Combinations that arrive after laycan closes are excluded",
        ])]),
        ("DOCUMENTS", [(None, ["New Modelling assumptions document"])]),
    ]),
    ("0.9", "2026-10-27 05:13", "Streamlined controls", "Fewer controls, and the dashboard fits the window", [
        ("GLOBAL", [("UI/UX", ["The dashboard fits the window at desktop sizes", "Controls on the main pages are simplified"])]),
    ]),
    ("0.8", "2026-10-27 04:52", "Responsive layout", "The layout adapts to narrower windows", [
        ("GLOBAL", [("UI/UX", ["The layout adapts to narrower windows", "Sidebar navigation between pages"])]),
    ]),
    ("0.7", "2026-10-27 04:20", "Grounded analyst reports", "Reports where every figure comes from an engine calculation", [
        ("ASK SHIPPY", [(None, [
            "Analyst briefings are built from engine results, so every figure is calculated",
            "Answers can include charts",
        ])]),
        ("GLOBAL", [("UI/UX", ["The dashboard is aligned with the product layout"])]),
    ]),
    ("0.6", "2026-10-26 04:54", "Dashboard fits the screen", "A real route map, and the dashboard and chat fit the window", [
        ("GLOBAL", [("UI/UX", [
            "The dashboard and chat fit the browser window",
            "A real route map with port pins",
            "Profile menu",
        ])]),
        ("DOCUMENTS", [(None, ["New Image and map credits document"])]),
    ]),
    ("0.5", "2026-10-26 04:26", "OceanFlow dashboard", "The first dashboard, with dark mode", [
        ("GLOBAL", [("UI/UX", ["New OceanFlow dashboard with KPI cards, voyage results and chat", "Dark mode"])]),
        ("DOCUMENTS", [(None, ["New Metric coverage document mapping each project metric to where the app shows it"])]),
    ]),
    ("0.4", "2026-10-26 03:56", "API client tidy", "A small clean-up with no change in behaviour", [
        ("GLOBAL", [("Stability", ["Removed stray whitespace in the API client"])]),
    ]),
    ("0.3", "2026-10-26 03:55", "Voyage engine and assistant", "The voyage engine and a layered assistant on top of it", [
        ("ENGINE", [(None, [
            ("Voyage engine", ["Calculates every vessel and cargo pairing in Python from the data pack",
                               "Duration, fuel, revenue, costs, TCE and feasibility checks"]),
            "The assistant can only reach the engine through validated Python tools",
        ])]),
        ("ASK SHIPPY", [(None, [
            "The model reads the question, Python tools compute the numbers and the model explains them",
        ])]),
    ]),
    ("0.2", "2026-10-26 03:46", "Connection test fix", "The model connection test has room to answer", [
        ("GLOBAL", [("Bug fixes", ["The free-model connection test no longer stops before replying"])]),
    ]),
    ("0.1", "2026-10-26 03:35", "First commit", "A starter that checks the model API connection", [
        ("GLOBAL", [(None, [
            "Connection check for the OpenRouter model API",
            "API keys are read from Streamlit secrets and kept out of Git",
            "Setup and run steps in the README",
        ])]),
    ]),
]


DATES_PER_PAGE = 5


def _when(patch):
    return datetime.strptime(patch[1], "%Y-%m-%d %H:%M")


def days():
    """[(date, [patches on that date, newest first])], newest date first."""
    grouped = {}
    for patch in PATCHES:
        grouped.setdefault(patch[1][:10], []).append(patch)
    return list(grouped.items())


def pages():
    """The dated notes split into pages of DATES_PER_PAGE dates."""
    dated = days()
    return [dated[i:i + DATES_PER_PAGE] for i in range(0, len(dated), DATES_PER_PAGE)]


def _text(value):
    """Escape, then set `backticks` as code."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", html.escape(value))


def _items(items):
    rows = []
    for item in items:
        if isinstance(item, tuple):
            lead, details = item
            rows.append(f'<li><b>{_text(lead)}</b><ul>' + "".join(f"<li>{_text(d)}</li>" for d in details) + "</ul></li>")
        else:
            rows.append(f"<li>{_text(item)}</li>")
    return "<ul>" + "".join(rows) + "</ul>"


def _merge(patches):
    """One set of sections for the day: same-named sections and subsections are joined, newest first."""
    merged = {}
    for patch in patches:
        for name, groups in patch[4]:
            section = merged.setdefault(name, {})
            for sub, items in groups:
                section.setdefault(sub, []).extend(items)
    return merged


def day_html(date, patches):
    """One date's note: date heading, a row per push (version, title, time, intro), then merged sections."""
    day = datetime.strptime(date, "%Y-%m-%d")
    parts = [f'<article class="pn"><h2 class="pn-date">{day:%B} {day.day}, {day:%Y}</h2><ul class="pn-pushes">']
    for patch in patches:
        number, _, title, intro, _ = patch
        parts.append(f'<li><span class="pn-v">v{html.escape(number)}</span><b class="pn-title">{_text(title)}</b>'
                     f'<span class="pn-time">{_when(patch):%H:%M} SGT</span><p class="pn-intro">{_text(intro)}</p></li>')
    parts.append("</ul>")
    for name, groups in _merge(patches).items():
        parts.append(f'<section><h3 class="pn-section">{html.escape(name)}</h3>')
        for sub, items in groups.items():
            if sub:
                parts.append(f'<h4 class="pn-sub">{html.escape(sub)}</h4>')
            parts.append(_items(items))
        parts.append("</section>")
    parts.append("</article>")
    return "".join(parts)


def open_patch_notes():
    st.session_state.docs_view = "patch_notes"


def close_patch_notes():
    st.session_state.docs_view = "documents"


def _go(page):
    st.session_state.patch_page = page


def page():
    """Patch notes view inside Documents: a text back link, the notes for one page of dates in their own
    scroll panel, and the pager under it."""
    st.button("All documents", icon=":material/arrow_back:", key="patch_back", on_click=close_patch_notes, type="tertiary")
    book = pages()
    current = min(st.session_state.get("patch_page", 0), len(book) - 1)
    shown = book[current]
    first, last = (datetime.strptime(d, "%Y-%m-%d") for d in (shown[0][0], shown[-1][0]))
    pushes = sum(len(p) for _, p in shown)
    st.html(f'<p class="pn-count">{last:%d %b} to {first:%d %b %Y} · {len(shown)} dates, {pushes} pushes · '
            f'page {current + 1} of {len(book)}</p>')
    # Keyed by page, so a new page starts at the top of the panel.
    with st.container(key=f"patch_scroll_{current}"):
        st.html("".join(day_html(date, patches) for date, patches in shown))
    with st.container(key="patch_pager", horizontal=True):
        st.button("Newer", icon=":material/chevron_left:", key="patch_newer", type="tertiary",
                  disabled=current == 0, on_click=_go, args=(current - 1,))
        for n in range(len(book)):
            st.button(str(n + 1), key=f"patch_pg_{n}", type="tertiary", disabled=n == current, on_click=_go, args=(n,))
        st.button("Older", icon=":material/chevron_right:", icon_position="right", key="patch_older", type="tertiary",
                  disabled=current == len(book) - 1, on_click=_go, args=(current + 1,))
