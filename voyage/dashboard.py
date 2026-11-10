"""Reference-inspired dashboard components; all displayed numbers have a source."""
from datetime import datetime
from functools import lru_cache
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from voyage.analysis import profit_tone
from voyage.assets import icon_styles
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
    # Chart-room graphite: neutral surfaces, one sea-blue accent, toned semantics.
    palette = ({"rail":"#0a0c0f", "bg":"#0d0f13", "panel":"#13161b", "field":"#1b1f25", "raised":"#22272e",
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
    # The rail follows the theme: graphite in dark mode, harbour navy in light mode.
    palette.update({"railtext":"#e8ebf0", "railtext2":"#a3a9b5", "railmuted":"#858c98", "railfield":"#16191e",
                    "railraised":"#1d2127", "railline":"rgba(232,236,242,.08)", "railaccent":"#5aa9f0"}
                   if dark else
                   {"railtext":"#edf4fd", "railtext2":"#c1d0e4", "railmuted":"#a1b4cc", "railfield":"#1c334c",
                    "railraised":"#203e5d", "railline":"rgba(255,255,255,.13)", "railaccent":"#7fc2ff"})
    variables = ";".join(f"--{key}:{value}" for key, value in palette.items())
    st.html("<style>:root{" + variables + ";color-scheme:" + ("dark" if dark else "light") + ";}" + _stylesheet() + "</style>")


@lru_cache(maxsize=1)
def _stylesheet():
    return Path(__file__).with_name("dashboard.css").read_text(encoding="utf-8") + icon_styles()


def heading(title, note=""):
    st.html(f'<div class="panel-head"><h3>{e(title)}</h3><small>{e(note)}</small></div>')


def select_vessel(vessel_id):
    st.session_state.selected_vessel = vessel_id


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
        plan = r["bunker_plan"]
        st.caption(f'Planned fuel at {plan["current_port"]} before ballast and {plan["load_port"]} on arrival at loading (tonnes).')
        st.dataframe(pd.DataFrame(plan["by_grade"]).T)
        st.caption("The opening-fuel diagnostic below shows balances before any planned replenishment.")
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
              ("Tightest draft headroom",f'{r["limiting_draft_margin_m"]:.3f} m'),
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
    st.html('<div class="gap-note"><b>Analysis coverage</b> · managed vessels and committed cargoes. Stress rankings use the stated scenario. Market quotes and fleet allocation are outside this comparison.</div>')


def result_frame(case):
    return pd.DataFrame(case["comparison"]["rows"])
