"""Tables and charts rendered from Python results, never generated model code."""

import pandas as pd
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
            st.dataframe(frame, hide_index=True, width="stretch")
            feasible = frame[frame["Feasible"]]
            if len(feasible) > 1:
                left, right = st.columns(2)
                with left:
                    st.caption("TCE before hire (USD/day)")
                    st.bar_chart(feasible.set_index("Vessel")[["TCE (USD/day)"]])
                with right:
                    st.caption("Voyage contribution after hire (USD)")
                    st.bar_chart(feasible.set_index("Vessel")[["Contribution (USD)"]])
            st.caption("Charts include feasible voyages only. Different voyage durations apply.")
        with st.expander("Source results and assumptions"):
            st.json(output)
