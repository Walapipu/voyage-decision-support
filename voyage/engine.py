"""Deterministic Decimal voyage calculation, adapted from the reconciled CSV check."""
from datetime import datetime, timedelta
from decimal import Decimal as D, InvalidOperation, getcontext
from voyage.data import load_tables, index
from voyage.fuel import audit_fuel
from voyage.policy import load_policy

getcontext().prec = 32

def num(row, key): return D(row[key])
def date(value): return datetime.fromisoformat(value.replace("Z", "+00:00"))

def calculate(vessel_id, cargo_id, lift, period="2026-03", policy=None):
    policy = policy or load_policy()
    tables = load_tables()
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
    location = ports[c["load_port"]]["bunker_pricing_location"]
    if any((period, location, fuel) not in prices for fuel in ("VLSFO", "MGO")):
        raise ValueError("No bunker prices for that month and location.")
    q = D(lift)
    bd = ballast[v['current_port'], c['load_port']] / num(v, 'economical_ballast_speed_knots') / 24
    ld = num(laden[cargo_id], 'route_distance_nm') / num(v, 'economical_laden_speed_knots') / 24
    start_gap = D(str((date(c['laycan_start_utc']) - date(v['available_from_utc'])).total_seconds())) / 86400
    wait = max(D(0), start_gap - bd)
    loading = q / num(c, 'load_rate_tonnes_per_day') + num(c, 'load_turn_time_hours') / 24
    discharge = q / num(c, 'discharge_rate_tonnes_per_day') + num(c, 'discharge_turn_time_hours') / 24
    days = bd + wait + loading + ld + discharge
    fuel = audit_fuel({"VLSFO": num(v, "vlsfo_rob_tonnes"), "MGO": num(v, "mgo_rob_tonnes")}, [
        ("Ballast passage", bd, {"VLSFO": bd*num(v, "economical_ballast_vlsfo_tpd"), "MGO": bd*num(v, "economical_ballast_mgo_tpd")}),
        ("Waiting at load port", wait, {"VLSFO": wait*num(v, "port_idle_vlsfo_tpd"), "MGO": D(0)}),
        ("Loading", loading, {"VLSFO": loading*num(v, "port_working_vlsfo_tpd"), "MGO": D(0)}),
        ("Laden passage", ld, {"VLSFO": ld*num(v, "economical_laden_vlsfo_tpd"), "MGO": ld*num(v, "economical_laden_mgo_tpd")}),
        ("Discharge", discharge, {"VLSFO": discharge*num(v, "port_working_vlsfo_tpd"), "MGO": D(0)}),
    ])
    vf = bd*num(v, 'economical_ballast_vlsfo_tpd') + ld*num(v, 'economical_laden_vlsfo_tpd') + wait*num(v, 'port_idle_vlsfo_tpd') + (loading+discharge)*num(v, 'port_working_vlsfo_tpd')
    mg = bd*num(v, 'economical_ballast_mgo_tpd') + ld*num(v, 'economical_laden_mgo_tpd')
    vp = max(D(0), vf + num(assumptions, 'vlsfo_reserve_tonnes') - num(v, 'vlsfo_rob_tonnes'))
    mp = max(D(0), mg + num(assumptions, 'mgo_reserve_tonnes') - num(v, 'mgo_rob_tonnes'))
    # Keep the unsupplied ledger visible, without treating its negative balances
    # as a feasibility failure under the authorised planning-purchase assumption.
    fuel['opening_rob_pass'] = fuel['fuel_pass']
    fuel['planning_purchase_assumed'] = policy.fuel_policy == 'planning_purchase'
    fuel['fuel_pass'] = fuel['opening_rob_pass'] or fuel['planning_purchase_assumed']
    if fuel['planning_purchase_assumed']:
        fuel['fuel_status'] = 'covered by planning-purchase assumption'
    fuel['vlsfo_planned_end_balance_tonnes'] = num(v, 'vlsfo_rob_tonnes') + vp - vf
    fuel['mgo_planned_end_balance_tonnes'] = num(v, 'mgo_rob_tonnes') + mp - mg
    location = ports[c['load_port']]['bunker_pricing_location']
    cost = vf*prices[period, location, 'VLSFO'] + mg*prices[period, location, 'MGO']
    dw = q + ld*(num(v, 'economical_laden_vlsfo_tpd')+num(v, 'economical_laden_mgo_tpd')) + num(assumptions, 'vlsfo_reserve_tonnes') + num(assumptions, 'mgo_reserve_tonnes') + num(assumptions, 'other_deadweight_tonnes')
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
    port_cost = num(c, 'load_port_cost_usd')+num(c, 'discharge_port_cost_usd')
    # No canal data supplied. Zero reproduces CHECK-01, not a global route rule.
    canal = D(0)
    cashflow = revenue-commission-cost-port_cost-canal
    hire = days*num(v, 'hire_rate_usd_per_day')
    arrival = date(v['available_from_utc'])+timedelta(days=float(bd))
    slack = D(str((date(c['laycan_end_utc'])-date(v['available_from_utc'])).total_seconds()))/86400-bd
    return dict(vessel_id=vessel_id, cargo_id=cargo_id, selected_lift_tonnes=q,
        ballast_distance_nm=ballast[v['current_port'], c['load_port']], laden_distance_nm=num(laden[cargo_id], 'route_distance_nm'),
        ballast_days=bd, laycan_wait_days=wait, loading_days=loading, laden_days=ld, discharge_days=discharge, voyage_days=days,
        vlsfo_consumption_tonnes=vf, mgo_consumption_tonnes=mg, vlsfo_purchase_tonnes=vp, mgo_purchase_tonnes=mp,
        bunker_price_period=period, bunker_pricing_location=location, bunker_cost_usd=cost,
        departure_deadweight_tonnes=dw, deadweight_margin_tonnes=num(v,'dwt_tonnes')-dw,
        estimated_sailing_draft_m=draft, draft_margin_m=limit-draft,
        required_summer_draft_margin_m=num(assumptions,'minimum_draft_margin_m'),
        port_draft_checks=port_checks, port_draft_policy=policy.port_draft_policy,
        port_draft_pass=all(p['passes'] for p in port_checks), freight_revenue_usd=revenue,
        commission_usd=commission, port_cost_usd=port_cost, voyage_cashflow_usd=cashflow, tce_usd_per_day=cashflow/days,
        hire_cost_usd=hire, voyage_contribution_usd=cashflow-hire, arrival_at_load_utc=arrival.isoformat(),
        laycan_slack_days=slack, quantity_pass=num(c,'minimum_quantity_tonnes')<=q<=num(c,'maximum_quantity_tonnes'),
        laycan_pass=slack>=0, deadweight_pass=dw<=num(v,'dwt_tonnes'), draft_pass=limit-draft>=num(assumptions,'minimum_draft_margin_m'), **fuel)
