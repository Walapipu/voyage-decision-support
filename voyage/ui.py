"""Analyst dashboards rendered inside assistant replies from engine evidence."""
from html import escape
import streamlit as st
from voyage.analysis import analyst_facts, profit_tone, result_frame
from voyage.charts import earnings_chart, cost_chart, duration_chart
from voyage.fuel import shortage_message
from voyage.decision import OBJECTIVES


def open_in_voyages(row):
    """Answer action: show this comparison on the Voyages page."""
    st.session_state.update(page="Voyages", selected_vessel=row["vessel_id"], selected_cargo=row["cargo_id"],
                            selected_lift=float(row["selected_lift_tonnes"]), price_period=row.get("bunker_price_override", row["bunker_price_period"]),
                            voyage_port=None, voyage_query=None)


def compact_evidence(output, key):
    """Show the selected objective and feasibility in the drawer or a ranking panel."""
    rows = output["rows"]
    lead = rows[0]
    ranking = output.get("ranking")
    objective = ranking["objective"] if ranking else "contribution"
    metric, label, _ = OBJECTIVES[objective]
    lead_eligible = lead.get("ranking_eligible", lead["feasible"])
    if ranking:
        if lead_eligible:
            st.html(f'<div class="report-head"><b>{escape(label)} · {escape(lead["vessel_id"])} / {escape(lead["cargo_id"])}</b>'
                    f'<span>{lead["selected_lift_tonnes"]:,.0f} t · {escape(lead["bunker_price_period"])}</span></div>')
            st.caption(ranking["status"])
        else:
            st.caption("No voyage passes the checks for this objective.")
        if objective == "stress_contribution":
            scenario = output["stress_scenario"]
            st.caption(f'Stress case · bunkers +{scenario["bunker_increase"]:.0%} · '
                       f'port charges +{scenario["port_cost_increase"]:.0%} · '
                       f'{scenario["idle_delay_days"]:g} extra idle days at loading')
    body = []
    for row in rows:
        eligible = row.get("ranking_eligible", row["feasible"])
        reasons = row["failed_checks"] or row.get("stress_failed_checks", [])
        note = "best" if row is lead and eligible else "feasible" if eligible else ", ".join(reasons)
        body.append(
            f'<tr class="{"lead" if row is lead and eligible else ""}"><td><b>{escape(row["vessel_id"])}</b>'
            f'<small>{row["selected_lift_tonnes"]:,.0f} t</small></td>'
            f'<td class="num {"neg" if row[metric] < 0 else ""}">&#36;{row[metric]:,.0f}</td>'
            f'<td class="num">{row["laycan_slack_days"]:.1f} d</td><td>{escape(note)}</td></tr>'
        )
    st.html(f'<table class="answer-table"><thead><tr><th>Vessel</th><th class="num">{escape(label)}</th>'
            f'<th class="num">Slack</th><th>Note</th></tr></thead><tbody>{"".join(body)}</tbody></table>')
    with st.container(key=f"answer_{key}"):
        st.button("Open in Voyages", icon=":material/arrow_forward:", key=key, on_click=open_in_voyages, args=(lead,))
        st.caption(f'Voyage engine · {lead["cargo_id"]} at {lead["selected_lift_tonnes"]:,.0f} t · {lead["bunker_price_period"]} bunkers')


def pairing_evidence(output, key):
    """/compare for vessels across cargoes: one row per vessel and cargo pairing, best feasible first."""
    rows = output["rows"]
    lead = next((r for r in rows if r["feasible"]), None)
    body = "".join(
        f'<tr class="{"lead" if r is lead else ""}"><td><b>{escape(r["vessel_id"])}</b></td><td>{escape(r["cargo_id"])}<small>{r["selected_lift_tonnes"]:,.0f} t</small></td>'
        f'<td class="num {"neg" if r["tce_usd_per_day"] < 0 else ""}">${r["tce_usd_per_day"]:,.0f}</td>'
        f'<td class="num {"neg" if r["voyage_contribution_usd"] < 0 else ""}">${r["voyage_contribution_usd"]:,.0f}</td>'
        f'<td class="num">{r["laycan_slack_days"]:.1f} d</td>'
        f'<td>{"best" if r is lead else "feasible" if r["feasible"] else escape(", ".join(r["failed_checks"]))}</td></tr>'
        for r in rows)
    st.html(f'<table class="answer-table"><thead><tr><th>Vessel</th><th>Cargo</th><th class="num">TCE/day</th>'
            f'<th class="num">Contribution</th><th class="num">Slack</th><th>Note</th></tr></thead><tbody>{body}</tbody></table>')
    with st.container(key=f"answer_{key}"):
        if lead:
            st.button("Open in Voyages", icon=":material/arrow_forward:", key=key, on_click=open_in_voyages, args=(lead,))
        months = ", ".join(sorted({row["bunker_price_period"] for row in rows}))
        st.caption(f'Voyage engine · contract quantities unless a lift was given · {months} bunkers')


def render_evidence(evidence, key_prefix="analysis", compact=False):
    for idx, item in enumerate(evidence):
        output = item["result"]
        if item.get("tool") == "compare_cargoes" and output.get("rows"):
            pairing_evidence(output, f"{key_prefix}_{idx}_open")
            continue
        if "error" in output:
            st.warning(output["error"])
        if output.get("rows") and compact:
            compact_evidence(output, f"{key_prefix}_{idx}_open")
            continue
        if output.get("rows"):
            rows = output["rows"]
            ranking = output.get("ranking")
            facts = output.get("analysis") or analyst_facts(rows, ranking)
            focus = next(r for r in rows if r["vessel_id"] == facts["focus_vessel"])
            dark = st.session_state.get("dark_mode", True)
            colour, _ = profit_tone(facts["focus_margin_pct"], dark)
            label = "Highest contribution" if len(rows) > 1 and focus["feasible"] else "Voyage analysis"
            if ranking and ranking["winner"]:
                label = ranking["label"]
                note = ranking["status"]
                if ranking["runner_up"]:
                    note += f' · {ranking["unit"]} {ranking["difference"]:,.0f} ahead of {ranking["runner_up"]}'
                st.caption(note)
            if not facts["feasible_count"]:
                st.warning("No option passes the feasibility checks for this ranking. Figures below are hypothetical.")
            if not focus["fuel_pass"]:
                st.info("Replenishment plan required. " + shortage_message(focus))
            for warning in focus['warnings']:
                st.info(warning)
            margin = f'{facts["focus_margin_pct"]:.1f}%' if facts["focus_margin_pct"] is not None else "—"
            st.html(f'<div class="report-head"><b>{escape(label)} · {escape(focus["vessel_id"])} / {escape(focus["cargo_id"])}</b>'
                    f'<span>{focus["selected_lift_tonnes"]:,.0f} t · {escape(focus["bunker_price_period"])}</span></div>'
                    f'<div class="report-metrics"><div><small>Contribution</small><strong style="color:{colour}">${focus["voyage_contribution_usd"]:,.0f}</strong></div>'
                    f'<div><small>Profit margin</small><strong style="color:{colour}">{margin}</strong></div>'
                    f'<div><small>Feasible options</small><strong>{facts["feasible_count"]} / {facts["evaluated_count"]}</strong></div></div>')
            if ranking and ranking["objective"] == "stress_contribution":
                scenario = output["stress_scenario"]
                st.caption(f'Stress case · bunkers +{scenario["bunker_increase"]:.0%} · '
                           f'port charges +{scenario["port_cost_increase"]:.0%} · '
                           f'{scenario["idle_delay_days"]:g} extra idle days at loading')
            tabs = st.tabs(["Earnings", "Cost drivers", "Voyage time"])
            config = {"displaylogo": False, "displayModeBar": "hover", "scrollZoom": False}
            prefix = f"{key_prefix}_{idx}"
            with tabs[0]:
                if facts["feasible_count"]:
                    st.plotly_chart(earnings_chart(rows, dark).update_layout(hovermode=False), width="stretch", theme=None, key=prefix+"_earnings", config=config)
                    st.caption("Base-case contribution after hire. Voyage durations differ.")
                else:
                    st.info("Earnings ranking unavailable: all options fail feasibility checks.")
            with tabs[1]:
                st.plotly_chart(cost_chart(focus, dark).update_layout(hovermode=False), width="stretch", theme=None, key=prefix+"_costs", config=config)
                st.caption("Revenue less commission, bunkers, port charges and hire. Canal cost assumed zero.")
            with tabs[2]:
                st.plotly_chart(duration_chart(rows, dark).update_layout(hovermode=False), width="stretch", theme=None, key=prefix+"_duration", config=config)
                st.caption("All evaluated options; check feasibility before selecting a vessel.")
            with st.expander("Comparison table"):
                frame = result_frame(rows)
                frame["Status"] = ["Feasible" if r.get("ranking_eligible", r["feasible"]) else
                                   ", ".join(r["failed_checks"] or r.get("stress_failed_checks", [])) for r in rows]
                frame = frame.rename(columns={"vessel_id":"Vessel", "voyage_days":"Days", "tce_usd_per_day":"TCE / day", "voyage_contribution_usd":"Contribution", "profit_margin_pct":"Margin %"})
                columns = ["Vessel", "Status", "Days", "TCE / day", "Contribution", "Margin %"]
                if ranking:
                    frame = frame.rename(columns={"selected_lift_tonnes": "Lift (t)", "stress_contribution_usd": "Stressed contribution"})
                    columns = ["Vessel", "Lift (t)", *columns[1:], "Stressed contribution"]
                st.html('<div class="table-wrap">' + frame[columns].to_html(index=False, escape=True, float_format=lambda x:f"{x:,.2f}", classes="ocean-table", border=0) + '</div>')
        with st.expander("Calculation details"):
            st.json(output)
