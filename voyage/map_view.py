"""Detailed external basemap with display-only port locations; engine data unchanged."""
import json
from pathlib import Path
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]


def locations():
    return json.loads((ROOT / "data/map_locations.json").read_text())


def _coordinates(code, where):
    return [where[code]["lon"], where[code]["lat"]]


def _draw(points, legs, legend=(), height=200, alt="Interactive map of selected voyage ports", show_tce=False):
    def payload(value):
        return json.dumps(list(value)).replace("<", "\\u003c")
    style = "dark" if st.session_state.get("dark_mode", True) else "light"
    markup = (Path(__file__).with_name("route_map.html").read_text(encoding="utf-8")
              .replace("__POINTS__", payload(points)).replace("__LEGS__", payload(legs))
              .replace("__LEGEND__", payload(legend)).replace("__STYLE__", style)
              .replace("__SHOW_TCE__", json.dumps(show_tce))
              .replace("__BOUNDARIES__", (ROOT / "data/map_boundaries.geojson").read_text(encoding="utf-8")))
    st.iframe(markup, height=height, alt=alt)


def render_home_map(case, catalog):
    """Show committed routes before selection and calculated candidate TCE afterwards."""
    where, ports = locations(), catalog["ports"]
    cargoes = [case["cargo"]] if case else catalog["tables"]["committed_cargoes"]
    points, legs = [], []
    seen = set()
    for cargo in cargoes:
        load, discharge = cargo["load_port"], cargo["discharge_port"]
        for code, kind in ((load, "load"), (discharge, "discharge")):
            if code not in seen:
                points.append({"name": ports[code]["port_name"], "coordinates": _coordinates(code, where), "kind": kind})
                seen.add(code)
        legs.append({"from": _coordinates(load, where), "to": _coordinates(discharge, where), "kind": "laden"})
    if case:
        vessels = {v["vessel_id"]: v for v in catalog["tables"]["managed_vessels"]}
        for row in case["comparison"]["rows"]:
            vessel_id = row["vessel_id"]
            code = vessels[vessel_id]["current_port"]
            origin = _coordinates(code, where)
            focused = vessel_id == case["row"]["vessel_id"]
            points.append({"name": f'{vessel_id} · {ports[code]["port_name"]}', "coordinates": origin,
                           "kind": "vessel", "focused": focused, "tce": row["tce_usd_per_day"], "feasible": row["feasible"]})
            legs.append({"from": origin, "to": _coordinates(case["cargo"]["load_port"], where),
                         "kind": "ballast" if focused else "other" if row["feasible"] else "late"})
    _draw(points, legs, height=184, alt="TCE heat map and committed voyage routes", show_tce=True)


def render_candidate_map(cargo, rows, focus_id, ports, vessels, height=320):
    """Every evaluated vessel's ballast leg into the load port, with the focused one emphasised.

    Connectors are schematic straight lines between approximate port locations;
    distances and days come from the engine, not from this drawing.
    """
    where = locations()
    load, discharge = cargo["load_port"], cargo["discharge_port"]
    points = [{"name": f'{ports[load]["port_name"]} · load port', "coordinates": _coordinates(load, where), "kind": "load", "permanent": True},
              {"name": f'{ports[discharge]["port_name"]} · discharge', "coordinates": _coordinates(discharge, where), "kind": "discharge", "permanent": True, "direction": "right"}]
    legs = [{"from": points[0]["coordinates"], "to": points[1]["coordinates"], "kind": "laden"}]
    for row in rows:
        vessel = vessels[row["vessel_id"]]
        focus = row["vessel_id"] == focus_id
        kind = "ballast" if focus else "other" if row["feasible"] else "late"
        origin = _coordinates(vessel["current_port"], where)
        speed = f'{vessel["economical_ballast_speed_knots"]} kn'
        points.append({"name": f'{row["vessel_id"]} · {speed}' if focus else f'{row["vessel_id"]} · {ports[vessel["current_port"]]["port_name"]} · {speed}',
                       "coordinates": origin, "kind": "vessel" if focus else kind, "permanent": focus, "direction": "left"})
        legs.append({"from": origin, "to": points[0]["coordinates"], "kind": kind})
    legend = [{"label": f"Ballast · {focus_id}", "kind": "ballast"}, {"label": "Laden leg", "kind": "laden"},
              {"label": "Other feasible", "kind": "other"}, {"label": "Infeasible", "kind": "late"}]
    present = {leg["kind"] for leg in legs}
    _draw(points, legs, [item for item in legend if item["kind"] in present], height,
          alt=f'Map of ballast legs for {len(rows)} vessels into {ports[load]["port_name"]}')
