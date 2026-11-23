"""First-visit product tours: a short, page-specific walkthrough the first time each page opens.

Each page has 3 to 5 steps. A step points at an element by CSS selector and is skipped when that
element is not on screen (for example the Voyages search card once a cargo is open). Whether a
page's tour has been seen is kept in the browser's localStorage against an ID made when the server
starts, so a browser refresh keeps tours dismissed but restarting the app shows them all again.
"Replay page tour" in the profile menu shows the current page's tour on demand. Copy stays under 140 characters
and says what the user gains, not which button to press.
"""
import json
import uuid

import streamlit as st

MAX_COPY = 140

# (selector, title, body). Selectors are Streamlit keys (.st-key-…) or stable classes from this app.
TOURS = {
    "Overview": [
        (".overview-title h1", "Your recommended plan",
         "The best use of your fleet this month: every committed cargo covered at the highest total contribution"),
        (".kpi-grid", "Plan health at a glance",
         "Contribution, TCE against the market and the tightest laycan in one row, so you see risk early"),
        (".st-key-plan_panel", "Every voyage, and why",
         "Each voyage with its earnings and risks. Alternatives shows what each choice is worth against the next best."),
        (".st-key-map_panel", "Routes on the map",
         "Spot long ballast legs before you commit a ship. Select a voyage to see its route, or show the whole plan."),
        (".ask-shippy", "Ask Shippy",
         "Ask why a ship got a cargo or what a fuel spike would do. Answers come from the same engine as the plan."),
    ],
    "Voyages": [
        (".st-key-selected_cargo", "Start with a cargo",
         "Pick one and every ship that could carry it is priced and ranked. Nothing else is required."),
        (".st-key-ranking_objective", "Decide what best means",
         "Rank by profit after hire, daily earnings before hire, or profit that holds up when costs rise"),
        (".st-key-selected_lift", "Cargo size, suggested",
         "We fill in the most profitable lift for each ship. Type tonnes to test one size across the fleet."),
        (".st-key-voyage_search", "Search without IDs",
         "Find a cargo by port, country or commodity, typos included, when you don't have its ID to hand"),
        (".st-key-voyage_guide, .st-key-voyage_help", "Quick reference",
         "What every control on this page does, in one place, whenever you need a reminder"),
    ],
    "AI Assistant": [
        ('[data-testid="stChatInput"]', "Ask in plain words",
         "Ask about any ship, cargo or price month. Answers are calculated by the voyage engine, not guessed."),
        (".st-key-voyage_selectors", "Set the context",
         "Choose a vessel, cargo and lift so answers focus on the voyage you are weighing"),
        (".st-key-new_conversation", "Start fresh any time",
         "Open a clean conversation for a new question. Your plan and selections stay as they are."),
    ],
    "Analytics": [
        (".st-key-an_filters", "Compare what you can use",
         "Filter ships and cargoes, or show only feasible pairings, to weigh just the options on the table"),
        (".st-key-an_heatmap", "Every pairing at once",
         "Contribution for each ship and cargo, so the strongest and weakest pairings stand out immediately"),
        (".st-key-an_ranking", "Rank one cargo",
         "Rank ships for the selected cargo by profit, TCE or stressed profit, with the evidence behind the winner"),
        (".st-key-an_report", "Share the analysis",
         "Download a report of the current view to send to your team"),
    ],
}

_ENGINE = """
(() => {
  if (window.kfTour) return;
  const KEY = page => 'kingfish.tour.' + page;
  const seen = (page, boot) => { try { return localStorage.getItem(KEY(page)) === boot; } catch (e) { return false; } };
  const remember = (page, boot) => { try { localStorage.setItem(KEY(page), boot); } catch (e) {} };
  const visible = el => { if (!el) return false; const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const target = step => [...document.querySelectorAll(step.selector)].find(visible);
  let state = null;

  const close = () => {
    if (!state) return;
    cancelAnimationFrame(state.frame); clearTimeout(state.wait);
    const {ring, tip} = state;
    // close() and hidden start the CSS exit transitions; the nodes go once they have played.
    if (tip.open) tip.close();
    ring.hidden = true;
    setTimeout(() => { ring.remove(); tip.remove(); }, 200);
    document.removeEventListener('keydown', state.keys, true);
    state = null;
  };

  const place = () => {
    if (!state) return;
    const el = target(state.steps[state.index]);
    if (!el) { next(); return; }
    const r = el.getBoundingClientRect(), pad = 6, gap = 12, margin = 12;
    Object.assign(state.ring.style, {left: (r.left - pad) + 'px', top: (r.top - pad) + 'px',
                                     width: (r.width + 2 * pad) + 'px', height: (r.height + 2 * pad) + 'px'});
    const tip = state.tip, w = tip.offsetWidth, h = tip.offsetHeight, W = innerWidth, H = innerHeight;
    // Below the element if it fits, else above, else beside it, else pinned inside the viewport.
    let top, left = Math.min(Math.max(r.left, margin), W - w - margin), side = 'below';
    if (r.bottom + pad + gap + h <= H - margin) top = r.bottom + pad + gap;
    else if (r.top - pad - gap - h >= margin) { top = r.top - pad - gap - h; side = 'above'; }
    else if (r.right + pad + gap + w <= W - margin) { left = r.right + pad + gap; top = Math.min(Math.max(r.top, margin), H - h - margin); side = 'right'; }
    else if (r.left - pad - gap - w >= margin) { left = r.left - pad - gap - w; top = Math.min(Math.max(r.top, margin), H - h - margin); side = 'left'; }
    else { top = H - h - margin; side = 'inside'; }
    tip.style.left = left + 'px'; tip.style.top = top + 'px'; tip.dataset.side = side;
    state.frame = requestAnimationFrame(place);
  };

  const show = index => {
    const steps = state.steps;
    while (index < steps.length && !target(steps[index])) index++;
    if (index >= steps.length) { close(); return; }
    state.index = index;
    // Count against the steps found when the tour opened, plus any that appeared since, in tour order.
    const step = steps[index], shown = steps.filter(s => state.found.has(s) || target(s)), position = shown.indexOf(step) + 1;
    const el = target(step);
    const r = el.getBoundingClientRect();
    if (r.top < 0 || r.bottom > innerHeight) el.scrollIntoView({block: 'nearest', behavior: 'instant'});
    const tip = state.tip;
    tip.querySelector('.kf-tour-count').textContent = position + ' of ' + shown.length;
    tip.querySelector('h4').textContent = step.title;
    tip.querySelector('p').textContent = step.body;
    const last = position === shown.length;
    tip.querySelector('[data-next]').textContent = last ? 'Done' : 'Next';
    tip.querySelector('[data-skip]').hidden = last;
    if (!tip.open) tip.show();  // non-modal, so the page behind stays usable
    state.ring.hidden = false;
    cancelAnimationFrame(state.frame); place();
    tip.querySelector('[data-next]').focus({preventScroll: true});
  };
  const next = () => state && show(state.index + 1);

  const start = (page, steps, boot, force) => {
    if (state && state.page === page) return;
    close();
    if (!steps.length || (!force && seen(page, boot))) return;
    const ring = document.createElement('div'); ring.className = 'kf-tour-ring'; ring.hidden = true;
    const tip = document.createElement('dialog'); tip.className = 'kf-tour';
    tip.setAttribute('aria-live', 'polite'); tip.setAttribute('aria-label', page + ' tour');
    // Built with DOM calls: markup inside this script's strings would be stripped by the HTML sanitiser.
    const make = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; };
    const actions = make('div', 'kf-tour-actions'), skip = make('button', 'kf-tour-skip', 'Skip tour'), go = make('button', 'kf-tour-next', 'Next');
    skip.type = go.type = 'button'; skip.dataset.skip = ''; go.dataset.next = '';
    actions.append(skip, go);
    tip.append(make('span', 'kf-tour-count'), make('h4'), make('p'), actions);
    tip.addEventListener('click', event => {
      if (event.target.closest('[data-next]')) next();
      else if (event.target.closest('[data-skip]')) close();
    });
    const keys = event => { if (event.key === 'Escape' && state) { event.stopPropagation(); close(); } };
    document.addEventListener('keydown', keys, true);
    document.body.append(ring, tip);
    state = {page, steps, ring, tip, keys, index: 0, frame: 0, wait: 0, found: new Set()};
    // The first step opens on page load, once every target has rendered or the page has settled
    // (1.2 s after the first target appears). The tour counts as seen from then on.
    const began = performance.now();
    let first = 0;
    const ready = () => {
      if (!state || state.page !== page) return;
      const present = steps.filter(target), now = performance.now();
      if (present.length && !first) first = now;
      if (present.length === steps.length || (first && now - first > 1200)) {
        present.forEach(s => state.found.add(s)); remember(page, boot); show(0); return;
      }
      if (now - began < 8000) state.wait = setTimeout(ready, 150); else close();
    };
    ready();
  };
  window.kfTour = {start, close};
})();
"""


@st.cache_resource
def _server_boot():
    """An ID for this server run: tours seen before the app restarted show again afterwards."""
    return uuid.uuid4().hex


def tour(page, replay=False):
    """Start this page's tour on its first visit, or again when replay is set."""
    steps = [{"selector": s, "title": t, "body": b} for s, t, b in TOURS.get(page, [])]
    st.html("<script>" + _ENGINE + f"window.kfTour.start({json.dumps(page)}, {json.dumps(steps)}, "
            + f"{json.dumps(_server_boot())}, {json.dumps(bool(replay))});"
            + "</script>", unsafe_allow_javascript=True)
