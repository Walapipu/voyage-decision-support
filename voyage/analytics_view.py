"""Analytics page: a fleet-by-cargo dashboard built entirely from voyage-engine rows.

Filters sit in one row above the charts. The bunker month comes from the workspace strip;
clicking a bubble in the TCE chart (or choosing a vessel and cargo in the strip) focuses one
pairing, which the heat map, line charts and the detail panel then follow.
"""
from datetime import datetime

import pandas as pd
import streamlit as st

from voyage import analytics_charts as charts
from voyage import analytics_data as data
from voyage.charts import cost_chart
from voyage.dashboard import e, heading
from voyage.ui import open_in_voyages

CONFIG = {"displaylogo": False, "displayModeBar": "hover", "scrollZoom": False,
          "modeBarButtonsToRemove": ["zoom2d", "pan2d", "select2d", "lasso2d", "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d"],
          "toImageButtonOptions": {"format": "png", "scale": 2}}


def money(value):
    return f"${value / 1e6:,.2f}M" if abs(value) >= 1e6 else f"${value:,.0f}"


def _month(period):
    return datetime.strptime(period, "%Y-%m").strftime("%b %Y") if period else "Laycan month"


def _focus(rows):
    """Clicked pairing, else the strip's vessel and cargo, else the best feasible pairing."""
    state = st.session_state
    keys = {(r["vessel_id"], r["cargo_id"]): r for r in rows}
    for candidate in (state.get("analytics_focus"), (state.get("selected_vessel"), state.get("selected_cargo"))):
        if candidate and tuple(candidate) in keys:
            return keys[tuple(candidate)]
    feasible = [r for r in rows if r["feasible"]]
    return max(feasible, key=lambda r: r["voyage_contribution_usd"]) if feasible else (rows[0] if rows else None)


def _on_pick():
    event = st.session_state.get("an_scatter")
    points = (event or {}).get("selection", {}).get("points", [])
    if points and points[0].get("customdata"):
        st.session_state.analytics_focus = tuple(points[0]["customdata"].split("|"))


FEASIBLE_ONLY = "Feasible only"
# Button labels only; charts and notes keep the full wording from data.BASES.
SHORT_BASES = {"best": "Best feasible", "nominal": "Contract qty", "min": "Contract min", "max": "Contract max"}


def filters(report_button):
    with st.container(key="an_filters", horizontal=True, vertical_alignment="bottom", gap="small"):
        st.segmented_control("Lift basis", list(data.BASES), format_func=SHORT_BASES.get, key="an_basis", default="best", required=True)
        st.pills("Vessels", data.vessel_ids(), selection_mode="multi", key="an_vessels", default=data.vessel_ids())
        st.pills("Cargoes", data.cargo_ids(), selection_mode="multi", key="an_cargoes", default=data.cargo_ids())
        # A one-option pill rather than a toggle, so it matches the other buttons in size and theme.
        st.pills("Show", [FEASIBLE_ONLY], selection_mode="single", key="an_show")
        with st.container(key="an_report"):
            report_button()


def kpis(rows, period):
    s = data.summary(rows)
    best, tight = s["best"], s["tightest"]
    tiles = [
        ("Feasible pairings", f'{s["feasible"]} of {s["count"]}', "pass every check", "" if s["feasible"] else "warn"),
        ("Best contribution", money(best["voyage_contribution_usd"]) if best else "—",
         f'{best["vessel_id"]} → {best["cargo_id"]} · {best["selected_lift_tonnes"]:,.0f} t' if best else "no feasible pairing", ""),
        ("Avg TCE, feasible", f'{money(s["avg_tce"])}/day' if s["avg_tce"] is not None else "—", "before hire", ""),
        ("Avg bunker cost", money(s["bunker_cost"]) if s["bunker_cost"] is not None else "—", f"per feasible voyage · {_month(period)} curve", ""),
        ("Tightest laycan slack", f'{tight["laycan_slack_days"]:.1f} d' if tight else "—",
         f'{tight["vessel_id"]} → {tight["cargo_id"]}' if tight else "no feasible pairing",
         "warn" if tight and tight["laycan_slack_days"] < 3 else ""),
    ]
    st.html('<div class="kpi-grid">' + "".join(
        f'<div class="kpi {tone}"><h4>{e(label)}</h4><strong>{e(value)}</strong><small>{e(note)}</small></div>'
        for label, value, note, tone in tiles) + "</div>")


def panel(key, title, note=""):
    box = st.container(border=True, key=key)
    with box:
        heading(title, note)
    return box


def detail(focus, dark):
    row = focus
    m = data.margin(row)
    facts = [("Lift", f'{row["selected_lift_tonnes"]:,.0f} t'), ("Freight revenue", money(row["freight_revenue_usd"])),
             ("Contribution", money(row["voyage_contribution_usd"]) + (f" · {m:.1f}%" if m is not None else "")),
             ("TCE before hire", f'{money(row["tce_usd_per_day"])}/day'), ("Voyage", f'{row["voyage_days"]:.1f} days'),
             ("Laycan slack", f'{row["laycan_slack_days"]:+.1f} d'), ("Draft headroom", f'{row["limiting_draft_margin_m"]:.3f} m'),
             ("Deadweight margin", f'{row["deadweight_margin_tonnes"]:,.0f} t'),
             ("Bunkers bought", f'{row["vlsfo_purchase_tonnes"]:,.0f} t VLSFO · {row["mgo_purchase_tonnes"]:,.0f} t MGO')]
    status = ('<span class="tag good">Feasible</span>' if row["feasible"] else
              f'<span class="tag bad">Fails: {e(charts.failed(row))}</span>')
    left, right = st.columns([1, 1.5], gap="medium")
    with left:
        st.html(f'<div class="an-facts">{status}<dl>' + "".join(f'<dt>{e(a)}</dt><dd>{e(b)}</dd>' for a, b in facts) + '</dl></div>')
        st.button("Open in Voyages", icon=":material/arrow_forward:", key="an_open", on_click=open_in_voyages, args=(row,))
    with right:
        st.plotly_chart(cost_chart(row, dark).update_layout(height=260, title=None, margin=dict(t=8)), width="stretch",
                        theme=None, key="an_waterfall", config=CONFIG)


def table(rows, period):
    frame = pd.DataFrame([{
        "Vessel": r["vessel_id"], "Cargo": r["cargo_id"], "Lift t": r["selected_lift_tonnes"],
        "Status": "Feasible" if r["feasible"] else "Fails: " + charts.failed(r),
        "TCE $/day": r["tce_usd_per_day"], "Contribution $": r["voyage_contribution_usd"], "Margin %": data.margin(r),
        "Revenue $": r["freight_revenue_usd"], "Hire $": r["hire_cost_usd"], "Bunkers $": r["bunker_cost_usd"],
        "Ports $": r["port_cost_usd"], "Commission $": r["commission_usd"], "Days": r["voyage_days"],
        "Ballast d": r["ballast_days"], "Slack d": r["laycan_slack_days"], "Draft headroom m": r["limiting_draft_margin_m"],
        "DWT margin t": r["deadweight_margin_tonnes"]} for r in rows])
    whole = ["Lift t", "TCE $/day", "Contribution $", "Revenue $", "Hire $", "Bunkers $", "Ports $", "Commission $", "DWT margin t"]
    frame[whole] = frame[whole].round(0).astype("int64")
    money_col = lambda label: st.column_config.NumberColumn(label, format="localized")
    st.dataframe(frame, hide_index=True, width="stretch", height=min(38 * (len(frame) + 1) + 4, 480), key="an_table",
                 column_config={"Lift t": st.column_config.NumberColumn(format="localized"),
                                "TCE $/day": money_col("TCE $/day"), "Contribution $": money_col("Contribution $"),
                                "Revenue $": money_col("Revenue $"), "Hire $": money_col("Hire $"), "Bunkers $": money_col("Bunkers $"),
                                "Ports $": money_col("Ports $"), "Commission $": money_col("Commission $"),
                                "Margin %": st.column_config.NumberColumn(format="%.1f%%"),
                                "Days": st.column_config.NumberColumn(format="%.1f"), "Ballast d": st.column_config.NumberColumn(format="%.1f"),
                                "Slack d": st.column_config.NumberColumn(format="%+.1f"),
                                "Draft headroom m": st.column_config.NumberColumn(format="%.2f"),
                                "DWT margin t": st.column_config.NumberColumn(format="localized")})
    st.download_button("Export CSV", frame.to_csv(index=False).encode("utf-8"), file_name=f"kingfish_pairings_{period or 'laycan'}.csv",
                       mime="text/csv", icon=":material/download:", key="an_csv", on_click="ignore")


def analytics_page(report_button, ranking_panel):
    state = st.session_state
    period, dark = state.price_period, state.get("dark_mode", True)
    heading("Fleet analytics", f"Bunkers priced at {_month(period)}" if period else "Bunkers priced at each cargo's laycan month")
    filters(report_button)
    ranking_panel()
    basis = state.get("an_basis") or "best"
    vessels = state.get("an_vessels") or data.vessel_ids()
    cargoes = state.get("an_cargoes") or data.cargo_ids()
    vessels = [v for v in data.vessel_ids() if v in vessels]
    cargoes = [c for c in data.cargo_ids() if c in cargoes]
    rows = data.grid(period, basis, vessels, cargoes, state.get("an_show") == FEASIBLE_ONLY)
    kpis(rows, period)
    if not rows:
        st.info("No pairing matches these filters. Turn off Feasible only, add vessels or cargoes, or switch the lift basis.")
        return
    focus_row = _focus(rows)
    focus = (focus_row["vessel_id"], focus_row["cargo_id"])
    shown_vessels = [v for v in vessels if any(r["vessel_id"] == v for r in rows)]
    shown_cargoes = [c for c in cargoes if any(r["cargo_id"] == c for r in rows)]
    basis_note = data.BASES[basis].lower()

    with st.container(key="an_row1"):
        left, right = st.columns([1, 1.15], gap="small")
        with left, panel("an_heat", "Contribution by vessel and cargo", f"after hire · {basis_note}"):
            st.plotly_chart(charts.heatmap(rows, shown_vessels, shown_cargoes, focus, dark), width="stretch", theme=None, key="an_heatmap", config=CONFIG)
            st.caption("Empty cells fail a check; the check is named. Outlined cell is the focus.")
        with right, panel("an_tce", "TCE against laycan slack", "bubble area is contribution · click a bubble to focus it"):
            st.plotly_chart(charts.scatter(rows, focus, dark), width="stretch", theme=None, key="an_scatter", config=CONFIG,
                            on_select=_on_pick, selection_mode="points")
    with st.container(key="an_row2"):
        left, right = st.columns(2, gap="small")
        with left, panel("an_costs", "Where the freight revenue goes", "share of revenue · highest margin at the bottom"):
            st.plotly_chart(charts.cost_share(rows, dark), width="stretch", theme=None, key="an_cost_share", config=CONFIG)
        with right, panel("an_time", "Voyage time by stage", "open position to discharge complete"):
            st.plotly_chart(charts.stages(rows, dark), width="stretch", theme=None, key="an_stages", config=CONFIG)
    with st.container(key="an_row3"):
        left, right = st.columns([1.3, 1], gap="small")
        with left, panel("an_months", "Bunker-month sensitivity", f"contribution by pricing month · {basis_note} · open marker fails a check"):
            series = data.month_series(basis, shown_vessels, shown_cargoes)
            st.plotly_chart(charts.months(series, shown_cargoes, shown_vessels, focus, dark), width="stretch", theme=None,
                            key="an_month_lines", config=CONFIG)
        cargo = next(c for c in data.load_tables()["committed_cargoes"] if c["cargo_id"] == focus[1])
        with right, panel("an_lift", f"Lift sensitivity · {focus[1]}", "contract range · dotted where a check fails"):
            curves = {v: data.lift_curve(v, focus[1], period) for v in shown_vessels}
            st.plotly_chart(charts.lift_sensitivity(curves, cargo, (*focus, focus_row["selected_lift_tonnes"]), dark),
                            width="stretch", theme=None, key="an_lift_lines", config=CONFIG)
    with panel("an_focus", f"Focus · {focus[0]} → {focus[1]}", "revenue to contribution · click another bubble to change"):
        detail(focus_row, dark)
    with panel("an_data", "All pairings", f"{len(rows)} rows · sortable · same data as the charts"):
        table(rows, period)
