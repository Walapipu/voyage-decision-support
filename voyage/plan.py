"""Recommended fleet plan, built from the voyage engine.

Each owned vessel (MF) takes at most one voyage: a committed cargo (CC) or a market cargo (MC).
Every committed cargo must be covered, by an owned vessel or a chartered-in market vessel (MV).
Market vessels are hired only to cover committed cargoes, never to trade market cargoes.
Market hire and market freight are the stated assumptions in voyage.market.

The search is exhaustive: coverage first, then total contribution. An owned vessel left idle
contributes zero; the comparison does not put voyages of different lengths on a common horizon.
"""
from datetime import datetime, timedelta
from functools import lru_cache
from itertools import permutations, product

from voyage.data import index, load_tables
from voyage.decision import max_loadable_lift, present, within_load_limits
from voyage.engine import calculate
from voyage.market import all_cargoes, all_vessels
from voyage.policy import load_policy

TIGHT_SLACK_DAYS = 3.0      # laycan slack below this is flagged amber
DRAFT_AT_LIMIT_M = 0.05     # summer-draft headroom within this of the required margin
STAGES = ("ballast", "wait", "load", "laden", "discharge")


def _utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


_cargoes, _vessels = all_cargoes, all_vessels


@lru_cache(maxsize=8192)
def _row(vessel_id, cargo_id, lift, period):
    return present(calculate(vessel_id, cargo_id, lift, period, load_policy()))


@lru_cache(maxsize=1024)
def best_voyage(vessel_id, cargo_id, period):
    """Highest-contribution feasible lift inside the contract range, or None.

    Deadweight and draft only tighten as the lift grows, so the largest lift that
    passes them is found by bisection; the contract min, nominal, max and any freight
    threshold are tried as well and the best feasible row wins."""
    cargo = _cargoes()[cargo_id]
    low, high = float(cargo["minimum_quantity_tonnes"]), float(cargo["maximum_quantity_tonnes"])
    lifts = {low, float(cargo["nominal_quantity_tonnes"]), high}
    threshold = float(cargo["special_freight_threshold_tonnes"] or 0)
    if low < threshold < high:
        lifts.add(threshold)
    top = max_loadable_lift(lambda lift: within_load_limits(_row(vessel_id, cargo_id, lift, period)), low, high)
    if top is not None:
        lifts.add(float(top))
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
    return {"vessel_id": vessel["vessel_id"], "cargo_id": cargo["cargo_id"],
            "owned": vessel["vessel_id"].startswith("MF"), "market_cargo": cargo["cargo_id"].startswith("MC"),
            "load_port": cargo["load_port"], "discharge_port": cargo["discharge_port"],
            "origin_port": vessel["current_port"],
            "route": f'{load["port_name"]} → {discharge["port_name"]}',
            "lift": row["selected_lift_tonnes"], "tce": row["tce_usd_per_day"],
            "contribution": row["voyage_contribution_usd"], "bunker_cost": row["bunker_cost_usd"],
            "hire": float(vessel["hire_rate_usd_per_day"]),
            "freight_rate": float(cargo["contract_freight_rate_usd_per_tonne"]),
            "slack": row["laycan_slack_days"], "draft_limited": draft_limited, "tight": tight,
            "start": start, "days": days, "end": start + timedelta(days=row["voyage_days"]),
            "laycan": (_utc(cargo["laycan_start_utc"]), _utc(cargo["laycan_end_utc"])),
            "row": row}


@lru_cache(maxsize=16)
def _options(period):
    """Best feasible voyage for every pairing the plan may use, keyed (vessel, cargo)."""
    tables = load_tables()
    owned = tuple(v["vessel_id"] for v in tables["managed_vessels"])
    hired = tuple(v["vessel_id"] for v in tables["market_vessels"])
    committed = tuple(c["cargo_id"] for c in tables["committed_cargoes"])
    market = tuple(c["cargo_id"] for c in tables["market_cargoes"])
    pairs = [(v, c) for v in owned for c in committed + market] + [(v, c) for v in hired for c in committed]
    rows = {pair: best_voyage(*pair, period) for pair in pairs}
    return {pair: row for pair, row in rows.items() if row is not None}, owned, hired, committed


def _contribution(row):
    return float(row["voyage_contribution_usd"])


@lru_cache(maxsize=4096)
def optimise(period, exclude=frozenset(), force=None):
    """Best assignment {vessel_id: cargo_id} with its score (committed covered, total contribution).

    exclude: pairings that may not be used. force: one (vessel, cargo) pairing that must be used.
    Returns None when no assignment includes the forced pairing."""
    options, owned, hired, committed = _options(period)
    usable = {pair: row for pair, row in options.items() if pair not in exclude}
    if force and force not in usable:
        return None
    value = {pair: _contribution(row) for pair, row in usable.items()}

    charters = {}

    def charter(left):
        """Best distinct market vessels for the committed cargoes the owned fleet leaves over."""
        if left not in charters:
            best = ((0, 0.0), {})
            for pick in permutations(hired + (None,) * len(left), len(left)):
                chosen = {v: c for v, c in zip(pick, left) if v}
                if any(pair not in value for pair in chosen.items()):
                    continue
                if force and force[0] in hired and chosen.get(force[0]) != force[1]:
                    continue
                score = (len(chosen), sum(value[pair] for pair in chosen.items()))
                if score > best[0]:
                    best = (score, chosen)
            charters[left] = best
        return charters[left]

    choices = [[None] + sorted(c for (v, c) in usable if v == vid) for vid in owned]
    best = None
    for pick in product(*choices):
        taken = [c for c in pick if c]
        if len(taken) != len(set(taken)):
            continue
        own = {v: c for v, c in zip(owned, pick) if c}
        if force and force[0] in owned and own.get(force[0]) != force[1]:
            continue
        (covered, extra), hire = charter(tuple(c for c in committed if c not in taken))
        if force and force[0] in hired and hire.get(force[0]) != force[1]:
            continue
        score = (sum(c in committed for c in taken) + covered, sum(value[pair] for pair in own.items()) + extra)
        if best is None or score > best[0]:
            best = (score, {**own, **hire})
    return best


@lru_cache(maxsize=16)
def build_plan(period=None):
    tables = load_tables()
    ports = index(tables["ports"], "port_code")
    options = _options(period)[0]
    _, assignment = optimise(period)
    vessels, cargoes = _vessels(), _cargoes()
    voyages = sorted((_voyage(options[v, c], vessels[v], cargoes[c], ports) for v, c in assignment.items()),
                     key=lambda v: v["start"] + timedelta(days=v["days"]["ballast"] + v["days"]["wait"]))
    planned = {v["vessel_id"]: v for v in voyages}
    availability = sorted(
        ({"vessel_id": vid, "free": planned[vid]["end"], "port": ports[planned[vid]["discharge_port"]]["port_name"],
          "after": planned[vid]["cargo_id"]} if vid in planned else
         {"vessel_id": vid, "free": _utc(v["available_from_utc"]), "port": ports[v["current_port"]]["port_name"], "after": None}
         for vid, v in index(tables["managed_vessels"], "vessel_id").items()), key=lambda a: a["free"])
    chartered = [{"vessel_id": v["vessel_id"], "redelivery": v["end"], "port": ports[v["discharge_port"]]["port_name"],
                  "after": v["cargo_id"], "hire": v["hire"]} for v in voyages if not v["owned"]]
    fivetc = {r["period"]: float(r["reference_value"]) for r in tables["ffa_reference"] if r["route_code"] == "5TC_USD_PER_DAY"}
    tightest = min(voyages, key=lambda v: v["slack"], default=None)
    committed = [c["cargo_id"] for c in tables["committed_cargoes"]]
    return {"period": period, "voyages": voyages, "availability": availability,
            "uncovered": [c for c in committed if c not in assignment.values()],
            "committed": len(committed),
            "contribution": sum(v["contribution"] for v in voyages),
            "avg_tce": sum(v["tce"] for v in voyages) / len(voyages) if voyages else None,
            "bunker_cost": sum(v["bunker_cost"] for v in voyages),
            "tightest": tightest, "fivetc": fivetc.get(period), "chartered": chartered,
            "computed": datetime.now().astimezone()}


def _changes(base, other):
    """How another assignment differs from the plan, one entry per vessel that moves."""
    return [{"vessel_id": v, "from": base.get(v), "to": other.get(v)}
            for v in sorted(set(base) | set(other)) if base.get(v) != other.get(v)]


def why_not(vessel_id, cargo_id, period):
    """Checks a pairing fails, tried at the contract minimum lift."""
    cargo = _cargoes()[cargo_id]
    row = _row(vessel_id, cargo_id, float(cargo["minimum_quantity_tonnes"]), period)
    return list(row["failed_checks"]) or ["no feasible lift"]


@lru_cache(maxsize=512)
def what_if(period, vessel_id, cargo_id):
    """The best plan that includes this pairing, against the recommended plan."""
    base = optimise(period)
    if (vessel_id, cargo_id) not in _options(period)[0]:
        return {"feasible": False, "reasons": why_not(vessel_id, cargo_id, period)}
    forced = optimise(period, force=(vessel_id, cargo_id))
    if forced is None:
        return {"feasible": False, "reasons": ["no plan covers every committed cargo with it"]}
    return {"feasible": True, "delta": forced[0][1] - base[0][1],
            "covers_all": forced[0][0] == base[0][0], "changes": _changes(base[1], forced[1])}


@lru_cache(maxsize=16)
def alternatives(period=None):
    """What each planned pairing is worth (the best plan without it) and owned-vessel swaps."""
    options, owned, _, _ = _options(period)
    (covered, total), assignment = optimise(period)
    worth = []
    for vessel, cargo in assignment.items():
        other = optimise(period, exclude=frozenset({(vessel, cargo)}))
        same_cover = other is not None and other[0][0] == covered
        worth.append({"vessel_id": vessel, "cargo_id": cargo,
                      "given_up": total - other[0][1] if same_cover else None,
                      "changes": _changes(assignment, other[1]) if same_cover else []})
    swaps = []
    mine = [v for v in owned if v in assignment]
    for i, a in enumerate(mine):
        for b in mine[i + 1:]:
            ca, cb = assignment[a], assignment[b]
            bad = [(v, c) for v, c in ((a, cb), (b, ca)) if (v, c) not in options]
            entry = {"pair": (a, b), "cargoes": (ca, cb), "feasible": not bad}
            if bad:
                entry["reasons"] = {f"{v} → {c}": why_not(v, c, period) for v, c in bad}
            else:
                entry["delta"] = (_contribution(options[a, cb]) + _contribution(options[b, ca])
                                  - _contribution(options[a, ca]) - _contribution(options[b, cb]))
            swaps.append(entry)
    return {"worth": sorted(worth, key=lambda w: -(w["given_up"] or 0)), "swaps": swaps,
            "idle": [v for v in owned if v not in assignment]}


def plan_voyage(plan, vessel_id):
    return next((v for v in plan["voyages"] if v["vessel_id"] == vessel_id), None)


def plan_summary(plan):
    """One line per voyage for the assistant's context. Engine figures only."""
    lines = [f'{v["vessel_id"]} → {v["cargo_id"]} {v["route"]}, lift {v["lift"]:,.0f} t, TCE ${v["tce"]:,.0f}/day, '
             f'contribution ${v["contribution"]:,.0f}, laycan slack {v["slack"]:.1f} days'
             + ("" if v["owned"] else ", chartered-in market vessel")
             + (", market cargo at assumed freight" if v["market_cargo"] else "")
             + (", draft at limit" if v["draft_limited"] else "") for v in plan["voyages"]]
    idle = [a["vessel_id"] for a in plan["availability"] if a["after"] is None]
    return ("; ".join(lines) + (f'. Unassigned owned vessels: {", ".join(idle)}' if idle else "")
            + (f'. Uncovered cargoes: {", ".join(plan["uncovered"])}' if plan["uncovered"] else ""))
