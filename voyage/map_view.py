"""Detailed external basemap with display-only port locations; engine data unchanged."""
import json
from pathlib import Path
import streamlit as st


def render_map(case):
    locations = json.loads((Path(__file__).resolve().parents[1] / "data/map_locations.json").read_text())
    codes = [case["vessel"]["current_port"], case["cargo"]["load_port"], case["cargo"]["discharge_port"]]
    points = [{"name":case["ports"][code]["port_name"], "coordinates":[locations[code]["lon"],locations[code]["lat"]], "role":role} for code,role in zip(codes,["Current position","Load port","Discharge port"])]
    payload = json.dumps(points).replace("<", "\\u003c")
    style = "dark" if st.session_state.get("dark_mode", True) else "light"
    markup = (Path(__file__).with_name("route_map.html").read_text(encoding="utf-8")
              .replace("__POINTS__",payload).replace("__STYLE__",style)
              .replace("__BOUNDARIES__", (Path(__file__).resolve().parents[1] / "data/map_boundaries.geojson").read_text(encoding="utf-8")))
    st.iframe(markup, height=260, alt="Interactive map of selected voyage ports")
