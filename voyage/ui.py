"""Tables and charts rendered from Python results, never generated model code."""

import pandas as pd
import altair as alt
import streamlit as st


def render_evidence(evidence):
    for item in evidence:
        output = item["result"]
        if "error" in output:
            st.warning(output["error"])
        if output.get("rows"):
            rows = output["rows"]
            st.caption("Calculated by Python · " + item["tool"])
            frame = pd.DataFrame([{
                "Vessel": r["vessel_id"], "Cargo": r["cargo_id"],
                "Lift (t)": r["selected_lift_tonnes"], "Feasible": r["feasible"],
                "Failed checks": ", ".join(r["failed_checks"]) or "None",
                "Voyage days": round(r["voyage_days"], 2),
                "TCE (USD/day)": round(r["tce_usd_per_day"], 2),
                "Contribution (USD)": round(r["voyage_contribution_usd"], 2),
            } for r in rows])
            st.html('<div class="table-wrap">' + frame.to_html(index=False, escape=True, classes="ocean-table", border=0) + '</div>')
            feasible = frame[frame["Feasible"]]
            if len(feasible) > 1:
                left, right = st.columns(2)
                with left:
                    st.caption("TCE before hire (USD/day)")
                    comparison_chart(feasible, "TCE (USD/day)")
                with right:
                    st.caption("Voyage contribution after hire (USD)")
                    comparison_chart(feasible, "Contribution (USD)")
            st.caption("Charts include feasible voyages only. Different voyage durations apply.")
        with st.expander("Source results and assumptions"):
            st.json(output)


def comparison_chart(frame, metric):
    dark = st.session_state.get("dark_mode", True)
    chart = alt.Chart(frame).mark_bar(color="#12a9ec", cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("Vessel:N", title=None), y=alt.Y(metric + ":Q", title=metric),
        tooltip=["Vessel:N", alt.Tooltip(metric + ":Q", format=",.2f")]
    ).properties(height=210, background="#122337" if dark else "#ffffff").configure_axis(
        labelColor="#b8cbe0" if dark else "#52647a", titleColor="#b8cbe0" if dark else "#52647a",
        gridColor="#2a4056" if dark else "#e0e7ef", domain=False
    ).configure_view(strokeWidth=0)
    st.altair_chart(chart, theme=None, width="stretch")
