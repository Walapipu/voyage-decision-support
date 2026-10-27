"""Analyst dashboards rendered inside assistant replies from engine evidence."""
from html import escape
import streamlit as st
from voyage.analysis import analyst_facts, profit_tone, result_frame
from voyage.charts import earnings_chart, cost_chart, duration_chart
from voyage.fuel import shortage_message


def render_evidence(evidence, key_prefix="analysis"):
    for idx, item in enumerate(evidence):
        output = item["result"]
        if "error" in output:
            st.warning(output["error"])
        if output.get("rows"):
            rows = output["rows"]
            facts = output.get("analysis") or analyst_facts(rows)
            focus = next(r for r in rows if r["vessel_id"] == facts["focus_vessel"])
            dark = st.session_state.get("dark_mode", True)
            colour, _ = profit_tone(facts["focus_margin_pct"], dark)
            label = "Highest contribution" if len(rows) > 1 and focus["feasible"] else "Voyage analysis"
            if not focus["feasible"]:
                st.warning("No feasible voyage in these results. Figures below are hypothetical.")
            if not focus["fuel_pass"]:
                st.info("Replenishment plan required. " + shortage_message(focus))
            margin = f'{facts["focus_margin_pct"]:.1f}%' if facts["focus_margin_pct"] is not None else "—"
            st.html(f'<div class="report-head"><b>{escape(label)} · {escape(focus["vessel_id"])} / {escape(focus["cargo_id"])}</b>'
                    f'<span>{focus["selected_lift_tonnes"]:,.0f} t · {escape(focus["bunker_price_period"])}</span></div>'
                    f'<div class="report-metrics"><div><small>Contribution</small><strong style="color:{colour}">${focus["voyage_contribution_usd"]:,.0f}</strong></div>'
                    f'<div><small>Profit margin</small><strong style="color:{colour}">{margin}</strong></div>'
                    f'<div><small>Feasible options</small><strong>{facts["feasible_count"]} / {facts["evaluated_count"]}</strong></div></div>')
            tabs = st.tabs(["Earnings", "Cost drivers", "Voyage time"])
            config = {"displaylogo": False, "displayModeBar": "hover", "scrollZoom": False}
            prefix = f"{key_prefix}_{idx}"
            with tabs[0]:
                if facts["feasible_count"]:
                    st.plotly_chart(earnings_chart(rows, dark), width="stretch", theme=None, key=prefix+"_earnings", config=config)
                    st.caption("Feasible options · contribution after hire · voyage durations differ")
                else:
                    st.info("Earnings ranking unavailable: all options fail feasibility checks.")
            with tabs[1]:
                st.plotly_chart(cost_chart(focus, dark), width="stretch", theme=None, key=prefix+"_costs", config=config)
                st.caption("Revenue less commission, bunkers, port charges and hire. Canal cost assumed zero.")
            with tabs[2]:
                st.plotly_chart(duration_chart(rows, dark), width="stretch", theme=None, key=prefix+"_duration", config=config)
                st.caption("All evaluated options; check feasibility before selecting a vessel.")
            with st.expander("Comparison table"):
                frame = result_frame(rows)
                frame["Status"] = ["Feasible" if r["feasible"] else ", ".join(r["failed_checks"]) for r in rows]
                frame = frame.rename(columns={"vessel_id":"Vessel", "voyage_days":"Days", "tce_usd_per_day":"TCE / day", "voyage_contribution_usd":"Contribution", "profit_margin_pct":"Margin %"})
                columns = ["Vessel", "Status", "Days", "TCE / day", "Contribution", "Margin %"]
                st.html('<div class="table-wrap">' + frame[columns].to_html(index=False, escape=True, float_format=lambda x:f"{x:,.2f}", classes="ocean-table", border=0) + '</div>')
        with st.expander("Calculation details"):
            st.json(output)
