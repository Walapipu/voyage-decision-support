"""Reference-inspired dashboard components; all displayed numbers have a source."""
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from voyage.assets import icon_styles, vessel_photo
from voyage.map_view import render_map



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
    st.html("<style>:root{" + variables + ";color-scheme:" + ("dark" if dark else "light") + ";}" + Path(__file__).with_name("dashboard.css").read_text(encoding="utf-8") + icon_styles() + "</style>")


def heading(title, note=""):
    st.html(f'<div class="panel-head"><h3>{e(title)}</h3><small>{e(note)}</small></div>')


def summary_cards(case):
    row = case["row"]
    suffix = " · infeasible case" if not row["feasible"] else " · selected voyage"
    cards = [
        ("ship", "Active Voyages", "—", "Activity history not supplied"),
        ("chart-pie", "Fleet Utilisation", "—", "No fleet occupancy history"),
        ("fuel", "Fuel Cost (USD)", usd(row["bunker_cost_usd"]), f'{case["fuel_tonnes"]:,.0f} t consumed' + suffix),
        ("clock", "ETA Reliability", "—", "No actual-versus-planned arrivals"),
        ("trending-up", "Profit Margin", f'{case["margin_pct"]:.1f}%' if case["margin_pct"] is not None else "—", "Contribution ÷ freight revenue" + suffix),
    ]
    st.html('<div class="kpi-grid">' + "".join(f'<div class="kpi"><div class="kpi-icon"><span class="lucide icon-{e(icon)}"></span></div><div><h4>{e(label)}</h4><strong>{e(value)}</strong><small>{e(note)}</small></div></div>' for icon,label,value,note in cards) + '</div>')


def fleet_panel(case, query):
    heading("Fleet Overview", "4 managed / 11 market")
    group = st.radio("Fleet filter", ["Managed", "Market", "All"], horizontal=True, label_visibility="collapsed")
    tables = case["tables"]
    rows = tables["managed_vessels"] if group == "Managed" else tables["market_vessels"] if group == "Market" else tables["managed_vessels"] + tables["market_vessels"]
    with st.container(height=400, border=False, key="fleet_scroll"):
        found = 0
        for vessel in rows:
            port = case["ports"][vessel["current_port"]]["port_name"]
            if query and query not in f'{vessel["vessel_id"]} {port} {vessel["vessel_class"]}'.lower():
                continue
            found += 1
            managed = vessel["vessel_id"].startswith("MF")
            illustration, description = st.columns([1, 3])
            with illustration:
                st.image(vessel_photo(vessel["vessel_id"]), width="stretch")
            with description:
                st.html(f'<div class="fleet-row"><div><b>{e(vessel["vessel_id"])}</b><p>Capesize bulk carrier</p><p>{float(vessel["dwt_tonnes"]):,.0f} DWT</p><p>{e(port)}</p></div><div class="fleet-meta"><span class="tag {"good" if managed else "warn"}">{"Managed" if managed else "Quote needed"}</span><small>Available {e(stamp(vessel["available_from_utc"]).split(",")[0])}</small></div></div>')
            if managed:
                st.button("Inspect " + vessel["vessel_id"], key="inspect_" + vessel["vessel_id"], on_click=select_vessel, args=(vessel["vessel_id"],), width="stretch")
        if not found:
            st.caption("No vessels match the search.")
    st.caption("Representative ship photos · fictional fleet. Credits in Documents.")


def select_vessel(vessel_id):
    st.session_state.selected_vessel = vessel_id


def route_map(case):
    with st.container(key="route_map"):
        heading("Route Map", "OpenStreetMap · zoom to explore")
        render_map(case)


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


def voyage_summary(case, compact=False):
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
    details_html = '<div class="details">'+''.join(f'<div class="detail"><span>{e(a)}</span><b>{e(b)}</b></div>' for a,b in detail)+'</div>'
    if compact:
        with st.expander("Route, ETA and draft checks"):
            st.html(details_html)
    else:
        st.html(details_html)


def comparison_table(case, compact=False):
    if not compact:
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
