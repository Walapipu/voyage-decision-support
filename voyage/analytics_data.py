"""Analytics dataset: every managed vessel against every committed cargo, from the voyage engine.

All numbers are engine rows (cached in voyage.plan), never estimates. A "lift basis" decides
which tonnage each pairing is evaluated at:
  best     the highest-contribution feasible lift in the contract range (the Overview plan's rule);
           a pairing with no feasible lift falls back to the contract quantity and stays infeasible
  nominal  the contract (nominal) quantity
  min/max  the contract minimum or maximum
"""
from functools import lru_cache

from voyage.data import load_tables
from voyage.plan import _row, best_voyage

BASES = {"best": "Best feasible lift", "nominal": "Contract quantity", "min": "Contract minimum", "max": "Contract maximum"}
QUANTITY = {"nominal": "nominal_quantity_tonnes", "min": "minimum_quantity_tonnes", "max": "maximum_quantity_tonnes"}


def vessel_ids():
    return [v["vessel_id"] for v in load_tables()["managed_vessels"]]


def cargo_ids():
    return [c["cargo_id"] for c in load_tables()["committed_cargoes"]]


def periods():
    return sorted({r["period"] for r in load_tables()["bunker_forward_curve"]})


def _cargo(cargo_id):
    return next(c for c in load_tables()["committed_cargoes"] if c["cargo_id"] == cargo_id)


def pairing(vessel_id, cargo_id, period, basis="best"):
    if basis == "best":
        row = best_voyage(vessel_id, cargo_id, period)
        if row:
            return row
        basis = "nominal"
    return _row(vessel_id, cargo_id, float(_cargo(cargo_id)[QUANTITY[basis]]), period)


@lru_cache(maxsize=64)
def _grid(period, basis):
    return tuple(pairing(v, c, period, basis) for v in vessel_ids() for c in cargo_ids())


def grid(period, basis="best", vessels=None, cargoes=None, feasible_only=False):
    """Pairing rows for one bunker month, filtered. Rows are shared cached dicts: do not mutate."""
    rows = [r for r in _grid(period, basis)
            if (not vessels or r["vessel_id"] in vessels) and (not cargoes or r["cargo_id"] in cargoes)]
    return [r for r in rows if r["feasible"]] if feasible_only else rows


def month_series(basis="best", vessels=None, cargoes=None):
    """{period: rows} across every supplied bunker month."""
    return {p: grid(p, basis, vessels, cargoes) for p in periods()}


@lru_cache(maxsize=128)
def lift_curve(vessel_id, cargo_id, period, steps=24):
    """Engine rows across the contract range, contract quantities included, for the lift-sensitivity chart."""
    cargo = _cargo(cargo_id)
    low, high = float(cargo["minimum_quantity_tonnes"]), float(cargo["maximum_quantity_tonnes"])
    lifts = {round(low + (high - low) * i / steps) for i in range(steps + 1)} | {float(cargo["nominal_quantity_tonnes"])}
    best = best_voyage(vessel_id, cargo_id, period)
    if best:
        lifts.add(best["selected_lift_tonnes"])
    return tuple(_row(vessel_id, cargo_id, float(lift), period) for lift in sorted(lifts))


def margin(row):
    return 100 * row["voyage_contribution_usd"] / row["freight_revenue_usd"] if row["freight_revenue_usd"] else None


def summary(rows):
    feasible = [r for r in rows if r["feasible"]]
    best = max(feasible, key=lambda r: r["voyage_contribution_usd"], default=None)
    tightest = min(feasible, key=lambda r: r["laycan_slack_days"], default=None)
    return {"count": len(rows), "feasible": len(feasible), "best": best, "tightest": tightest,
            "avg_tce": sum(r["tce_usd_per_day"] for r in feasible) / len(feasible) if feasible else None,
            "bunker_cost": sum(r["bunker_cost_usd"] for r in feasible) / len(feasible) if feasible else None}
