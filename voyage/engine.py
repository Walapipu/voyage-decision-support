"""Deterministic Decimal voyage calculation, adapted from the reconciled CSV check."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal as D, InvalidOperation, getcontext
from voyage.data import load_tables, index
from voyage.fuel import audit_fuel, plan_fuel
from voyage.policy import load_policy

getcontext().prec = 32

def num(row, key): return D(row[key])
def date(value): return datetime.fromisoformat(value.replace("Z", "+00:00"))

@dataclass(frozen=True)
class VoyageScenario:
    bunker_increase: D = D(0)
    idle_delay_days: D = D(0)
    working_delay_days: D = D(0)
    port_cost_increase: D = D(0)
    additional_ballast_nm: D = D(0)

    def __post_init__(self):
        for key, raw in vars(self).items():
            try:
                value = D(str(raw))
            except InvalidOperation:
                raise ValueError(f"{key} must be finite and nonnegative") from None
            if not value.is_finite() or value < 0:
                raise ValueError(f"{key} must be finite and nonnegative")
            object.__setattr__(self, key, value)


def calculate(vessel_id, cargo_id, lift, period=None, policy=None, *,
              speed="economical", scenario=None):
    return calculate_from_tables(load_tables(), vessel_id, cargo_id, lift, period,
                                 policy or load_policy(), speed, scenario or VoyageScenario())


def calculate_from_tables(tables, vessel_id, cargo_id, lift, period, policy, speed, scenario):
    if speed not in ("economical", "warranted"):
        raise ValueError("Choose economical or warranted speed.")
    assumptions = tables["commercial_assumptions"][0]
    vessels = index(tables["managed_vessels"], "vessel_id")
    cargoes = index(tables["committed_cargoes"], "cargo_id")
    if vessel_id not in vessels or cargo_id not in cargoes:
        raise ValueError("Choose MF-01 to MF-04 and CC-01 to CC-03. Market economics need user-supplied quotes and are not enabled yet.")
    try:
        lift = D(str(lift))
    except (InvalidOperation, ValueError):
        raise ValueError("Lift must be a finite positive number of tonnes.") from None
    if not lift.is_finite() or lift <= 0 or lift > D("1000000"):
        raise ValueError("Lift must be a finite positive number of tonnes, at most 1,000,000.")
    ports = index(tables["ports"], "port_code")
    ballast = {k: D(r["route_distance_nm"]) for k, r in index(tables["ballast_distances"], "origin_port", "destination_port").items()}
    laden = index(tables["laden_routes"], "cargo_id")
    prices = {k: D(r["price_usd_per_tonne"]) for k, r in index(tables["bunker_forward_curve"], "period", "pricing_location", "fuel_grade").items()}
    v, c = vessels[vessel_id], cargoes[cargo_id]
    price_override = period
    period = c["laycan_start_utc"][:7] if period is None else period
    location = ports[c["load_port"]]["bunker_pricing_location"]
    if any((period, location, fuel) not in prices for fuel in ("VLSFO", "MGO")):
        raise ValueError("No bunker prices for that month and location.")
    q = D(lift)
    ballast_nm = ballast[v['current_port'], c['load_port']] + scenario.additional_ballast_nm
    bd = ballast_nm / num(v, f'{speed}_ballast_speed_knots') / 24
    ld = num(laden[cargo_id], 'route_distance_nm') / num(v, f'{speed}_laden_speed_knots') / 24
    start_gap = D(str((date(c['laycan_start_utc']) - date(v['available_from_utc'])).total_seconds())) / 86400
    wait = max(D(0), start_gap - bd) + scenario.idle_delay_days
    loading = q / num(c, 'load_rate_tonnes_per_day') + num(c, 'load_turn_time_hours') / 24 + scenario.working_delay_days
    discharge = q / num(c, 'discharge_rate_tonnes_per_day') + num(c, 'discharge_turn_time_hours') / 24
    days = bd + wait + loading + ld + discharge
    opening = {"VLSFO": num(v, "vlsfo_rob_tonnes"), "MGO": num(v, "mgo_rob_tonnes")}
    reserves = {grade: num(assumptions, f"{grade.lower()}_reserve_tonnes") for grade in opening}
    stages = [
        ("Ballast passage", bd, {"VLSFO": bd*num(v, f"{speed}_ballast_vlsfo_tpd"), "MGO": bd*num(v, f"{speed}_ballast_mgo_tpd")}),
        ("Waiting at load port", wait, {"VLSFO": wait*num(v, "port_idle_vlsfo_tpd"), "MGO": D(0)}),
        ("Loading", loading, {"VLSFO": loading*num(v, "port_working_vlsfo_tpd"), "MGO": D(0)}),
        ("Laden passage", ld, {"VLSFO": ld*num(v, f"{speed}_laden_vlsfo_tpd"), "MGO": ld*num(v, f"{speed}_laden_mgo_tpd")}),
        ("Discharge", discharge, {"VLSFO": discharge*num(v, "port_working_vlsfo_tpd"), "MGO": D(0)}),
    ]
    fuel = audit_fuel(opening, stages)
    plan = plan_fuel(opening, reserves, stages)
    fuel["bunker_plan"] = {"current_port": v["current_port"], "load_port": c["load_port"], "by_grade": plan}
    fuel["opening_rob_pass"] = fuel["fuel_pass"]
    fuel["planning_purchase_assumed"] = policy.fuel_policy == "planning_purchase"
    reserves_met_from_opening = all(not entry["purchase_before_ballast_tonnes"] and
                                    not entry["purchase_at_load_tonnes"] for entry in plan.values())
    fuel["fuel_pass"] = reserves_met_from_opening or fuel["planning_purchase_assumed"]
    if fuel["planning_purchase_assumed"]:
        fuel["fuel_status"] = "covered by planning-purchase assumption"
    elif not reserves_met_from_opening:
        fuel["fuel_status"] = "replenishment plan required to maintain reserves"
    for grade, entry in plan.items():
        fuel[f"{grade.lower()}_planned_end_balance_tonnes"] = entry["discharge_complete_tonnes"]

    vf = sum(burn["VLSFO"] for _, _, burn in stages)
    mg = sum(burn["MGO"] for _, _, burn in stages)
    purchases = {grade: entry["purchase_before_ballast_tonnes"] + entry["purchase_at_load_tonnes"]
                 for grade, entry in plan.items()}
    cost = (vf*prices[period, location, 'VLSFO'] + mg*prices[period, location, 'MGO']) * (1 + scenario.bunker_increase)
    dw = q + sum(entry["laden_departure_tonnes"] for entry in plan.values()) + num(assumptions, 'other_deadweight_tonnes')
    draft = num(v, 'ballast_draft_m') + (num(v, 'summer_draft_m')-num(v, 'ballast_draft_m'))*dw/num(v, 'dwt_tonnes')
    limit = num(v, 'summer_draft_m')
    port_checks = []
    for role, code in [('loading', c['load_port']), ('discharge', c['discharge_port'])]:
        port_limit = num(ports[code], 'coursework_max_draft_m')
        port_checks.append(dict(port_role=role, port_code=code, limit_m=port_limit,
            compared_draft_m=draft, headroom_m=port_limit-draft,
            required_margin_m=D(policy.port_draft_margin_m),
            passes=port_limit-draft >= D(policy.port_draft_margin_m),
            basis='laden-departure draft proxy; not a stage-specific draft'))
    threshold = num(c, 'special_freight_threshold_tonnes')
    billed_tonnes = min(q, threshold) + max(D(0), q-threshold)/2 if c['special_freight_rule'] == 'half freight above threshold' else q
    revenue = billed_tonnes*num(c, 'contract_freight_rate_usd_per_tonne')
    commission = revenue*num(c, 'commission_rate')
    port_cost = (num(c, 'load_port_cost_usd') + num(c, 'discharge_port_cost_usd')) * (1 + scenario.port_cost_increase)
    # No canal data supplied. Zero reproduces CHECK-01, not a global route rule.
    canal = D(0)
    cashflow = revenue-commission-cost-port_cost-canal
    hire = days*num(v, 'hire_rate_usd_per_day')
    arrival = date(v['available_from_utc'])+timedelta(days=float(bd))
    slack = D(str((date(c['laycan_end_utc'])-date(v['available_from_utc'])).total_seconds()))/86400-bd
    return dict(vessel_id=vessel_id, cargo_id=cargo_id, selected_lift_tonnes=q,
        speed=speed, ballast_distance_nm=ballast_nm, laden_distance_nm=num(laden[cargo_id], 'route_distance_nm'),
        ballast_days=bd, laycan_wait_days=wait, loading_days=loading, laden_days=ld, discharge_days=discharge, voyage_days=days,
        vlsfo_consumption_tonnes=vf, mgo_consumption_tonnes=mg, vlsfo_purchase_tonnes=purchases["VLSFO"], mgo_purchase_tonnes=purchases["MGO"],
        bunker_price_period=period, bunker_price_override=price_override, bunker_pricing_location=location, bunker_cost_usd=cost,
        departure_deadweight_tonnes=dw, deadweight_margin_tonnes=num(v,'dwt_tonnes')-dw,
        estimated_sailing_draft_m=draft, draft_margin_m=limit-draft,
        required_summer_draft_margin_m=num(assumptions,'minimum_draft_margin_m'),
        limiting_draft_margin_m=min(limit-draft, *(check["headroom_m"] for check in port_checks)),
        port_draft_checks=port_checks, port_draft_policy=policy.port_draft_policy,
        port_draft_pass=all(p['passes'] for p in port_checks), freight_revenue_usd=revenue,
        commission_usd=commission, port_cost_usd=port_cost, voyage_cashflow_usd=cashflow, tce_usd_per_day=cashflow/days,
        hire_cost_usd=hire, voyage_contribution_usd=cashflow-hire, arrival_at_load_utc=arrival.isoformat(),
        laycan_slack_days=slack, quantity_pass=num(c,'minimum_quantity_tonnes')<=q<=num(c,'maximum_quantity_tonnes'),
        laycan_pass=slack>=0, deadweight_pass=dw<=num(v,'dwt_tonnes'), draft_pass=limit-draft>=num(assumptions,'minimum_draft_margin_m'), **fuel)
