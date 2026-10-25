"""Compare individual voyages; this is not a fleet allocation optimiser."""

from decimal import Decimal

from voyage.data import load_tables
from voyage.engine import calculate

CONVENTIONS = {
    "speed": "economical",
    "bunker_pricing": "load-port pricing location, explicitly selected month (default March 2026)",
    "draft": "0.3 m margin below the minimum of summer, load-port and discharge-port limits",
    "canal_cost": "zero provisional: no canal inputs supplied",
    "tce": "net voyage cashflow before hire divided by total voyage days, including ballast",
    "contribution": "net voyage cashflow less hire for that voyage; different voyage horizons",
}


def present(result):
    row = {k: float(v) if isinstance(v, Decimal) else v for k, v in result.items()}
    row["failed_checks"] = [k.removesuffix("_pass") for k in ("quantity_pass", "laycan_pass", "deadweight_pass", "draft_pass") if not row[k]]
    row["feasible"] = not row["failed_checks"]
    return row


def evaluate_voyage(vessel_id, cargo_id, lift_tonnes, period="2026-03"):
    return {"rows": [present(calculate(vessel_id, cargo_id, lift_tonnes, period))], "conventions": CONVENTIONS}


def compare_vessels(cargo_id, lift_tonnes, period="2026-03"):
    rows = [present(calculate(v["vessel_id"], cargo_id, lift_tonnes, period)) for v in load_tables()["managed_vessels"]]
    rows.sort(key=lambda r: (not r["feasible"], -r["voyage_contribution_usd"]))
    return {"rows": rows, "conventions": CONVENTIONS,
            "scope": "Four managed vessels for one cargo at one specified lift. Feasible voyages first, then contribution. Not a fleet-wide best plan."}
