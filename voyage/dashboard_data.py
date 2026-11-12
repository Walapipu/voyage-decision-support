"""Presentation metrics derived from the existing engine, never from mock-up values."""
from datetime import datetime, timedelta
from functools import lru_cache

from voyage.data import index, load_tables
from voyage.decision import OBJECTIVES, compare_vessels
from voyage.market import all_cargoes, all_vessels


def dashboard_case(cargo_id, lift, period, vessel_id, *, objective="contribution"):
    tables = load_tables()
    comparison = compare_vessels(cargo_id, lift, period, objective=objective, include_market=True)
    row = next((r for r in comparison["rows"] if r["vessel_id"] == vessel_id), comparison["rows"][0])
    vessel_id = row["vessel_id"]
    vessel = all_vessels()[vessel_id]
    cargo = all_cargoes()[cargo_id]
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


def bunker_price_scenarios(case):
    """Hold the voyage constant and apply each supplied month at its pricing location."""
    row, cargo = case["row"], case["cargo"]
    location = case["ports"][cargo["load_port"]]["bunker_pricing_location"]
    prices = {}
    for quote in case["tables"]["bunker_forward_curve"]:
        if quote["pricing_location"] == location:
            prices.setdefault(quote["period"], {})[quote["fuel_grade"]] = float(quote["price_usd_per_tonne"])
    revenue = row["freight_revenue_usd"]
    values = []
    for month, grades in sorted(prices.items()):
        if not {"VLSFO", "MGO"}.issubset(grades):
            continue
        cost = row["vlsfo_consumption_tonnes"] * grades["VLSFO"] + row["mgo_consumption_tonnes"] * grades["MGO"]
        contribution = row["voyage_contribution_usd"] + row["bunker_cost_usd"] - cost
        values.append((month, cost, 100 * contribution / revenue if revenue else None))
    return values


# Nearest Baltic Capesize route for each committed cargo, shown as market context only.
BALTIC_ROUTES = {"CC-02": ("C5", "West Australia → Qingdao"), "CC-03": ("C3", "Tubarão → Qingdao")}


def _reference_period(period, available):
    """A month's own FFA row if supplied, else its quarter (2026-05 → 2026-Q2)."""
    if period in available:
        return period
    year, month = period.split("-")
    quarter = f"{year}-Q{(int(month) - 1) // 3 + 1}"
    return quarter if quarter in available else None


@lru_cache(maxsize=128)
def suggested_lift(cargo_id, period, objective="contribution"):
    """The lift the ranking recommends: the top-ranked vessel's best lift within the cargo tolerance.

    Falls back to the best feasible lift, then the nominal lift, when nothing ranks."""
    rows = compare_vessels(cargo_id, None, period, objective=objective, include_market=True)["rows"]
    winner = next((r for r in rows if r["ranking_eligible"]), None) or next((r for r in rows if r["feasible"]), None)
    return float(winner["selected_lift_tonnes"]) if winner else float(all_cargoes()[cargo_id]["nominal_quantity_tonnes"])


def candidates_case(cargo_id, lift, period, objective="contribution", per_vessel=False):
    """Every vessel that may carry one cargo, ranked by the chosen objective, plus display context.

    per_vessel evaluates each vessel at its own best lift within the cargo tolerance (used while the lift
    box still holds the suggestion); otherwise every vessel is evaluated at the given lift.
    Managed vessels always; chartered-in market vessels too when the cargo is committed."""
    tables = load_tables()
    suggestion = suggested_lift(cargo_id, period, objective)
    if per_vessel:
        lift = suggestion
    comparison = compare_vessels(cargo_id, None if per_vessel else lift, period, objective=objective, include_market=True)
    rows = comparison["rows"]
    metric, label, unit = OBJECTIVES[objective]
    period = rows[0]["bunker_price_period"]
    cargo = all_cargoes()[cargo_id]
    ports = index(tables["ports"], "port_code")
    location = ports[cargo["load_port"]]["bunker_pricing_location"]
    prices = {r["fuel_grade"]: float(r["price_usd_per_tonne"]) for r in tables["bunker_forward_curve"]
              if r["period"] == period and r["pricing_location"] == location}
    feasible = [r for r in rows if r["feasible"]]
    ranked = [r for r in rows if r["ranking_eligible"]]
    lead = None
    if len(ranked) > 1:
        gap = ranked[0][metric] - ranked[1][metric]
        lead = {"vessel_id": ranked[1]["vessel_id"], "usd": gap,
                "pct": 100 * gap / ranked[1][metric] if ranked[1][metric] > 0 else None}
    baltic = None
    if cargo_id in BALTIC_ROUTES:
        route, name = BALTIC_ROUTES[cargo_id]
        ffa = {r["period"]: r for r in tables["ffa_reference"] if r["route_code"] == f"{route}_USD_PER_TONNE"}
        ref = _reference_period(period, ffa)
        if ref:
            baltic = {"route": route, "name": name, "period": ref, "usd_per_tonne": float(ffa[ref]["reference_value"])}
    return {"rows": rows, "cargo": cargo, "ports": ports, "conventions": comparison["conventions"],
            "vessels": all_vessels(),
            "best": ranked[0] if ranked else None, "feasible_count": len(feasible), "ranked_count": len(ranked),
            "objective": {"key": objective, "metric": metric, "label": label, "unit": unit},
            "lead": lead, "baltic": baltic, "bunker_prices": prices, "pricing_location": location,
            "period": period, "lift": float(lift), "suggested_lift": suggestion, "per_vessel": per_vessel}
