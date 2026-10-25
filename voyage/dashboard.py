"""Reference-inspired dashboard components; all displayed numbers have a source."""
import re
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st



def e(value):
    return escape(str(value))


def usd(value):
    return f"${value:,.0f}"


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d %b, %H:%M")


def apply_theme(dark):
    palette = ({"bg":"#0b1624","panel":"#122337","field":"#182d43","text":"#e1edf9","muted":"#9bb0c7","line":"#2a4056","blue":"#51bcff","bluewash":"#133650","green":"#5dd6a6","greenwash":"#143d36","amber":"#f5c274","amberwash":"#443626"}
               if dark else {"bg":"#f0f4f8","panel":"#ffffff","field":"#f3f6fa","text":"#14243b","muted":"#62768e","line":"#e0e7ef","blue":"#087bf5","bluewash":"#edf6ff","green":"#14885d","greenwash":"#e6f7ef","amber":"#a16a12","amberwash":"#fff2db"})
    variables = ";".join(f"--{key}:{value}" for key, value in palette.items())
    st.html("<style>:root{" + variables + ";color-scheme:" + ("dark" if dark else "light") + ";}" + Path(__file__).with_name("dashboard.css").read_text(encoding="utf-8") + "</style>")


def ship_svg():
    return '''<svg viewBox="0 0 110 92" aria-label="Illustration of a bulk carrier" role="img"><defs><linearGradient id="sea" x2="0" y2="1"><stop stop-color="#36718b"/><stop offset="1" stop-color="#112f44"/></linearGradient></defs><rect width="110" height="92" fill="url(#sea)"/><path d="M0 69 Q30 62 58 72 T110 67 V92 H0Z" fill="#155b78"/><path d="M14 53 L95 49 85 70 27 72Z" fill="#13232f"/><path d="M23 66 L87 63 84 70 27 72Z" fill="#ce6347"/><path d="M30 43 H84 V52 H30Z" fill="#b6bec0"/><path d="M34 41 V28 H48 V43 M35 28 V23 H46 V28" fill="#e9e2cf"/><path d="M57 45 V21 L60 20 61 45 M79 43 V19 L82 18 83 43" fill="#d5c9ac"/><path d="M59 22 L79 39 M81 20 L98 38" stroke="#d7cbb1" stroke-width="2"/><path d="M17 78 Q45 73 75 78 T110 76" stroke="#75c8dc" fill="none" opacity=".7"/></svg>'''


def heading(title, note=""):
    st.html(f'<div class="panel-head"><h3>{e(title)}</h3><small>{e(note)}</small></div>')


def summary_cards(case):
    row = case["row"]
    suffix = " · infeasible case" if not row["feasible"] else " · selected voyage"
    cards = [
        ("◈", "Active Voyages", "—", "Activity history not supplied"),
        ("◉", "Fleet Utilisation", "—", "No fleet occupancy history"),
        ("▣", "Fuel Cost (USD)", usd(row["bunker_cost_usd"]), f'{case["fuel_tonnes"]:,.0f} t consumed' + suffix),
        ("◷", "ETA Reliability", "—", "No actual-versus-planned arrivals"),
        ("↗", "Profit Margin", f'{case["margin_pct"]:.1f}%' if case["margin_pct"] is not None else "—", "Contribution ÷ freight revenue" + suffix),
    ]
    st.html('<div class="kpi-grid">' + "".join(f'<div class="kpi"><div class="kpi-icon">{e(icon)}</div><div><h4>{e(label)}</h4><strong>{e(value)}</strong><small>{e(note)}</small></div></div>' for icon,label,value,note in cards) + '</div>')


def fleet_panel(case, query):
    heading("Fleet Overview", "4 managed / 11 market")
    group = st.radio("Fleet filter", ["Managed", "Market", "All"], horizontal=True, label_visibility="collapsed")
    tables = case["tables"]
    rows = tables["managed_vessels"] if group == "Managed" else tables["market_vessels"] if group == "Market" else tables["managed_vessels"] + tables["market_vessels"]
    with st.container(height=438, border=False):
        found = 0
        for vessel in rows:
            port = case["ports"][vessel["current_port"]]["port_name"]
            if query and query not in f'{vessel["vessel_id"]} {port} {vessel["vessel_class"]}'.lower():
                continue
            found += 1
            managed = vessel["vessel_id"].startswith("MF")
            illustration, description = st.columns([1, 3])
            with illustration:
                st.image(ship_svg(), width="stretch")
            with description:
                st.html(f'<div class="fleet-row"><div><b>{e(vessel["vessel_id"])}</b><p>Capesize bulk carrier</p><p>{float(vessel["dwt_tonnes"]):,.0f} DWT</p><p>{e(port)}</p></div><div class="fleet-meta"><span class="tag {"good" if managed else "warn"}">{"Managed" if managed else "Quote needed"}</span><small>Available {e(stamp(vessel["available_from_utc"]).split(",")[0])}</small></div></div>')
            if managed:
                st.button("Inspect " + vessel["vessel_id"], key="inspect_" + vessel["vessel_id"], on_click=select_vessel, args=(vessel["vessel_id"],), width="stretch")
        if not found:
            st.caption("No vessels match the search.")
    st.caption("Availability dates come from the frozen case. They are not live operating statuses.")


def select_vessel(vessel_id):
    st.session_state.selected_vessel = vessel_id


def route_map(case):
    origin = case["ports"][case["vessel"]["current_port"]]["port_name"]
    load = case["ports"][case["cargo"]["load_port"]]["port_name"]
    discharge = case["ports"][case["cargo"]["discharge_port"]]["port_name"]
    # Diagram positions only: not geographic coordinates or navigation geometry.
    positions = {"CNRIZ": (345, 76), "THLCH": (307, 117), "KRGWG": (367, 69), "CNJTG": (347, 64),
                 "AUPHE": (340, 170), "GNKMS": (189, 108), "BRIGI": (108, 142),
                 "CNLYG": (350, 80), "CNQDG": (352, 73)}
    ox, oy = positions[case["vessel"]["current_port"]]
    lx, ly = positions[case["cargo"]["load_port"]]
    dx, dy = positions[case["cargo"]["discharge_port"]]
    markup = f'''<div class="map-box"><div class="map-title">Route Map <small>FROZEN CASE · SCHEMATIC</small></div>
    <svg viewBox="0 0 430 238" role="img" aria-label="Schematic route from {e(origin)} through {e(load)} to {e(discharge)}">
    <g stroke="#23465c" stroke-width=".7"><path d="M0 45H430M0 90H430M0 135H430M0 180H430M60 0V238M130 0V238M200 0V238M270 0V238M340 0V238M410 0V238"/></g>
    <g fill="#264b60" stroke="#396177" stroke-width="1"><path d="M22 39L66 16 108 32 124 54 102 66 95 89 70 99 57 78 33 73Z"/><path d="M92 102L121 117 130 147 116 180 100 201 92 170 82 137Z"/><path d="M178 45L209 31 238 37 254 21 312 24 365 45 397 72 370 86 351 72 330 100 306 117 286 103 264 84 239 92 219 73 197 76Z"/><path d="M190 84L221 84 249 109 237 142 216 168 199 142 187 110Z"/><path d="M322 165L349 148 381 158 391 181 369 196 339 191Z"/><path d="M295 121L318 129 333 141 320 147 302 136Z"/></g>
    <path d="M{ox} {oy} Q{(ox+lx)/2-24} {(oy+ly)/2} {lx} {ly}" stroke="#65c9f6" stroke-width="2.4" stroke-dasharray="5 5" fill="none"/><path d="M{lx} {ly} Q{(lx+dx)/2+36} {(ly+dy)/2+20} {dx} {dy}" stroke="#13b5f4" stroke-width="3" fill="none"/>
    <g fill="#17c8b2" stroke="#dcffff" stroke-width="2"><circle cx="{ox}" cy="{oy}" r="5"/><circle cx="{lx}" cy="{ly}" r="5"/><circle cx="{dx}" cy="{dy}" r="5"/></g>
    <g fill="#f0f7ff" font-family="sans-serif" font-size="11" font-weight="600"><text x="{ox-8}" y="{oy+20}" text-anchor="end">{e(origin)}</text><text x="{lx}" y="{ly+22}" text-anchor="middle">{e(load)}</text><text x="{dx}" y="{dy-13}" text-anchor="middle">{e(discharge)}</text></g></svg>
    <div class="map-legend">┄ Ballast: {case["row"]["ballast_distance_nm"]:,.0f} nm &nbsp; ━ Laden: {case["row"]["laden_distance_nm"]:,.0f} nm<br>Illustrative positions only. No route geometry, canal routing or live congestion data supplied.</div></div>'''
    svg = re.search(r"<svg.*?</svg>", markup, flags=re.S).group()
    with st.container(key="route_map"):
        st.html('<div class="map-title">Route Map <small>FROZEN CASE · SCHEMATIC</small></div>')
        st.image(svg, width="stretch")
        st.html(markup.split('</svg>', 1)[1].removesuffix('</div>'))


def freight_panel(case, query):
    heading("Freight Planning", "11 cargo opportunities")
    group = st.radio("Cargo filter", ["Committed", "Market"], horizontal=True, label_visibility="collapsed")
    rows = case["tables"]["committed_cargoes" if group == "Committed" else "market_cargoes"]
    body = ""
    for cargo in rows:
        if query and query not in " ".join(cargo.values()).lower():
            continue
        market = cargo["cargo_role"] == "market"
        rate = "Quote needed" if market else f'${float(cargo["contract_freight_rate_usd_per_tonne"]):.2f}'
        body += f'<tr><td><b>{e(cargo["cargo_id"])}</b><br>{e(cargo["commodity"].replace("_"," "))}</td><td>{e(cargo["load_port"])}<br>→ {e(cargo["discharge_port"])}</td><td>{e(rate)}</td><td>{float(cargo["nominal_quantity_tonnes"])/1000:g}k t</td></tr>'
    st.html('<div class="table-wrap"><table class="ocean-table"><thead><tr><th>Cargo</th><th>Route</th><th>USD/t</th><th>Nominal</th></tr></thead><tbody>'+body+'</tbody></table></div>')
    st.caption("No booked/completed statuses or market margins are supplied. Market freight zeros mean missing quotes.")


def voyage_summary(case):
    r, v, c = case["row"], case["vessel"], case["cargo"]
    best = next((x for x in case["comparison"]["rows"] if x["feasible"]), None)
    verdict = f'Highest contribution at this lift: <b>{e(best["vessel_id"])}</b>.' if best else "No managed vessel is feasible at this lift."
    st.html(f'<div class="callout"><b>{e(v["vessel_id"])} / {e(c["cargo_id"])}</b> · {r["selected_lift_tonnes"]:,.0f} tonnes<br>{verdict} {case["feasible_count"]}/4 managed vessels pass all checks. This compares one cargo, not a fleet allocation.</div>')
    if not r["feasible"]:
        st.warning("Selected voyage is infeasible: " + ", ".join(r["failed_checks"]) + ". Its economics are hypothetical, not a recommendation.")
    cards = [("TCE before hire", usd(r["tce_usd_per_day"]),"USD/day"), ("Contribution",usd(r["voyage_contribution_usd"]),"after voyage hire"), ("Voyage duration",f'{r["voyage_days"]:.2f}',"days, including ballast"), ("Laycan slack",f'{r["laycan_slack_days"]:.2f}',"days to closing date")]
    st.html('<div class="metrics-mini">'+''.join(f'<div class="mini"><small>{e(a)}</small><strong>{e(b)}</strong><em>{e(c)}</em></div>' for a,b,c in cards)+'</div>')
    detail = [("Route", case["ports"][c["load_port"]]["port_name"] + " → " + case["ports"][c["discharge_port"]]["port_name"]),
              ("Discharge ETA (UTC)",stamp(case["discharge_eta"])),
              ("Ballast / laden",f'{r["ballast_distance_nm"]:,.0f} / {r["laden_distance_nm"]:,.0f} nm'),
              ("Economical speed",f'{v["economical_ballast_speed_knots"]} / {v["economical_laden_speed_knots"]} kn'),
              ("Sailing draft",f'{r["estimated_sailing_draft_m"]:.2f} m'),
              ("Draft headroom",f'{r["draft_margin_m"]:.2f} m (≥ 0.30 required)'),
              ("Selected / permitted lift",f'{r["selected_lift_tonnes"]/1000:g}k / {float(c["minimum_quantity_tonnes"])/1000:g}–{float(c["maximum_quantity_tonnes"])/1000:g}k t'),
              ("Pricing month",r["bunker_price_period"]+" · "+r["bunker_pricing_location"])]
    st.html('<div class="details">'+''.join(f'<div class="detail"><span>{e(a)}</span><b>{e(b)}</b></div>' for a,b in detail)+'</div>')


def comparison_table(case):
    heading("Managed Vessel Comparison", "Feasible first · contribution ranking")
    body = ""
    for r in case["comparison"]["rows"]:
        body += f'<tr class="{"selected" if r["vessel_id"] == case["vessel"]["vessel_id"] else ""}"><td><b>{e(r["vessel_id"])}</b></td><td><span class="tag {"good" if r["feasible"] else "bad"}">{"Feasible" if r["feasible"] else e(", ".join(r["failed_checks"]))}</span></td><td class="num">{r["voyage_days"]:.2f}</td><td class="num">{usd(r["tce_usd_per_day"])}</td><td class="num">{usd(r["voyage_contribution_usd"])}</td></tr>'
    st.html('<div class="table-wrap"><table class="ocean-table"><thead><tr><th>Vessel</th><th>Checks</th><th>Days</th><th>TCE/day</th><th>Contribution</th></tr></thead><tbody>'+body+'</tbody></table></div>')
    st.caption("USD. Voyage durations differ; this is not a common-horizon fleet optimum.")


def economics(case):
    r = case["row"]
    items = [("Freight revenue",r["freight_revenue_usd"]),("Commission",r["commission_usd"]),("Bunker expense",r["bunker_cost_usd"]),("Port costs",r["port_cost_usd"]),("Canal costs (provisional)",0),("Voyage hire",r["hire_cost_usd"]),("Total costs incl. hire",case["total_cost_usd"]),("Contribution after hire",r["voyage_contribution_usd"])]
    st.html('<div class="details">'+''.join(f'<div class="detail"><span>{e(a)}</span><b>{usd(b)}</b></div>' for a,b in items)+'</div>')
    st.caption(f'Fuel consumed: VLSFO {r["vlsfo_consumption_tonnes"]:,.2f} t · MGO {r["mgo_consumption_tonnes"]:,.2f} t. Purchase requirement: VLSFO {r["vlsfo_purchase_tonnes"]:,.2f} t · MGO {r["mgo_purchase_tonnes"]:,.2f} t.')
    st.caption(f'Days: ballast {r["ballast_days"]:.2f}, waiting {r["laycan_wait_days"]:.2f}, loading {r["loading_days"]:.2f}, laden {r["laden_days"]:.2f}, discharge {r["discharge_days"]:.2f}.')


def timeline(case):
    heading("Voyage Timeline — " + case["vessel"]["vessel_id"], "Calculated schedule · UTC · not live status")
    st.html('<div class="timeline">'+''.join(f'<div class="stop"><b>{e(s["label"])}</b><small>{e(stamp(s["time"]))}</small><small>{e(s["detail"])}</small><em>Estimated</em></div>' for s in case["timeline"])+'</div>')


def requirements_notice():
    st.html('<div class="gap-note"><b>Required next:</b> bunker-price and port-delay scenarios, recommendation-switch thresholds, and market-vessel/cargo comparisons. These are missing from the reference and are not implemented yet. Current results cover managed vessels and committed cargoes.</div>')


def result_frame(case):
    return pd.DataFrame(case["comparison"]["rows"])
