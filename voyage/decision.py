"""Compare individual voyages; this is not a fleet allocation optimiser."""

from decimal import Decimal

from voyage.data import load_tables
from voyage.engine import calculate
from voyage.policy import load_policy, conventions

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
        row['warnings'].append('Fuel replenishment assumed covered by planning purchase; no added bunkering days or cost. Delivery timing and locations remain unresolved.')
    for check in row['port_draft_checks']:
        if not check['passes']:
            row['warnings'].append(f"{check['port_role'].title()} port {check['port_code']}: departure-draft proxy fails the separate port check (headroom {check['headroom_m']:.3f} m). Policy: {row['port_draft_policy']}.")
    row["feasible"] = not row["failed_checks"]
    return row


def evaluate_voyage(vessel_id, cargo_id, lift_tonnes, period="2026-03", policy=None):
    policy = policy or load_policy()
    return {"rows": [present(calculate(vessel_id, cargo_id, lift_tonnes, period, policy))], "conventions": conventions(policy)}


def compare_vessels(cargo_id, lift_tonnes, period="2026-03", policy=None):
    policy = policy or load_policy()
    rows = [present(calculate(v["vessel_id"], cargo_id, lift_tonnes, period, policy)) for v in load_tables()["managed_vessels"]]
    rows.sort(key=lambda r: (not r["feasible"], -r["voyage_contribution_usd"]))
    return {"rows": rows, "conventions": conventions(policy),
            "excluded_combinations": [{"vessel_id": r['vessel_id'], "cargo_id": r['cargo_id'], "reasons": r['failed_checks']} for r in rows if not r['feasible']],
            "scope": "Four managed vessels for one cargo at one specified lift. Feasible voyages first, then contribution. Not a fleet-wide best plan."}
