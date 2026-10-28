"""Reference-inspired dashboard components; all displayed numbers have a source."""
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from voyage.analysis import profit_tone
from voyage.assets import icon_styles, vessel_photo
from voyage.map_view import render_map
from voyage.fuel import shortage_message



def e(value):
    return escape(str(value))


def usd(value):
    return f"${value:,.0f}"


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%d %b, %H:%M")


def profit_style(value):
    colour, strength = profit_tone(value, st.session_state.get("dark_mode", True))
    return f'--profit-colour:{colour};--profit-wash:{colour}{int(20 + 35 * strength):02x};'


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
        ("ship", "Active Voyages", "—", "Not connected"),
        ("chart-pie", "Fleet Utilisation", "—", "Not connected"),
        ("fuel", "Fuel Cost (USD)", usd(row["bunker_cost_usd"]), f'{case["fuel_tonnes"]:,.0f} t consumed' + suffix),
        ("clock", "ETA Reliability", "—", "Not connected"),
        ("trending-up", "Profit Margin", f'{case["margin_pct"]:.1f}%' if case["margin_pct"] is not None else "—", "Contribution ÷ freight revenue" + suffix),
    ]
    tiles = []
    for icon, label, value, note in cards:
        is_profit = label == "Profit Margin"
        style = profit_style(case["margin_pct"]) if is_profit else ""
        gradient = ''
        if is_profit and case["margin_pct"] is not None:
            position = max(0, min(100, 50 + case["margin_pct"] * 2))
            gradient = f'<div class="profit-scale" title="Display scale: −25% to +25%; zero is break-even. Not an industry rating."><i style="left:{position:.1f}%"></i></div>'
        tiles.append(f'<div class="kpi {"profit-kpi" if is_profit else ""}" style="{style}"><div class="kpi-icon"><span class="lucide icon-{e(icon)}"></span></div><div class="kpi-body"><h4>{e(label)}</h4><strong>{e(value)}</strong><small>{e(note)}</small>{gradient}</div></div>')
    st.html('<div class="kpi-grid">' + ''.join(tiles) + '</div>')


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
                if managed:
                    st.button(vessel["vessel_id"], key="inspect_" + vessel["vessel_id"], on_click=select_vessel, args=(vessel["vessel_id"],), type="tertiary")
                else:
                    if st.button(vessel["vessel_id"], key="inspect_" + vessel["vessel_id"], type="tertiary"):
                        inspect_market_vessel(vessel, port)
                st.html(f'<div class="fleet-row"><div><p>Capesize bulk carrier</p><p>{float(vessel["dwt_tonnes"]):,.0f} DWT</p><p>{e(port)}</p></div><div class="fleet-meta"><span class="tag {"good" if managed else "warn"}">{"Managed" if managed else "Quote needed"}</span><small>Available {e(stamp(vessel["available_from_utc"]).split(",")[0])}</small></div></div>')
        if not found:
            st.caption("No vessels match the search.")


@st.dialog("Vessel details")
def inspect_market_vessel(vessel, port):
    st.subheader(vessel["vessel_id"])
    st.write(f'Capesize bulk carrier · {float(vessel["dwt_tonnes"]):,.0f} DWT · {port}')
    st.dataframe(pd.DataFrame([vessel]).T.rename(columns={0:"Value"}), width="stretch")


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


def voyage_summary(case, compact=False):
    r, v, c = case["row"], case["vessel"], case["cargo"]
    best = next((x for x in case["comparison"]["rows"] if x["feasible"]), None)
    verdict = f'Highest contribution at this lift: <b>{e(best["vessel_id"])}</b>.' if best else "No managed vessel is feasible at this lift."
    st.html(f'<div class="callout"><b>{e(v["vessel_id"])} / {e(c["cargo_id"])}</b> · {r["selected_lift_tonnes"]:,.0f} tonnes<br>{verdict} {case["feasible_count"]}/4 managed vessels pass all checks. This compares one cargo, not a fleet allocation.</div>')
    if not r["feasible"]:
        st.warning("Selected voyage is infeasible: " + ", ".join(r["failed_checks"]) + ". Its economics are hypothetical, not a recommendation.")
    if not r["fuel_pass"]:
        st.info("Replenishment plan required. " + shortage_message(r))
    for warning in r['warnings']:
        st.info(warning)
    with st.expander("Fuel diagnostic and port draft checks"):
        st.caption("Opening ROB without replenishment: a diagnostic, not the assumed fuel-delivery plan. Negative balances show where replenishment is needed. Reserve timing remains unconfirmed.")
        st.dataframe(pd.DataFrame(r["fuel_ledger"]), hide_index=True, width="stretch")
        st.caption('Port comparisons use the same laden-departure draft. Current-port and stage-specific drafts are not modelled.')
        st.dataframe(pd.DataFrame(r['port_draft_checks']), hide_index=True, width='stretch')
    cards = [("TCE before hire", usd(r["tce_usd_per_day"]),"USD/day"), ("Contribution",usd(r["voyage_contribution_usd"]),"after voyage hire"), ("Voyage duration",f'{r["voyage_days"]:.2f}',"days, including ballast"), ("Laycan slack",f'{r["laycan_slack_days"]:.2f}',"days to closing date")]
    values = [r["tce_usd_per_day"], r["voyage_contribution_usd"], None, r["laycan_slack_days"]]
    minis = []
    for (label, value, note), numeric in zip(cards, values):
        style = profit_style(100 * r["voyage_contribution_usd"] / r["freight_revenue_usd"] if r["freight_revenue_usd"] else None) if label == "Contribution" else profit_style(1 if numeric is not None and numeric > 0 else -1 if numeric is not None and numeric < 0 else 0)
        minis.append(f'<div class="mini {"signed-metric" if numeric is not None else ""}" style="{style}"><small>{e(label)}</small><strong>{e(value)}</strong><em>{e(note)}</em></div>')
    st.html('<div class="metrics-mini">'+''.join(minis)+'</div>')
    detail = [("Route", case["ports"][c["load_port"]]["port_name"] + " → " + case["ports"][c["discharge_port"]]["port_name"]),
              ("Discharge ETA (UTC)",stamp(case["discharge_eta"])),
              ("Ballast / laden",f'{r["ballast_distance_nm"]:,.0f} / {r["laden_distance_nm"]:,.0f} nm'),
              ("Economical speed",f'{v["economical_ballast_speed_knots"]} / {v["economical_laden_speed_knots"]} kn'),
              ("Sailing draft",f'{r["estimated_sailing_draft_m"]:.2f} m'),
              ("Summer-draft headroom",f'{r["draft_margin_m"]:.2f} m (≥ {r["required_summer_draft_margin_m"]:.2f} required)'),
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
    heading("Voyage Timeline — " + case["vessel"]["vessel_id"], "Estimated schedule · UTC")
    st.html('<div class="timeline">'+''.join(f'<div class="stop"><b>{e(s["label"])}</b><small>{e(stamp(s["time"]))}</small><small>{e(s["detail"])}</small><em>Estimated</em></div>' for s in case["timeline"])+'</div>')


def requirements_notice():
    st.html('<div class="gap-note"><b>Analysis coverage:</b> managed vessels and committed cargoes. Market comparisons and bunker-price / port-delay scenarios are not yet available.</div>')


def result_frame(case):
    return pd.DataFrame(case["comparison"]["rows"])
