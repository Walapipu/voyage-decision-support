"""Voyages page: every vessel that may carry one cargo, evaluated at one lift.

Managed vessels always; chartered-in market vessels as well when the cargo is committed.

Everything shown comes from the engine rows or the source tables. Items in the
reference sketch without source data (scrubber fitting, AIS density, weather,
bunker-hub stops, live market feeds) are deliberately left out.
"""
from datetime import datetime

import pandas as pd
import streamlit as st

from voyage.market import all_cargoes

from voyage.analysis import STAGES, STAGE_COLOURS
from voyage.dashboard import e, usd, profit_style, select_vessel, heading
from voyage.dashboard_data import suggested_lift
from voyage.decision import OBJECTIVES
from voyage.data import index, load_tables
from voyage.map_view import locations, render_candidate_map
from voyage.search import open_cargoes, search

MAP_LIMIT = 3  # vessels drawn on the map; the cards and table still list every candidate

CHECK_NAMES = {"quantity": "Lift outside range", "laycan": "Laycan missed", "deadweight": "Over deadweight",
               "draft": "Draft margin", "fuel": "Fuel", "port_draft": "Port draft"}


def _utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _when(value, year=False):
    return _utc(value).strftime("%d %b %Y, %H:%M" if year else "%d %b, %H:%M")


def _signed(value, places=2):
    return f'{"+" if value > 0 else "−" if value < 0 else ""}{abs(value):,.{places}f}'


def _sign_style(value):
    return profit_style(1 if value > 0 else -1 if value < 0 else 0)


def _dms(value, positive, negative):
    degrees = abs(value)
    whole = int(degrees)
    return f'{whole}°{round((degrees - whole) * 60):02d}′{positive if value >= 0 else negative}'


def _laycan(cargo):
    opens, closes = _utc(cargo["laycan_start_utc"]), _utc(cargo["laycan_end_utc"])
    return f'{opens:%d}–{closes:%d %b %Y}' if opens.month == closes.month else f'{opens:%d %b} – {closes:%d %b %Y}'


def _ranks(rows):
    return {r["vessel_id"]: i for i, r in enumerate((r for r in rows if r["ranking_eligible"]), 1)}


def _value(cc, value):
    """An objective value in its unit: USD, or USD/day for TCE."""
    return f'{usd(value)}/day' if cc["objective"]["unit"] == "USD/day" else usd(value)


def _phrase(label):
    """'Contribution after hire' -> 'contribution after hire'; TCE keeps its capitals."""
    return label if label.startswith("TCE") else label[0].lower() + label[1:]


def _highest(cc):
    return "Highest " + _phrase(cc["objective"]["label"])


# ---------- Lift suggestion and rank method ----------

def apply_suggested_lift():
    """Fill the lift box with the top-ranked vessel's best lift for the cargo, month and rank method.

    Called from widget callbacks (and before the widgets on a rerun), so the lift box can still be edited."""
    cargo_id = st.session_state.get("selected_cargo")
    objective = st.session_state.get("ranking_objective") or "contribution"
    st.session_state.selected_lift = suggested_lift(cargo_id, st.session_state.get("price_period"), objective) if cargo_id else None
    st.session_state.lift_is_suggested = cargo_id is not None


def lift_edited():
    st.session_state.lift_is_suggested = False


def ranking_basis_changed():
    """A new rank method or price month re-suggests the lift, unless the user typed their own."""
    if st.session_state.get("lift_is_suggested") or not st.session_state.get("selected_lift"):
        apply_suggested_lift()


def rank_method_picker():
    st.selectbox("Rank by", list(OBJECTIVES), format_func=lambda key: "Rank by " + _phrase(OBJECTIVES[key][1]),
                 key="ranking_objective", on_change=ranking_basis_changed, label_visibility="collapsed")


def stem_card(cc):
    cargo, ports = cc["cargo"], cc["ports"]
    load, discharge = ports[cargo["load_port"]], ports[cargo["discharge_port"]]
    place = " · ".join(dict.fromkeys([load["country"], load["region"]]))
    rows = [("Cargo", f'{cargo["cargo_id"]} · {cargo["commodity"].replace("_", " ")}'),
            ("Discharge", f'{discharge["port_name"]} {cargo["discharge_port"]}'),
            ("Lift", "Best per vessel" if cc["per_vessel"] else f'{cc["lift"]:,.0f} t' + (" · suggested" if cc["lift"] == cc["suggested_lift"] else "")),
            ("Permitted", f'{float(cargo["minimum_quantity_tonnes"]):,.0f}–{float(cargo["maximum_quantity_tonnes"]):,.0f} t'),
            ("Laycan", _laycan(cargo)),
            (_freight_label(cargo), f'${float(cargo["contract_freight_rate_usd_per_tonne"]):.2f}/t')]
    st.html(f'<div class="stem-card"><div class="stem-head"><span class="stem-icon"><span class="lucide icon-anchor"></span></span>'
            f'<div><b>{e(load["port_name"])} <span class="code">{e(cargo["load_port"])}</span></b>'
            f'<small>{e(place)} · load port</small></div></div><div class="stem-grid">'
            + "".join(f'<div><small>{e(a)}</small><b>{e(b)}</b></div>' for a, b in rows) + '</div></div>')


def stage_bar(row):
    total = row["voyage_days"] or 1
    parts = "".join(f'<i style="width:{100 * row[key] / total:.2f}%;background:{STAGE_COLOURS[name]}"></i>'
                    for name, key in STAGES.items() if row[key] > 0)
    return f'<div class="stage-bar" role="img" aria-label="Voyage stages, {row["voyage_days"]:.1f} days">{parts}</div>'


def stage_legend():
    return '<div class="stage-legend">' + "".join(
        f'<span><i style="background:{STAGE_COLOURS[name]}"></i>{e(name)}</span>' for name in STAGES) + '</div>'


def candidate_card(row, cc, rank, focus_id):
    vessel = cc["vessels"][row["vessel_id"]]
    port = cc["ports"][vessel["current_port"]]["port_name"]
    feasible = row["feasible"]
    tags = f'<span class="tag">Rank {rank}</span>' if rank else ""
    hired = row["vessel_id"].startswith("MV")
    if rank == 1:
        tags += f'<span class="tag info">{e(_highest(cc))}</span>'
    status = ('<span class="tag good">Feasible</span>' if feasible else
              f'<span class="tag bad">{e(", ".join(CHECK_NAMES.get(c, c) for c in row["failed_checks"]))}</span>')
    head = (f'<div class="cand-head"><span class="cand-id"><i class="dot {"good" if feasible else "bad"}"></i>'
            f'<b class="code">{e(row["vessel_id"])}</b>{tags}</span>{status}</div>'
            f'<p class="cand-spec">{"Chartered in" if hired else "Capesize"} · <span class="num">{float(vessel["dwt_tonnes"]):,.0f}</span> DWT · '
            + (f'Best lift <span class="num">{row["selected_lift_tonnes"]:,.0f}</span> t · ' if cc["per_vessel"] else "") +
            f'Open {e(port)} · {e(_utc(vessel["available_from_utc"]).strftime("%d %b"))}'
            + (f' · hire <span class="num">{e(usd(float(vessel["hire_rate_usd_per_day"])))}</span>/day assumed' if hired else "") + '</p>')
    margin = 100 * row["voyage_contribution_usd"] / row["freight_revenue_usd"] if row["freight_revenue_usd"] else None
    if feasible:
        cells = [("TCE before hire", f'{usd(row["tce_usd_per_day"])}/day', _sign_style(row["tce_usd_per_day"])),
                 ("Contribution", usd(row["voyage_contribution_usd"]), profit_style(margin)),
                 ("Laycan slack", f'{_signed(row["laycan_slack_days"])} days', _sign_style(row["laycan_slack_days"])),
                 ("Summer-draft headroom", f'{row["draft_margin_m"]:.2f} m', "")]
    else:
        cells = [("Laycan slack", f'{_signed(row["laycan_slack_days"])} days', _sign_style(row["laycan_slack_days"])),
                 ("Load arrival (UTC)", _when(row["arrival_at_load_utc"]), ""),
                 ("Summer-draft headroom", f'{_signed(row["draft_margin_m"])} m', _sign_style(row["draft_margin_m"] - row["required_summer_draft_margin_m"])),
                 ("Deadweight margin", f'{_signed(row["deadweight_margin_tonnes"], 0)} t', _sign_style(row["deadweight_margin_tonnes"]))]
    metrics = '<div class="cand-metrics">' + "".join(
        f'<div class="signed-metric" style="{style}"><small>{e(label)}</small><strong>{e(value)}</strong></div>' for label, value, style in cells) + '</div>'
    foot = (f'<div class="cand-foot"><span>Voyage <b class="num">{row["voyage_days"]:.1f}</b> days</span>'
            f'<span>Load ETA <b class="num">{e(_when(row["arrival_at_load_utc"]))}</b></span></div>' + stage_bar(row))
    best = cc["best"]
    note = ""
    metric = cc["objective"]["metric"]
    if feasible and not rank:
        note = '<p class="cand-note">Not ranked: fails the stress scenario.</p>'
    elif feasible and best and rank != 1:
        note = (f'<p class="cand-note">{e(cc["objective"]["label"])} {e(_value(cc, best[metric] - row[metric]))} '
                f'below {e(best["vessel_id"])}.</p>')
    elif not feasible:
        note = f'<p class="cand-note">Economics hypothetical: {e(usd(row["voyage_contribution_usd"]))} contribution if the checks were waived.</p>'
    focus = row["vessel_id"] == focus_id
    with st.container(border=True, key=f'cand_{row["vessel_id"]}'):
        st.html(f'<div class="cand{" cand-focus" if focus else ""}">' + head + metrics + foot + note + '</div>')
        if row["vessel_id"] == st.session_state.get("selected_vessel"):
            st.html('<p class="cand-selected"><i class="dot info"></i>Selected · shown on the map and below</p>')
        else:
            st.button("Select vessel", key=f'pick_{row["vessel_id"]}', on_click=select_vessel, args=(row["vessel_id"],))


def ticker_items(cc, focus):
    """Ticker segments: port positions, the focused route, then each vessel's load-port ETA."""
    cargo, ports = cc["cargo"], cc["ports"]
    where = locations()
    items = [f'{ports[code]["port_name"].upper()} {_dms(where[code]["lat"], "N", "S")} {_dms(where[code]["lon"], "E", "W")}'
             for code in (cargo["load_port"], cargo["discharge_port"])]
    vessel = cc["vessels"][focus["vessel_id"]]
    items.append(f'{focus["vessel_id"]} BALLAST {focus["ballast_distance_nm"]:,.0f} NM + LADEN {focus["laden_distance_nm"]:,.0f} NM')
    items.append(f'ECONOMICAL SPEED {vessel["economical_ballast_speed_knots"]} / {vessel["economical_laden_speed_knots"]} KN')
    for row in cc["rows"]:
        items.append(f'{row["vessel_id"]} ETA {_when(row["arrival_at_load_utc"]).upper()} · SLACK {_signed(row["laycan_slack_days"])} DAYS')
    return items


def ticker(items):
    # Ticker board: the run is doubled so the scroll loops seamlessly; the copy is hidden from screen readers.
    # The motion is a transform-only animation, so the compositor runs it without restyling the page.
    run = "".join(f'<span>{e(item)}</span>' for item in items)
    return (f'<div class="ticker" aria-label="{e(" · ".join(items))}">'
            f'<div class="ticker-track"><div class="ticker-run">{run}</div><div class="ticker-run" aria-hidden="true">{run}</div></div></div>')


def matrix(rows, cc, ranks, focus_id):
    body = ""
    for r in rows:
        v = cc["vessels"][r["vessel_id"]]
        port = cc["ports"][v["current_port"]]["port_name"]
        rank = f'Rank {ranks[r["vessel_id"]]}' if r["vessel_id"] in ranks else "Not ranked"
        status = ('<span class="tag good">Feasible</span>' if r["feasible"] else
                  f'<span class="tag bad">{e(", ".join(CHECK_NAMES.get(c, c) for c in r["failed_checks"]))}</span>')
        slack_style = _sign_style(r["laycan_slack_days"])
        body += (f'<tr class="{"selected" if r["vessel_id"] == focus_id else ""}">'
                 f'<td><b class="code">{e(r["vessel_id"])}</b><small>{e(rank)} · {float(v["dwt_tonnes"]):,.0f} DWT · {e(port)}{f" · lift {r['selected_lift_tonnes']:,.0f} t" if cc["per_vessel"] else ""}</small></td>'
                 f'<td>{status}</td>'
                 f'<td class="num">{e(_when(r["arrival_at_load_utc"]))}<small class="signed-metric" style="{slack_style}"><strong>{_signed(r["laycan_slack_days"])} days slack</strong></small></td>'
                 f'<td class="num">{r["ballast_days"]:.1f} / {r["laden_days"]:.1f} days<small>{r["ballast_distance_nm"]:,.0f} / {r["laden_distance_nm"]:,.0f} nm</small></td>'
                 f'<td class="num">{r["voyage_days"]:.1f} days<small>wait {r["laycan_wait_days"]:.1f} days</small></td>'
                 f'<td class="num">{v["economical_ballast_speed_knots"]} / {v["economical_laden_speed_knots"]} kn</td>'
                 f'<td class="num">{float(v["vlsfo_rob_tonnes"]):,.0f} / {float(v["mgo_rob_tonnes"]):,.0f} t'
                 f'<small>buy {r["vlsfo_purchase_tonnes"]:,.0f} / {r["mgo_purchase_tonnes"]:,.0f} t</small></td>'
                 f'<td class="num">{r["draft_margin_m"]:.2f} m<small>{r["estimated_sailing_draft_m"]:.2f} m sailing</small></td>'
                 f'<td class="num">{usd(r["tce_usd_per_day"])}</td>'
                 f'<td class="num">{usd(r["voyage_contribution_usd"])}</td></tr>')
    head = ("<th>Vessel</th><th>Checks</th><th class='num'>Load ETA / slack</th><th class='num'>Ballast / laden</th>"
            "<th class='num'>Total</th><th class='num'>Speed b / l</th><th class='num'>ROB VLSFO / MGO</th>"
            "<th class='num'>Draft headroom</th><th class='num'>TCE/day</th><th class='num'>Contribution</th>")
    if not body:
        body = '<tr><td colspan="10">No vessels match this filter.</td></tr>'
    return f'<div class="table-wrap matrix-wrap"><table class="ocean-table matrix-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def export_frame(rows, cc):
    frame = pd.DataFrame([{k: v for k, v in r.items() if not isinstance(v, (list, dict))} for r in rows])
    frame["failed_checks"] = [", ".join(r["failed_checks"]) for r in rows]
    frame.insert(0, "lift_tonnes", [r["selected_lift_tonnes"] for r in rows])
    return frame


def _freight_label(cargo):
    return "Assumed freight" if cargo["cargo_id"].startswith("MC") else "Contract freight"


def market_strip(cc):
    cargo = cc["cargo"]
    items = [f'{_freight_label(cargo)} <b>${float(cargo["contract_freight_rate_usd_per_tonne"]):.2f}/t</b>']
    if cc["baltic"]:
        b = cc["baltic"]
        items.append(f'Baltic {e(b["route"])} {e(b["name"])} ({e(b["period"])}) <b>${b["usd_per_tonne"]:.2f}/t</b>, market context only')
    if cc["bunker_prices"]:
        items.append(f'VLSFO <b>${cc["bunker_prices"].get("VLSFO", 0):,.0f}/t</b> · MGO <b>${cc["bunker_prices"].get("MGO", 0):,.0f}/t</b> '
                     f'({e(cc["pricing_location"])}, {e(cc["period"])})')
    best = cc["best"]
    if best:
        items.append(f'{e(_highest(cc))} <b>{e(best["vessel_id"])} ({e(_value(cc, best[cc["objective"]["metric"]]))})</b>')
    elif cc["feasible_count"]:
        items.append('<b>No feasible vessel passes the stress scenario at this lift</b>')
    else:
        items.append('<b>No vessel is feasible at this lift</b>')
    if cc["lead"]:
        lead = cc["lead"]
        pct = f' ({lead["pct"]:.1f}% above)' if lead["pct"] is not None else ""
        items.append(f'Lead over {e(lead["vessel_id"])} <b>+{e(_value(cc, lead["usd"]))}</b>{pct}')
    elif cc["best"]:
        items.append("No feasible runner-up")
    st.html('<div class="market-strip">' + "".join(f'<span>{item}</span>' for item in items) + '</div>')


# ---------- Search: load port or cargo ----------

def _choose_cargo(cargo_id):
    st.session_state.selected_cargo = cargo_id
    # A new cargo starts at the ranking's suggested lift; the lift box in the top strip stays editable.
    apply_suggested_lift()
    st.session_state.voyage_port = None
    st.session_state.voyage_query = None


def _open(key):
    """Act on a search result key: 'cargo:<id>' or 'port:<code>'."""
    kind, _, ident = key.partition(":")
    if kind == "cargo":
        _choose_cargo(ident)
        return
    cargoes = open_cargoes(ident)
    if len(cargoes) == 1:
        _choose_cargo(cargoes[0]["cargo_id"])
    else:
        st.session_state.voyage_port, st.session_state.voyage_query = ident, None


def _on_search():
    value = st.session_state.voyage_search
    browsing = st.session_state.get("voyage_port") or st.session_state.get("voyage_query")
    st.session_state.voyage_port = st.session_state.voyage_query = None
    if value is None:
        if not browsing:  # clearing while viewing a cargo clears that cargo
            st.session_state.selected_cargo = st.session_state.selected_lift = None
        return
    if value.startswith(("cargo:", "port:")):
        _open(value)
        return
    # Free text submitted with Enter: the server-side search, as a live database would run it.
    results = search(value)
    if len(results) == 1:
        _open(f'{results[0]["kind"]}:{results[0]["id"]}')
    else:
        st.session_state.voyage_query = value


def search_bar():
    labels = {f'{r["kind"]}:{r["id"]}': r["label"] for r in search("")}
    port, query, cargo_id = (st.session_state.get(k) for k in ("voyage_port", "voyage_query", "selected_cargo"))
    current = query or (f"port:{port}" if port else None)
    if current is None and cargo_id:
        current = "port:" + all_cargoes()[cargo_id]["load_port"]
    options = list(labels) + ([current] if current and current not in labels else [])
    st.session_state.voyage_search = current
    st.selectbox("Search load port or cargo", options, format_func=lambda k: labels.get(k, k), index=None,
                 key="voyage_search", on_change=_on_search, accept_new_options=True, filter_mode="contains",
                 placeholder="Search port, country, cargo or commodity", label_visibility="collapsed")


def result_list(title, results):
    heading(title, f"{len(results)} found")
    if not results:
        st.caption("No load ports or cargoes match. Try a port, country, commodity or cargo ID.")
    with st.container(key="search_results"):
        for r in results:
            st.button(r["label"], key=f'open_{r["kind"]}_{r["id"]}', on_click=_open, args=(f'{r["kind"]}:{r["id"]}',),
                      type="tertiary", icon=":material/anchor:" if r["kind"] == "port" else ":material/inventory_2:")


def browse_panel():
    """Search results or a port's open cargoes, shown before a cargo is chosen."""
    port, query = st.session_state.get("voyage_port"), st.session_state.get("voyage_query")
    tables = load_tables()
    if port:
        name = index(tables["ports"], "port_code")[port]["port_name"]
        ids = {c["cargo_id"] for c in open_cargoes(port, tables)}
        result_list(f"Open cargoes at {name}", [r for r in search("", tables=tables) if r["kind"] == "cargo" and r["id"] in ids])
    elif query:
        result_list(f'Results for "{query}"', search(query, tables=tables))
    else:
        heading("Find a voyage")
        st.caption("Search a load port or cargo above, or pick a cargo in the top bar. The ranking suggests a lift, "
                   "which you can change. Every vessel that may carry the cargo is then evaluated; choosing a vessel is optional.")


def voyages_page(cc):
    browsing = st.session_state.get("voyage_port") or st.session_state.get("voyage_query")
    if cc is None or browsing:
        with st.container(border=True, key="voyage_start"):
            search_bar()
            rank_method_picker()
            browse_panel()
            if cc is None and st.session_state.get("selected_cargo") and not browsing:
                st.info("Enter a lift in the top bar to evaluate this cargo.")
        return
    rows = cc["rows"]
    ranks = _ranks(rows)
    selected = st.session_state.get("selected_vessel")
    focus = next((r for r in rows if r["vessel_id"] == selected), cc["best"] or rows[0])
    drawn = rows[:MAP_LIMIT] + [r for r in rows[MAP_LIMIT:] if r["vessel_id"] == focus["vessel_id"]]
    with st.container(key="voyages_grid"):
        left, right = st.columns([1, 1.9], gap="small")
        with left, st.container(border=True, key="candidates_panel"):
            search_bar()
            rank_method_picker()
            stem_card(cc)
            if cc["lift"] != cc["suggested_lift"]:
                st.button(f'Use suggested lift ({cc["suggested_lift"]:,.0f} t)', key="use_suggested_lift",
                          on_click=apply_suggested_lift, type="tertiary", icon=":material/restart_alt:")
            labels = {"all": f"All candidates ({len(rows)})", "feasible": f"Feasible ({cc['feasible_count']})"}
            choice = st.radio("Vessel filter", list(labels), format_func=labels.get, horizontal=True,
                              key="voyage_filter", label_visibility="collapsed")
            shown = [r for r in rows if r["feasible"]] if choice == "feasible" else rows
            heading(f"Evaluated vessels ({len(rows)})", f"{cc['feasible_count']} feasible · ranked by {_phrase(cc['objective']['label'])}"
                    + (" · each at its best lift" if cc["per_vessel"] else ""))
            st.html(stage_legend())
            with st.container(key="candidates_scroll"):
                for row in shown:
                    candidate_card(row, cc, ranks.get(row["vessel_id"]), focus["vessel_id"])
                if not shown:
                    st.caption("No vessel passes every check at this lift.")
        with right, st.container(key="voyage_right"):
            with st.container(border=True, key="voyage_map_panel"):
                note = f'Focused: {focus["vessel_id"]}' + ("" if focus["vessel_id"] == selected else " (top ranked)" if cc["best"] else " (none feasible)")
                if len(drawn) < len(rows):
                    note += f' · top {MAP_LIMIT} of {len(rows)} on map'
                heading("Ballast and laden legs", note)
                render_candidate_map(cc["cargo"], drawn, focus["vessel_id"], cc["ports"], cc["vessels"])
                st.html(ticker(ticker_items(cc, focus)))
            with st.container(border=True, key="matrix_panel"):
                title, action = st.columns([1, .28], vertical_alignment="center")
                with title:
                    heading("Voyage specifications and feasibility", f'{cc["cargo"]["cargo_id"]} · {"best lift per vessel" if cc["per_vessel"] else f"{cc['lift']:,.0f} t"} · {cc["period"]} prices · USD')
                with action:
                    st.download_button("Export CSV", export_frame(shown, cc).to_csv(index=False).encode("utf-8"),
                        file_name=f'{cc["cargo"]["cargo_id"]}_{cc["period"]}_vessels.csv', mime="text/csv",
                        icon=":material/download:", key="voyages_export", on_click="ignore")
                st.html(matrix(shown, cc, ranks, focus["vessel_id"]))
    market_strip(cc)
