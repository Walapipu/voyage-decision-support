"""Recommended fleet plan: one committed cargo per owned vessel, built from the voyage engine.

Scope is what the data can price. Owned vessels (MF) carry supplied hire, committed cargoes
(CC) carry supplied freight. Chartered (MV) hire offers and market (MC) freight quotes are
not supplied, so they are not placed in the plan. Each vessel takes at most one voyage.
"""
from datetime import datetime, timedelta
from functools import lru_cache
from itertools import permutations

from voyage.data import index, load_tables
from voyage.decision import present
from voyage.engine import calculate
from voyage.policy import load_policy

TIGHT_SLACK_DAYS = 3.0      # laycan slack below this is flagged amber
DRAFT_AT_LIMIT_M = 0.05     # summer-draft headroom within this of the required margin
STAGES = ("ballast", "wait", "load", "laden", "discharge")


def _utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@lru_cache(maxsize=4096)
def _row(vessel_id, cargo_id, lift, period):
    return present(calculate(vessel_id, cargo_id, lift, period, load_policy()))


@lru_cache(maxsize=256)
def best_voyage(vessel_id, cargo_id, period):
    """Highest-contribution feasible lift inside the contract range, or None.

    Deadweight and draft only tighten as the lift grows, so the largest lift that
    passes them is found by bisection; the contract min, nominal, max and any freight
    threshold are tried as well and the best feasible row wins."""
    cargo = index(load_tables()["committed_cargoes"], "cargo_id")[cargo_id]
    low, high = float(cargo["minimum_quantity_tonnes"]), float(cargo["maximum_quantity_tonnes"])
    def fits(lift):
        row = _row(vessel_id, cargo_id, lift, period)
        return row["deadweight_pass"] and row["draft_pass"] and (
            row["port_draft_policy"] != "exclude" or row["port_draft_pass"]
        )

    lifts = {low, float(cargo["nominal_quantity_tonnes"]), high}
    threshold = float(cargo["special_freight_threshold_tonnes"] or 0)
    if low < threshold < high:
        lifts.add(threshold)
    if fits(low) and not fits(high):
        good, bad = low, high
        while bad - good > 100:
            mid = (good + bad) / 2
            good, bad = (mid, bad) if fits(mid) else (good, mid)
        lifts.add(float(int(good // 100) * 100))
    rows = [_row(vessel_id, cargo_id, lift, period) for lift in sorted(lifts) if low <= lift <= high]
    feasible = [r for r in rows if r["feasible"]]
    return max(feasible, key=lambda r: r["voyage_contribution_usd"]) if feasible else None


def _flags(row):
    excess = row["draft_margin_m"] - row["required_summer_draft_margin_m"]
    if row["port_draft_policy"] == "exclude":
        excess = min(excess, *(port["headroom_m"] - port["required_margin_m"] for port in row["port_draft_checks"]))
    draft_limited = excess < DRAFT_AT_LIMIT_M
    tight = row["laycan_slack_days"] < TIGHT_SLACK_DAYS
    return draft_limited, tight


def _voyage(row, vessel, cargo, ports):
    start = _utc(vessel["available_from_utc"])
    days = dict(zip(STAGES, (row["ballast_days"], row["laycan_wait_days"], row["loading_days"],
                             row["laden_days"], row["discharge_days"])))
    draft_limited, tight = _flags(row)
    load, discharge = ports[cargo["load_port"]], ports[cargo["discharge_port"]]
    return {"vessel_id": vessel["vessel_id"], "cargo_id": cargo["cargo_id"], "owned": True,
            "load_port": cargo["load_port"], "discharge_port": cargo["discharge_port"],
            "origin_port": vessel["current_port"],
            "route": f'{load["port_name"]} → {discharge["port_name"]}',
            "lift": row["selected_lift_tonnes"], "tce": row["tce_usd_per_day"],
            "contribution": row["voyage_contribution_usd"], "bunker_cost": row["bunker_cost_usd"],
            "slack": row["laycan_slack_days"], "draft_limited": draft_limited, "tight": tight,
            "start": start, "days": days, "end": start + timedelta(days=row["voyage_days"]),
            "laycan": (_utc(cargo["laycan_start_utc"]), _utc(cargo["laycan_end_utc"])),
            "row": row}


@lru_cache(maxsize=16)
def build_plan(period=None):
    tables = load_tables()
    vessels = tables["managed_vessels"]
    cargoes = tables["committed_cargoes"]
    ports = index(tables["ports"], "port_code")
    options = {(v["vessel_id"], c["cargo_id"]): best_voyage(v["vessel_id"], c["cargo_id"], period)
               for v in vessels for c in cargoes}
    # Exhaustive: each cargo gets a distinct vessel or stays uncovered. Coverage first, then contribution.
    best_key, best = (-1, 0.0), {}
    slots = [v["vessel_id"] for v in vessels] + [None] * len(cargoes)
    for pick in set(permutations(slots, len(cargoes))):
        chosen = {c["cargo_id"]: options.get((vid, c["cargo_id"])) if vid else None for vid, c in zip(pick, cargoes)}
        if any(vid and chosen[c["cargo_id"]] is None for vid, c in zip(pick, cargoes)):
            continue
        rows = [r for r in chosen.values() if r]
        key = (len(rows), sum(r["voyage_contribution_usd"] for r in rows))
        if key > best_key:
            best_key, best = key, chosen
    by_vessel, by_cargo = index(vessels, "vessel_id"), index(cargoes, "cargo_id")
    voyages = sorted((_voyage(r, by_vessel[r["vessel_id"]], by_cargo[cid], ports) for cid, r in best.items() if r),
                     key=lambda v: v["start"] + timedelta(days=v["days"]["ballast"] + v["days"]["wait"]))
    planned = {v["vessel_id"]: v for v in voyages}
    availability = sorted(
        ({"vessel_id": vid, "free": planned[vid]["end"], "port": ports[planned[vid]["discharge_port"]]["port_name"],
          "after": planned[vid]["cargo_id"]} if vid in planned else
         {"vessel_id": vid, "free": _utc(v["available_from_utc"]), "port": ports[v["current_port"]]["port_name"], "after": None}
         for vid, v in by_vessel.items()), key=lambda a: a["free"])
    fivetc = {r["period"]: float(r["reference_value"]) for r in tables["ffa_reference"] if r["route_code"] == "5TC_USD_PER_DAY"}
    tightest = min(voyages, key=lambda v: v["slack"], default=None)
    return {"period": period, "voyages": voyages, "availability": availability,
            "uncovered": [c["cargo_id"] for c in cargoes if best.get(c["cargo_id"]) is None],
            "committed": len(cargoes),
            "contribution": sum(v["contribution"] for v in voyages),
            "avg_tce": sum(v["tce"] for v in voyages) / len(voyages) if voyages else None,
            "bunker_cost": sum(v["bunker_cost"] for v in voyages),
            "tightest": tightest, "fivetc": fivetc.get(period),
            "chartered": [],  # no hire offers supplied, so nothing is chartered in
            "computed": datetime.now().astimezone()}


def plan_voyage(plan, vessel_id):
    return next((v for v in plan["voyages"] if v["vessel_id"] == vessel_id), None)


def plan_summary(plan):
    """One line per voyage for the assistant's context. Engine figures only."""
    lines = [f'{v["vessel_id"]} → {v["cargo_id"]} {v["route"]}, lift {v["lift"]:,.0f} t, TCE ${v["tce"]:,.0f}/day, '
             f'contribution ${v["contribution"]:,.0f}, laycan slack {v["slack"]:.1f} d'
             + (", draft at limit" if v["draft_limited"] else "") for v in plan["voyages"]]
    idle = [a["vessel_id"] for a in plan["availability"] if a["after"] is None]
    return ("; ".join(lines) + (f'. Unassigned owned vessels: {", ".join(idle)}' if idle else "")
            + (f'. Uncovered cargoes: {", ".join(plan["uncovered"])}' if plan["uncovered"] else ""))
