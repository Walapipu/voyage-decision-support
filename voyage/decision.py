"""Compare individual voyages; this is not a fleet allocation optimiser."""

from dataclasses import asdict
from decimal import Decimal

from voyage import engine
from voyage.data import index
from voyage.market import all_cargoes
from voyage.engine import calculate, calculate_from_tables, VoyageScenario
from voyage.policy import load_policy, conventions

OBJECTIVES = {
    "contribution": ("voyage_contribution_usd", "Contribution after hire", "USD"),
    "tce": ("tce_usd_per_day", "TCE before hire", "USD/day"),
    "stress_contribution": ("stress_contribution_usd", "Stressed contribution", "USD"),
}
BASE = VoyageScenario()
DEFAULT_STRESS = VoyageScenario(bunker_increase="0.20", idle_delay_days=3, port_cost_increase="0.15")

def serializable(value):
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: serializable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serializable(v) for v in value]
    return value


def present(result):
    row = serializable(result)
    row["failed_checks"] = [k.removesuffix("_pass") for k in ("quantity_pass", "laycan_pass", "deadweight_pass", "draft_pass", "fuel_pass") if not row[k]]
    if row['port_draft_policy'] == 'exclude' and not row['port_draft_pass']:
        row['failed_checks'].append('port_draft')
    row['warnings'] = []
    if row['planning_purchase_assumed']:
        plan = row["bunker_plan"]
        stops = []
        for port, key, timing in (
            (plan["current_port"], "purchase_before_ballast_tonnes", "before ballast departure"),
            (plan["load_port"], "purchase_at_load_tonnes", "on arrival at loading"),
        ):
            purchases = ", ".join(f'{grade} {entry[key]:,.3f} t' for grade, entry in plan["by_grade"].items() if entry[key] > 0)
            if purchases:
                stops.append(f"{port} {timing} ({purchases})")
        if stops:
            row["warnings"].append("Fuel replenishment assumed covered at " + " and ".join(stops) + ".")
    for check in row['port_draft_checks']:
        if not check['passes']:
            row['warnings'].append(f"{check['port_role'].title()} port {check['port_code']}: departure-draft proxy fails the separate port check (headroom {check['headroom_m']:.3f} m). Policy: {row['port_draft_policy']}.")
    row["feasible"] = not row["failed_checks"]
    return row


def evaluate_voyage(vessel_id, cargo_id, lift_tonnes, period=None, policy=None):
    policy = policy or load_policy()
    return {"rows": [present(calculate(vessel_id, cargo_id, lift_tonnes, period, policy))], "conventions": conventions(policy)}


LIFT_RESOLUTION_T = 100  # convention: optimised lifts are rounded down to the nearest 100 t


def within_load_limits(row):
    """Deadweight and draft checks: the only checks that tighten as the lift grows."""
    return row["deadweight_pass"] and row["draft_pass"] and (
        row["port_draft_policy"] != "exclude" or row["port_draft_pass"])


def max_loadable_lift(fits, low, high, resolution=LIFT_RESOLUTION_T):
    """Largest lift in [low, high] that passes `fits`, rounded down to `resolution`, or None.

    Bisection is valid because deadweight and draft only tighten as the lift grows.
    Shared by the Overview plan and the ranking so both reach the same cargo size."""
    if not fits(low):
        return None
    if fits(high):
        return high
    good, bad = low, high
    while bad - good > resolution:
        mid = (good + bad) / 2
        good, bad = (mid, bad) if fits(mid) else (good, mid)
    return max(low, (good // resolution) * resolution)


def quantity_grid(cargo):
    low, nominal, high = (Decimal(cargo[f"{bound}_quantity_tonnes"])
                          for bound in ("minimum", "nominal", "maximum"))
    step = Decimal(1000)
    choices = {low, nominal, high} | {low + i * step for i in range(int((high - low) // step) + 1)}
    threshold = Decimal(cargo["special_freight_threshold_tonnes"] or 0)
    if low <= threshold <= high:
        choices.add(threshold)
    return sorted(choices)


def ranking_evidence(ranked, objective, objective_winners):
    metric, label, unit = OBJECTIVES[objective]
    if not ranked:
        return {"objective": objective, "label": label, "status": "No feasible recommendation",
                "draft_limited": False, "status_display": "No feasible recommendation",
                "winner": None, "runner_up": None, "difference": None, "unit": unit,
                "dominant_vs_runner_up": False}
    winner = ranked[0]
    runner = ranked[1] if len(ranked) > 1 else None
    metrics = ("voyage_contribution_usd", "tce_usd_per_day", "laycan_slack_days", "voyage_days")
    deltas = {k: winner[k] - runner[k] for k in metrics} if runner else {}
    dominance = [deltas[k] if k != "voyage_days" else -deltas[k] for k in deltas]
    dominant = bool(dominance) and min(dominance) >= -1e-7 and max(dominance) > 1e-7
    # The lift search fills each vessel to its draft limit, so nearly every winner
    # sits within 0.10 m of the minimum. Report that as a qualifier, not the status,
    # or it would hide the objective and dominance comparison on every cargo.
    minimum = winner["required_summer_draft_margin_m"]
    draft_limited = winner["limiting_draft_margin_m"] < minimum + 0.10
    if not winner["stress_feasible"] or winner["stress_contribution_usd"] < 0:
        status = "Scenario-sensitive"
    elif len(set(objective_winners.values())) > 1:
        status = "Objective-dependent"
    elif dominant:
        status = "Dominant"
    else:
        status = "Trade-off" if runner else "Sole feasible option"
    display = status + (f' · draft-limited lift ({winner["limiting_draft_margin_m"]:.3f} m limiting margin)'
                        if draft_limited else "")
    return {"objective": objective, "label": label, "status": status,
            "draft_limited": draft_limited, "status_display": display,
            "winner": winner["vessel_id"], "lift_tonnes": winner["selected_lift_tonnes"],
            "speed": winner["speed"], "runner_up": runner["vessel_id"] if runner else None,
            "difference": winner[metric] - runner[metric] if runner else None, "unit": unit,
            "runner_up_comparison": deltas, "dominant_vs_runner_up": dominant}


def compare_vessels(cargo_id, lift_tonnes=None, period=None, policy=None, *,
                    objective="contribution", speeds=("economical",), stress=None, vessel_ids=None,
                    include_market=False):
    """Rank each vessel's best eligible candidate, keeping exclusions visible.

    Managed vessels are always candidates. include_market adds the chartered-in market vessels,
    at their assumed hire, for a committed cargo (market vessels are not hired for market cargoes)."""
    if objective not in OBJECTIVES:
        raise ValueError("Choose contribution, tce or stress_contribution.")
    if not speeds:
        raise ValueError("Choose at least one voyage speed.")
    stress = stress if stress is not None else DEFAULT_STRESS
    policy = policy or load_policy()
    tables = engine.load_tables()
    cargo = all_cargoes().get(cargo_id)
    if cargo is None:
        raise ValueError("Choose a cargo CC-01 to CC-03 or MC-01 to MC-08.")
    grid = [lift_tonnes] if lift_tonnes is not None else quantity_grid(cargo)
    pool = tables["managed_vessels"] + tables["market_vessels"]
    if vessel_ids is None:
        hired = include_market and cargo_id in {c["cargo_id"] for c in tables["committed_cargoes"]}
        pool = tables["managed_vessels"] + (tables["market_vessels"] if hired else [])
    vessels = [v for v in pool if vessel_ids is None or v["vessel_id"] in vessel_ids]
    if not vessels:
        raise ValueError("Select at least one vessel.")
    candidates = []
    for vessel in vessels:
        for speed in speeds:
            lifts = grid
            if lift_tonnes is None:
                # Add this vessel's largest loadable lift, found to the same 100 t as the plan.
                # Without it the 1,000 t grid can stop up to ~1,000 t short of the limit.
                fits = lambda lift: within_load_limits(
                    calculate_from_tables(tables, vessel["vessel_id"], cargo_id, lift, period, policy, speed, BASE))
                top = max_loadable_lift(fits, grid[0], grid[-1])
                lifts = sorted(set(grid) | ({top} if top is not None else set()))
            for lift in lifts:
                args = (tables, vessel["vessel_id"], cargo_id, lift, period, policy, speed)
                base = present(calculate_from_tables(*args, BASE))
                stressed = present(calculate_from_tables(*args, stress))
                base.update(
                    stress_feasible=stressed["feasible"],
                    stress_failed_checks=stressed["failed_checks"],
                    stress_contribution_usd=stressed["voyage_contribution_usd"],
                    stress_tce_usd_per_day=stressed["tce_usd_per_day"],
                    stress_voyage_days=stressed["voyage_days"],
                    stress_laycan_slack_days=stressed["laycan_slack_days"],
                    stress_limiting_draft_margin_m=stressed["limiting_draft_margin_m"],
                    downside_loss_usd=base["voyage_contribution_usd"] - stressed["voyage_contribution_usd"],
                )
                candidates.append(base)

    baseline = [r for r in candidates if r["feasible"]]
    objective_winners = {}
    for key, (metric, _, _) in OBJECTIVES.items():
        eligible = [r for r in baseline if key != "stress_contribution" or r["stress_feasible"]]
        if eligible:
            winner = min(eligible, key=lambda r: (-r[metric], -r["voyage_contribution_usd"],
                         r["vessel_id"], r["selected_lift_tonnes"]))
            objective_winners[key] = winner["vessel_id"]

    metric = OBJECTIVES[objective][0]
    for row in candidates:
        row["ranking_eligible"] = row["feasible"] and (objective != "stress_contribution" or row["stress_feasible"])
    candidates.sort(key=lambda r: (not r["ranking_eligible"], not r["feasible"], -r[metric],
                                   -r["voyage_contribution_usd"], r["vessel_id"], r["selected_lift_tonnes"]))
    best = {}
    for row in candidates:
        best.setdefault(row["vessel_id"], row)
    rows = list(best.values())
    ranked = [row for row in rows if row["ranking_eligible"]]
    scope = ("One cargo at the requested lift." if lift_tonnes is not None else
             "One cargo with a 1,000 t search grid plus contractual endpoints, nominal lift and freight threshold.")
    return {
        "rows": rows, "conventions": dict(conventions(policy), speed=", ".join(dict.fromkeys(speeds))), "scope": scope,
        "ranking": ranking_evidence(ranked, objective, objective_winners),
        "objective_winners": objective_winners, "stress_scenario": serializable(asdict(stress)),
        "baseline_feasible_candidates": len(baseline), "evaluated_candidates": len(candidates),
        "excluded_combinations": [
            {"vessel_id": r["vessel_id"], "cargo_id": r["cargo_id"],
             "reasons": r["failed_checks"] or r["stress_failed_checks"]}
            for r in rows if not r["ranking_eligible"]
        ],
    }
