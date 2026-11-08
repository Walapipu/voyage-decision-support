"""Reference-inspired dashboard components; all displayed numbers have a source."""
from base64 import b64encode
from datetime import datetime
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from voyage.analysis import profit_tone
from voyage.assets import icon_styles
from voyage.map_view import render_home_map
from voyage.fuel import shortage_message
from voyage.dashboard_data import bunker_price_scenarios



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
    # Chart-room graphite: neutral surfaces, one sea-blue accent, toned semantics.
    palette = ({"rail":"#090c12", "bg":"#0d0f13", "panel":"#13161b", "field":"#1b1f25", "raised":"#22272e",
                "line":"rgba(232,236,242,.08)", "linestrong":"rgba(232,236,242,.14)",
                "text":"#e8ebf0", "text2":"#a3a9b5", "muted":"#858c98",
                "blue":"#5aa9f0", "bluewash":"rgba(90,169,240,.13)", "onblue":"#0d0f13",
                "green":"#4cc38a", "greenwash":"rgba(76,195,138,.12)", "amber":"#e0b263", "amberwash":"rgba(224,178,99,.12)",
                "red":"#e5484d", "redwash":"rgba(229,72,77,.12)"}
               if dark else
               {"rail":"#13263d", "bg":"#f6f7f9", "panel":"#ffffff", "field":"#f1f3f6", "raised":"#e8ebf0",
                "line":"rgba(17,24,39,.09)", "linestrong":"rgba(17,24,39,.16)",
                "text":"#111827", "text2":"#4b5565", "muted":"#6b7487",
                "blue":"#0a6fd6", "bluewash":"rgba(10,111,214,.08)", "onblue":"#ffffff",
                "green":"#16803c", "greenwash":"rgba(22,128,60,.08)", "amber":"#9a6410", "amberwash":"rgba(154,100,16,.09)",
                "red":"#c62828", "redwash":"rgba(198,40,40,.08)"})
    variables = ";".join(f"--{key}:{value}" for key, value in palette.items())
    st.html("<style>:root{" + variables + ";color-scheme:" + ("dark" if dark else "light") + ";}" + Path(__file__).with_name("dashboard.css").read_text(encoding="utf-8") + icon_styles() + "</style>")


def heading(title, note=""):
    st.html(f'<div class="panel-head"><h3>{e(title)}</h3><small>{e(note)}</small></div>')


def sparkline(series, period, label):
    if len(series) < 2:
        return ""
    values = [value for _, value in series]
    low, high = min(values), max(values)
    points = [(3 + i * 58 / (len(series) - 1),
               13 if low == high else 23 - 20 * (value - low) / (high - low))
              for i, value in enumerate(values)]
    path = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    marker = next((point for (month, _), point in zip(series, points) if month == period), None)
    dark = st.session_state.get("dark_mode", True)
    colour, outline = ("#5aa9f0", "#13161b") if dark else ("#0a6fd6", "#ffffff")
    dot = (f'<circle cx="{marker[0]:.2f}" cy="{marker[1]:.2f}" r="2.5" fill="{colour}" stroke="{outline}"/>'
           if marker else "")
    title = f"{label} at supplied monthly bunker prices, {series[0][0]} to {series[-1][0]}. Dot marks selected month."
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 26">'
           f'<polyline points="{path}" fill="none" stroke="{colour}" stroke-width="1.6" stroke-linejoin="round"/>{dot}</svg>')
    image = b64encode(svg.encode()).decode("ascii")
    return f'<img class="kpi-spark" src="data:image/svg+xml;base64,{image}" alt="{e(title)}">'


def summary_cards(case):
    row = case["row"] if case else None
    margin = case["margin_pct"] if case else None
    status = ("Feasible" if row["feasible"] else "Infeasible") if row else "No voyage selected"
    scenarios = bunker_price_scenarios(case) if case else []
    period = row["bunker_price_period"] if row else ""
    cards = [
        ("Active Voyages", "—", "No operating data", [], ""),
        ("Fleet Utilisation", "—", "No operating data", [], ""),
        ("Fuel Cost (USD)", usd(row["bunker_cost_usd"]) if row else "—",
         "Bunker price curve" if scenarios else status, [(month, cost) for month, cost, _ in scenarios], ""),
        ("ETA Reliability", "—", "No arrival history", [], ""),
        ("Profit Margin", f"{margin:.1f}%" if margin is not None else "—",
         f"{status} · bunker curve" if scenarios else status,
         [(month, pct) for month, _, pct in scenarios] if margin is not None else [],
         profit_style(margin) if row and row["feasible"] else "--profit-colour:var(--muted);"),
    ]
    tiles = []
    for label, value, note, series, style in cards:
        css_class = "kpi profit-kpi" if style else "kpi"
        tiles.append(f'<div class="{css_class}" style="{style}"><h4>{e(label)}</h4>'
                     f'<div class="kpi-reading"><strong>{e(value)}</strong>{sparkline(series, period, label)}</div>'
                     f'<small>{e(note)}</small></div>')
    st.html('<div class="kpi-grid">' + "".join(tiles) + "</div>")


def fleet_panel(catalog, case):
    heading("Track your ship", "Planning snapshot")
    words = st.text_input("Search vessels, voyages or ports", key="ship_search",
                          placeholder="Search vessel, cargo or port…", label_visibility="collapsed").lower().split()
    tables, ports = catalog["tables"], catalog["ports"]
    st.html('<div class="track-header"><span>Vessel</span><span>Port / route</span><span>Available / ETA (UTC)</span></div>')
    with st.container(height=140, border=False, key="track_scroll"):
        found = False
        for vessel in tables["managed_vessels"] + tables["market_vessels"]:
            vessel_id, code = vessel["vessel_id"], vessel["current_port"]
            port = ports[code]["port_name"]
            route, date = port, stamp(vessel["available_from_utc"]).split(",")[0]
            cargo_id = ""
            if case and vessel_id == case["row"]["vessel_id"]:
                cargo = case["cargo"]
                cargo_id = cargo["cargo_id"]
                route = f'{cargo["load_port"]} → {cargo["discharge_port"]}'
                date = stamp(case["discharge_eta"])
            if not all(word in f"{vessel_id} {code} {port} {route} {cargo_id}".lower() for word in words):
                continue
            found = True
            name, location, timing = st.columns([1, 1.75, 1.35], gap="small", vertical_alignment="center")
            with name:
                if vessel_id.startswith("MF"):
                    st.button(vessel_id, key=f"inspect_{vessel_id}", on_click=select_vessel, args=(vessel_id,), type="tertiary")
                elif st.button(vessel_id, key=f"inspect_{vessel_id}", type="tertiary"):
                    inspect_market_vessel(vessel, port)
            with location:
                st.html(f'<span class="track-value">{e(route)}</span>')
            with timing:
                st.html(f'<span class="track-value">{e(date)}</span>')
        if not found:
            st.caption("No vessels match the search.")


@st.dialog("Vessel details")
def inspect_market_vessel(vessel, port):
    st.subheader(vessel["vessel_id"])
    st.write(f'Capesize bulk carrier · {float(vessel["dwt_tonnes"]):,.0f} DWT · {port}')
    st.dataframe(pd.DataFrame([vessel]).T.rename(columns={0:"Value"}), width="stretch")


def select_vessel(vessel_id):
    st.session_state.selected_vessel = vessel_id


def route_map(case, catalog):
    with st.container(key="home_map"):
        note = "Feasible candidate TCE · USD/day" if case else "Calculate a voyage to show TCE heat"
        heading("TCE heat map", note)
        render_home_map(case, catalog)


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
        heading("Managed vessel comparison", "Feasible first · contribution ranking")
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
    heading("Voyage timeline · " + case["vessel"]["vessel_id"], "Estimated schedule, UTC")
    st.html(laycan_track(case) + '<div class="timeline">'+''.join(f'<div class="stop"><b>{e(s["label"])}</b><small>{e(stamp(s["time"]))}</small><small>{e(s["detail"])}</small></div>' for s in case["timeline"])+'</div>')


def _utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def laycan_track(case):
    """Signature detail: the laycan window drawn to scale on the voyage, with slack to close."""
    stops = [_utc(s["time"]) for s in case["timeline"]]
    first, last = stops[0], stops[-1]
    span = (last - first).total_seconds() or 1
    def at(moment):
        return max(0.0, min(100.0, 100 * (moment - first).total_seconds() / span))
    opens, closes = _utc(case["cargo"]["laycan_start_utc"]), _utc(case["cargo"]["laycan_end_utc"])
    window = f'{opens:%d}–{closes:%d %b}' if opens.month == closes.month else f'{opens:%d %b} – {closes:%d %b}'
    slack = case["row"]["laycan_slack_days"]
    left, right = at(opens), at(closes)
    edge = "end" if left > 55 else "start"
    # Load arrival is drawn last so a stop at the same instant cannot cover it.
    order = [i for i in range(len(stops)) if i != 1] + [1]
    ticks = "".join(f'<i class="tick{" arrival" if i == 1 else ""}" style="left:{at(stops[i]):.2f}%"></i>' for i in order)
    return (f'<div class="laycan-track {"late" if slack < 0 else ""}" role="img" aria-label="Laycan {e(window)}; load arrival {e(stamp(case["timeline"][1]["time"]))}; {slack:.1f} days to laycan close">'
            f'<span class="laycan-band" style="left:{left:.2f}%;width:{max(right - left, 0.6):.2f}%"><em class="{edge}">Laycan {e(window)} · {slack:.1f} d slack</em></span>'
            f'{ticks}</div>')


def requirements_notice():
    st.html('<div class="gap-note"><b>Analysis coverage</b> · managed vessels and committed cargoes. Market comparisons and bunker-price / port-delay scenarios are not yet available.</div>')


def result_frame(case):
    return pd.DataFrame(case["comparison"]["rows"])
