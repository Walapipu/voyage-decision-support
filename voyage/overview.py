"""Overview page: plan, route map, fleet timeline, next availability and the Shippy drawer.

Every figure comes from voyage.plan, which is built from the voyage engine."""
from datetime import datetime, timedelta, timezone
from html import escape

import streamlit as st

from voyage.map_view import _coordinates, _draw, locations
from voyage.analytics_charts import CHECKS
from voyage.data import load_tables
from voyage.plan import TIGHT_SLACK_DAYS, alternatives, plan_voyage, what_if

STAGE_NAMES = {"ballast": "Ballast", "wait": "Wait", "load": "Load", "laden": "Laden", "discharge": "Discharge"}


def e(value):
    return escape(str(value))


def money(value):
    return f"${value / 1e6:,.2f}M" if abs(value) >= 1e6 else f"${value:,.0f}"


def day(moment):
    return f"{moment:%d %b}"


def signed(value):
    return ("−" if value < 0 else "+") + money(abs(value))


def check_names(reasons):
    return ", ".join(CHECKS.get(r, r) for r in reasons)


def focus_voyage(plan):
    """The plan row in focus: one picked on this page, else the top-bar selection if it is planned."""
    state = st.session_state
    picked = state.get("plan_focus")
    if picked:
        voyage = plan_voyage(plan, picked[0])
        if voyage and voyage["cargo_id"] == picked[1]:
            return voyage
    voyage = plan_voyage(plan, state.get("selected_vessel"))
    return voyage if voyage and voyage["cargo_id"] == state.get("selected_cargo") else None


def focus_row(vessel_id, cargo_id, lift):
    """Clicking a plan row focuses that voyage and makes it the top-bar selection, so the other
    pages open on it; clicking it again returns to the whole plan."""
    state = st.session_state
    current = state.get("plan_focus") or (state.get("selected_vessel"), state.get("selected_cargo"))
    if tuple(current) == (vessel_id, cargo_id):
        state.plan_focus = None
        if (state.get("selected_vessel"), state.get("selected_cargo")) == (vessel_id, cargo_id):
            state.selected_vessel = state.selected_cargo = state.selected_lift = None
        state.map_view = "All voyages"
        return
    state.plan_focus = (vessel_id, cargo_id)
    state.selected_vessel, state.selected_cargo, state.selected_lift = vessel_id, cargo_id, lift
    if state.get("an_cargoes") is not None and cargo_id not in state.an_cargoes:
        state.an_cargoes = [*state.an_cargoes, cargo_id]  # Analytics opens with this cargo shown
    state.voyage_port = state.voyage_query = None
    state.map_view = "Selected"


def header(plan, periods):
    with st.container(key="overview_head"):
        title, label, pricing, ask = st.columns([1, .08, .16, .14], vertical_alignment="center", gap="small")
        stamp = plan["computed"].astimezone(timezone.utc).strftime("%d %b, %H:%M UTC")
        prices = (datetime.strptime(plan["period"], "%Y-%m").strftime("%b %Y") if plan["period"] else "laycan-month") + " prices"
        title.html(f'<div class="overview-title"><h1>Overview</h1><span class="computed">'
                   f'Computed {e(stamp)} · {e(prices)}</span></div>')
        label.html('<label class="pricing-label" for="price_period">Pricing</label>')
        with pricing:
            st.selectbox("Pricing", [None, *periods], key="price_period",
                         format_func=lambda p: datetime.strptime(p, "%Y-%m").strftime("%b %Y") if p else "Laycan month",
                         label_visibility="collapsed", placeholder="Laycan month")
        ask.html('<button type="button" class="ask-shippy" data-shippy-open aria-haspopup="dialog">'
                 '<span class="lucide icon-message-circle" aria-hidden="true"></span>Ask Shippy</button>')


def banner(plan):
    covered = plan["committed"] - len(plan["uncovered"])
    cover = (f"all {plan['committed']} committed cargoes covered" if not plan["uncovered"]
             else f"{covered} of {plan['committed']} committed cargoes covered")
    st.html(f'<div class="plan-banner"><div><small>Recommended plan</small>'
            f'<b>{len(plan["voyages"])} voyages · {money(plan["contribution"])} contribution · {e(cover)}</b></div>'
            f'<span>Market hire and freight are stated assumptions · see Documents</span></div>')


def kpis(plan):
    tightest = plan["tightest"]
    avg, fivetc = plan["avg_tce"], plan["fivetc"]
    premium = 100 * (avg - fivetc) / fivetc if avg is not None and fivetc else None
    vs = f'vs 5TC {money(fivetc)} · {premium:+.0f}%' if premium is not None else "Select a curve month for 5TC" if plan["period"] is None else "5TC not supplied"
    covered = plan["committed"] - len(plan["uncovered"])
    month = datetime.strptime(plan["period"], "%Y-%m").strftime("%b %Y") if plan["period"] else "Laycan month"
    tiles = [
        ("Portfolio contribution", money(plan["contribution"]), f'after hire · {len(plan["voyages"])} voyages', ""),
        ("Avg TCE", money(avg) if avg is not None else "—", vs, "" if premium is None else "good-note" if premium > 0 else "bad-note"),
        ("Committed cargoes covered", f"{covered} of {plan['committed']}",
         (f'{covered - len(plan["chartered"])} owned · {len(plan["chartered"])} chartered in' if not plan["uncovered"]
          else "uncovered: " + ", ".join(plan["uncovered"])),
         "good-note" if not plan["uncovered"] else "warn"),
        ("Bunker cost", money(plan["bunker_cost"]), f"VLSFO and MGO · {month} curve", ""),
        ("Tightest laycan slack", f'{tightest["slack"]:.1f} days' if tightest else "—",
         f'{tightest["vessel_id"]} → {tightest["cargo_id"]}' + (f" · under {TIGHT_SLACK_DAYS:g} days" if tightest["tight"] else "")
         if tightest else "No voyages", "warn" if tightest and tightest["tight"] else ""),
    ]
    st.html('<div class="kpi-grid">' + "".join(
        f'<div class="kpi {tone}"><h4>{e(label)}</h4><strong>{e(value)}</strong><small>{e(note)}</small></div>'
        for label, value, note, tone in tiles) + "</div>")


def _status(voyage):
    tags = []
    if voyage["draft_limited"]:
        tags.append('<span class="tag warn">Draft at limit</span>')
    tags.append(f'<span class="tag {"warn" if voyage["tight"] else "good"}">{voyage["slack"]:.1f} days slack</span>')
    return "".join(tags)


def plan_table(plan, focus):
    with st.container(key="plan_panel"):
        title, switch, note = st.columns([.3, .5, 1], vertical_alignment="center", gap="small")
        title.html('<div class="panel-head"><h3>The plan</h3></div>')
        with switch:
            view = st.segmented_control("Plan view", ["Plan", "Alternatives"], key="plan_view",
                                        default="Plan", label_visibility="collapsed", required=True)
        if view == "Alternatives":
            alternatives_view(plan, focus, note)
            return
        note.html('<div class="panel-head plan-note"><small>Select a row to focus the map and timeline</small></div>')
        st.html('<div class="plan-grid plan-head"><span>Vessel</span><span>Cargo</span><span>Route</span>'
                '<span class="num">TCE /day</span><span class="num">Contribution</span><span>Status</span></div>')
        with st.container(key="plan_scroll"):
            for v in plan["voyages"]:
                picked = focus is not None and focus["vessel_id"] == v["vessel_id"]
                with st.container(key=f"plan_row_{v['vessel_id']}"):
                    st.html(f'<div class="plan-grid plan-row{" picked" if picked else ""}">'
                            f'<span class="cell"><b>{e(v["vessel_id"])}</b>{"" if v["owned"] else "<small>Hired</small>"}</span>'
                            f'<span class="cell"><span class="code">{e(v["cargo_id"])}</span>{"<small>Spot</small>" if v["market_cargo"] else ""}</span>'
                            f'<span class="route">{e(v["route"])}<small>{v["lift"]:,.0f} t</small></span>'
                            f'<span class="num">${v["tce"]:,.0f}</span><span class="num">${v["contribution"]:,.0f}</span>'
                            f'<span class="status">{_status(v)}</span></div>')
                    st.button(f'{"Clear" if picked else "Focus"} {v["vessel_id"]} → {v["cargo_id"]}', key=f"plan_pick_{v['vessel_id']}",
                              on_click=focus_row, args=(v["vessel_id"], v["cargo_id"], v["lift"]))
            if not plan["voyages"]:
                st.caption("No feasible voyage at this pricing month")


def route_map(plan, focus, ports):
    where = locations()
    with st.container(key="map_panel"):
        # The view switch floats over the map's top-right corner; the map fills the panel.
        st.segmented_control("Map view", ["Selected", "All voyages"], key="map_view",
                             label_visibility="collapsed", required=True)
        shown = plan["voyages"]
        if st.session_state.get("map_view") == "Selected" and focus:
            shown = [focus]
        points, legs = [], []
        for v in sorted(shown, key=lambda v: v is focus):
            dim = focus is not None and v is not focus
            origin, load, discharge = (_coordinates(code, where) for code in (v["origin_port"], v["load_port"], v["discharge_port"]))
            legs.append({"from": origin, "to": load, "kind": "ballast-dim" if dim else "ballast"})
            legs.append({"from": load, "to": discharge, "kind": "laden-dim" if dim else "laden"})
            label = not dim
            points += [
                {"name": v["vessel_id"], "coordinates": origin, "kind": "other" if dim else "vessel", "permanent": label, "direction": "left"},
                {"name": ports[v["load_port"]]["port_name"], "coordinates": load, "kind": "load", "permanent": label and focus is not None, "direction": "top"},
                {"name": ports[v["discharge_port"]]["port_name"], "coordinates": discharge, "kind": "discharge", "permanent": label and focus is not None, "direction": "right"}]
        legend = [{"label": "Ballast", "kind": "ballast"}, {"label": "Laden", "kind": "laden"}]
        _draw(points, legs, legend if legs else (), height=320,
              alt="Map of " + (f'{focus["vessel_id"]} ballast and laden legs' if len(shown) == 1 and focus else f"{len(shown)} planned voyages"))


def _axis(plan):
    starts = [v["start"] for v in plan["voyages"]]
    ends = [max(v["end"], v["laycan"][1]) for v in plan["voyages"]]
    first = min(starts).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last = max(ends) + timedelta(days=2)
    return first, last


def fleet_timeline(plan, focus):
    with st.container(key="timeline_panel_home"):
        st.html(f'<div class="panel-head"><h3>Fleet timeline</h3><div class="stage-key">'
                + "".join(f'<small><i class="seg-{k}"></i>{n}</small>' for k, n in STAGE_NAMES.items())
                + '<small><i class="laycan-key"></i>Laycan</small></div></div>')
        if not plan["voyages"]:
            st.caption("No planned voyages")
            return
        first, last = _axis(plan)
        span = (last - first).total_seconds()
        at = lambda moment: 100 * (moment - first).total_seconds() / span
        ticks, mark = [], first
        while mark < last:
            mid = ' class="mid"' if mark.day == 15 else ""  # mid-month labels drop out on narrow screens
            ticks.append(f'<span{mid} style="left:{at(mark):.2f}%">{mark.day} {mark:%b}</span>')
            mark = mark.replace(day=15) if mark.day == 1 else (mark.replace(day=1) + timedelta(days=32)).replace(day=1)
        rows = []
        for v in plan["voyages"]:
            cursor, segments = v["start"], []
            for stage, days in v["days"].items():
                if days <= 0:
                    continue
                end = cursor + timedelta(days=days)
                segments.append(f'<i class="seg seg-{stage}" style="left:{at(cursor):.2f}%;width:{at(end) - at(cursor):.2f}%"></i>')
                cursor = end
            opens, closes = v["laycan"]
            picked = focus is not None and focus["vessel_id"] == v["vessel_id"]
            label = (f'{v["vessel_id"]} → {v["cargo_id"]}: available {day(v["start"])}, laycan {day(opens)} to {day(closes)}, '
                     f'free {day(v["end"])}, {v["slack"]:.1f} days slack')
            rows.append(f'<div class="tl-row{" picked" if picked else ""}" role="img" aria-label="{e(label)}">'
                        f'<b>{e(v["vessel_id"])} <span>→ {e(v["cargo_id"])}</span></b>'
                        f'<div class="tl-track"><i class="tl-start" style="left:{at(v["start"]):.2f}%"></i>{"".join(segments)}'
                        f'<i class="tl-laycan" style="left:{at(opens):.2f}%;width:{at(closes) - at(opens):.2f}%"></i></div>'
                        f'<em class="{"warn" if v["tight"] else "good"}">{v["slack"]:.1f} days</em></div>')
        st.html(f'<div class="tl"><div class="tl-axis"><b>Vessel → cargo</b><div>{"".join(ticks)}</div><em>Slack</em></div>'
                f'<div class="tl-body">{"".join(rows)}</div></div>')


def _availability(plan):
    items = "".join(
        f'<li><time>{day(a["free"])}</time><b>{e(a["vessel_id"])}</b>'
        f'<span>{e(a["port"])}' + (f' · after {e(a["after"])}' if a["after"] else ' · not in plan') + '</span></li>'
        for a in plan["availability"])
    chartered = "".join(f'<li><time>{day(c["redelivery"])}</time><b>{e(c["vessel_id"])}</b>'
                        f'<span>{e(c["port"])} · after {e(c["after"])} · {money(c["hire"])}/day</span></li>'
                        for c in plan["chartered"])
    return (f'<div class="avail"><h4 class="first">Owned fleet</h4><ol>{items}</ol><h4>Chartered redelivery</h4>'
            + (f"<ol>{chartered}</ol>" if chartered else "<p>No chartered vessels in this plan.</p>") + "</div>")


def _moves(changes):
    return ", ".join(f'{c["vessel_id"]} {"idle" if c["to"] is None else "→ " + c["to"]}' for c in changes)


def _option(label, result):
    if not result["feasible"]:
        return f'<li class="off"><b>{e(label)}</b><span>Fails {e(check_names(result["reasons"]))}</span><em>—</em></li>'
    detail = _moves(result["changes"]) or "No other changes"
    tone = "bad" if result["delta"] < -0.5 else ""
    return f'<li><b>{e(label)}</b><span>{e(detail)}</span><em class="{tone}">{e(signed(result["delta"]))}</em></li>'


def _focused_options(plan, focus):
    """Every other use of the focused vessel and every other vessel for its cargo, each re-planned in full."""
    tables, period = load_tables(), plan["period"]
    committed = {c["cargo_id"] for c in tables["committed_cargoes"]}
    cargoes = [c["cargo_id"] for c in tables["committed_cargoes"] + tables["market_cargoes"]]
    vessels = [v["vessel_id"] for v in tables["managed_vessels"]]
    if focus["cargo_id"] in committed:
        vessels += [v["vessel_id"] for v in tables["market_vessels"]]
    if not focus["owned"]:
        cargoes = [c for c in cargoes if c in committed]

    def ranked(pairs):
        results = [(label, what_if(period, v, c)) for label, v, c in pairs]
        shown = sorted((r for r in results if r[1]["feasible"]), key=lambda r: -r[1]["delta"])[:5]
        failed = [r for r in results if not r[1]["feasible"]]
        more = f'<li class="off note"><span>{len(failed)} more fail a check</span></li>' if failed else ""
        return "".join(_option(*r) for r in shown) + more

    uses = ranked([(f'→ {c}', focus["vessel_id"], c) for c in cargoes if c != focus["cargo_id"]])
    carriers = ranked([(v, v, focus["cargo_id"]) for v in vessels if v != focus["vessel_id"]])
    return (f'<h4 class="first">Other uses of {e(focus["vessel_id"])}</h4><ol class="alts">{uses}</ol>'
            f'<h4>Other vessels for {e(focus["cargo_id"])}</h4><ol class="alts">{carriers}</ol>')


def _worth_row(w):
    if w["given_up"] is None:
        return (f'<li><b>{e(w["vessel_id"])} → {e(w["cargo_id"])}</b>'
                f'<span>No plan covers every committed cargo without it</span><em>—</em></li>')
    return (f'<li><b>{e(w["vessel_id"])} → {e(w["cargo_id"])}</b><span>Next best: {e(_moves(w["changes"]))}</span>'
            f'<em class="bad">{e(signed(-w["given_up"]))}</em></li>')


def _swap_row(s):
    pair = f'{e(s["pair"][0])} ⇄ {e(s["pair"][1])}'
    if not s["feasible"]:
        why = "; ".join(f"{k} fails {check_names(v)}" for k, v in s["reasons"].items())
        return f'<li class="off"><b>{pair}</b><span>{e(why)}</span><em>—</em></li>'
    tone = "bad" if s["delta"] < -0.5 else ""
    return (f'<li><b>{pair}</b><span>{e(s["pair"][0])} → {e(s["cargoes"][1])}, {e(s["pair"][1])} → {e(s["cargoes"][0])}</span>'
            f'<em class="{tone}">{e(signed(s["delta"]))}</em></li>')


FOOT = ('<p class="foot">Change in total plan contribution. Each option is re-planned so every committed cargo '
        'stays covered.</p>')


def alternatives_view(plan, focus, note):
    """The plan's alternatives: what each pairing is worth and owned-vessel swaps, or every
    other use of a focused vessel and every other vessel for its cargo."""
    if focus:
        with note:
            st.button("Back to whole plan", key="alt_clear",
                      icon=":material/close:", type="tertiary",
                      on_click=focus_row, args=(focus["vessel_id"], focus["cargo_id"], focus["lift"]))
        with st.container(key="alt_scroll"):
            st.html(f'<div class="avail alts-view">{_focused_options(plan, focus)}{FOOT}</div>')
        return
    note.html('<div class="panel-head plan-note"><small>Select a pairing to see every other option</small></div>')
    alts = alternatives(plan["period"])
    with st.container(key="alt_scroll"):
        st.html('<div class="avail alts-view"><h4 class="first">Cost of dropping each pairing</h4></div>')
        lifts = {v["vessel_id"]: v["lift"] for v in plan["voyages"]}
        for w in alts["worth"]:
            with st.container(key=f"plan_row_alt_{w['vessel_id']}"):
                st.html(f'<div class="avail alts-view"><ol class="alts">{_worth_row(w)}</ol></div>')
                st.button(f'Focus {w["vessel_id"]} → {w["cargo_id"]}', key=f"alt_pick_{w['vessel_id']}",
                          on_click=focus_row, args=(w["vessel_id"], w["cargo_id"], lifts[w["vessel_id"]]))
        swaps = "".join(_swap_row(s) for s in alts["swaps"]) or \
            '<li class="off note"><span>Fewer than two owned voyages</span></li>'
        idle = f'<p>Idle owned vessels: {e(", ".join(alts["idle"]))}</p>' if alts["idle"] else ""
        st.html(f'<div class="avail alts-view"><h4>Swap two owned vessels</h4><ol class="alts">{swaps}</ol>{idle}{FOOT}</div>')


def next_availability(plan):
    with st.container(key="availability_panel"):
        st.html('<div class="panel-head"><h3>Next availability</h3><small>Owned and chartered</small></div>')
        st.html(_availability(plan))


def suggestions(plan, focus):
    voyage = focus or plan["tightest"]
    if not voyage:
        return ["Which committed cargoes can the owned fleet cover?"]
    others = [v for v in plan["voyages"] if v is not voyage]
    return [f'Why is {voyage["cargo_id"]} on {voyage["vessel_id"]}?',
            f'Compare all options for {voyage["cargo_id"]} at {voyage["lift"]:,.0f} t',
            f'What drives {others[0]["vessel_id"]}\'s TCE on {others[0]["cargo_id"]}?' if others else "Which voyage has the least laycan slack?"]


def shippy_drawer(plan, focus, render_chat, start_new_chat):
    """Right-side drawer. It stays mounted while closed, so the conversation and any draft survive."""
    st.html('<div class="shippy-backdrop" data-shippy-close></div>')
    with st.container(key="shippy"):
        top, new, close = st.columns([1, .34, .1], vertical_alignment="center", gap="small")
        top.html('<h2 class="shippy-title" id="shippy-title"><span class="lucide icon-message-circle" aria-hidden="true"></span>Ask Shippy</h2>')
        new.button("New chat", icon=":material/add:", key="new_conversation", on_click=start_new_chat, type="tertiary")
        close.html('<button type="button" class="shippy-close" data-shippy-close aria-label="Close assistant">'
                   '<span class="lucide icon-x" aria-hidden="true"></span></button>')
        state = st.session_state
        chip = (f'{state.selected_vessel} → {state.selected_cargo}' if state.get("selected_vessel") and state.get("selected_cargo")
                else "Whole plan")
        note = "selected in plan" if focus else "selected voyage" if chip != "Whole plan" else f'{len(plan["voyages"])} voyages'
        st.html(f'<div class="shippy-context"><small>Context</small><span class="chip">{e(chip)}</span><small>{e(note)}</small></div>')
        render_chat(suggestions=suggestions(plan, focus), compact=True)
