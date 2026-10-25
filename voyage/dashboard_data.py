"""Presentation metrics derived from the existing engine, never from mock-up values."""
from datetime import datetime, timedelta

from voyage.data import index, load_tables
from voyage.decision import compare_vessels


def dashboard_case(cargo_id, lift, period, vessel_id):
    tables = load_tables()
    comparison = compare_vessels(cargo_id, lift, period)
    row = next(r for r in comparison["rows"] if r["vessel_id"] == vessel_id)
    vessel = index(tables["managed_vessels"], "vessel_id")[vessel_id]
    cargo = index(tables["committed_cargoes"], "cargo_id")[cargo_id]
    ports = index(tables["ports"], "port_code")
    start = datetime.fromisoformat(vessel["available_from_utc"].replace("Z", "+00:00"))
    stages = [("Available", 0, ports[vessel["current_port"]]["port_name"]),
              ("Load arrival", row["ballast_days"], ports[cargo["load_port"]]["port_name"]),
              ("Loading starts", row["ballast_days"] + row["laycan_wait_days"], "After laycan wait"),
              ("Load departure", row["ballast_days"] + row["laycan_wait_days"] + row["loading_days"], "Cargo aboard"),
              ("Discharge arrival", row["voyage_days"] - row["discharge_days"], ports[cargo["discharge_port"]]["port_name"]),
              ("Voyage ends", row["voyage_days"], "Discharge complete")]
    timeline = [{"label": label, "time": (start + timedelta(days=days)).isoformat(), "detail": detail} for label, days, detail in stages]
    total_cost = row["bunker_cost_usd"] + row["port_cost_usd"] + row["commission_usd"] + row["hire_cost_usd"]
    return {"row": row, "vessel": vessel, "cargo": cargo, "ports": ports, "tables": tables,
            "comparison": comparison, "timeline": timeline,
            "total_cost_usd": total_cost,
            "margin_pct": 100 * row["voyage_contribution_usd"] / row["freight_revenue_usd"] if row["freight_revenue_usd"] else None,
            "fuel_tonnes": row["vlsfo_consumption_tonnes"] + row["mgo_consumption_tonnes"],
            "feasible_count": sum(r["feasible"] for r in comparison["rows"]),
            "discharge_eta": timeline[-2]["time"]}
