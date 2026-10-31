"""Deterministic Decimal voyage calculation, adapted from the reconciled CSV check."""
from datetime import datetime, timedelta
from decimal import Decimal as D, InvalidOperation, getcontext
from voyage.data import load_tables, index

getcontext().prec = 32

def num(row, key): return D(row[key])
def date(value): return datetime.fromisoformat(value.replace("Z", "+00:00"))

def calculate(vessel_id, cargo_id, lift, period="2026-03", *, bunker_increase=0,
              port_delay_days=0, port_cost_increase=0, additional_ballast_nm=0):
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
    scenario = [D(str(value)) for value in (bunker_increase, port_delay_days, port_cost_increase, additional_ballast_nm)]
    if any(not value.is_finite() or value < 0 for value in scenario):
        raise ValueError("Stress inputs must be finite and nonnegative.")
    bunker_increase, port_delay_days, port_cost_increase, additional_ballast_nm = scenario
    ballast_nm = ballast[v['current_port'], c['load_port']] + additional_ballast_nm
    bd = ballast_nm / num(v, 'economical_ballast_speed_knots') / 24
    ld = num(laden[cargo_id], 'route_distance_nm') / num(v, 'economical_laden_speed_knots') / 24
    start_gap = D(str((date(c['laycan_start_utc']) - date(v['available_from_utc'])).total_seconds())) / 86400
    wait = max(D(0), start_gap - bd) + port_delay_days
    loading = q / num(c, 'load_rate_tonnes_per_day') + num(c, 'load_turn_time_hours') / 24
    discharge = q / num(c, 'discharge_rate_tonnes_per_day') + num(c, 'discharge_turn_time_hours') / 24
    days = bd + wait + loading + ld + discharge
    vf = bd*num(v, 'economical_ballast_vlsfo_tpd') + ld*num(v, 'economical_laden_vlsfo_tpd') + wait*num(v, 'port_idle_vlsfo_tpd') + (loading+discharge)*num(v, 'port_working_vlsfo_tpd')
    mg = bd*num(v, 'economical_ballast_mgo_tpd') + ld*num(v, 'economical_laden_mgo_tpd')
    vp = max(D(0), vf + num(assumptions, 'vlsfo_reserve_tonnes') - num(v, 'vlsfo_rob_tonnes'))
    mp = max(D(0), mg + num(assumptions, 'mgo_reserve_tonnes') - num(v, 'mgo_rob_tonnes'))
    location = ports[c['load_port']]['bunker_pricing_location']
    cost = (vf*prices[period, location, 'VLSFO'] + mg*prices[period, location, 'MGO']) * (1 + bunker_increase)
    dw = q + ld*(num(v, 'economical_laden_vlsfo_tpd')+num(v, 'economical_laden_mgo_tpd')) + num(assumptions, 'vlsfo_reserve_tonnes') + num(assumptions, 'mgo_reserve_tonnes') + num(assumptions, 'other_deadweight_tonnes')
    draft = num(v, 'ballast_draft_m') + (num(v, 'summer_draft_m')-num(v, 'ballast_draft_m'))*dw/num(v, 'dwt_tonnes')
    # Generalisation: conservative limiting draft. The supplied check only
    # distinguishes summer-draft margin from port-only margin.
    limit = min(num(v, 'summer_draft_m'), num(ports[c['load_port']], 'coursework_max_draft_m'), num(ports[c['discharge_port']], 'coursework_max_draft_m'))
    threshold = num(c, 'special_freight_threshold_tonnes')
    billed_tonnes = min(q, threshold) + max(D(0), q-threshold)/2 if c['special_freight_rule'] == 'half freight above threshold' else q
    revenue = billed_tonnes*num(c, 'contract_freight_rate_usd_per_tonne')
    commission = revenue*num(c, 'commission_rate')
    port_cost = (num(c, 'load_port_cost_usd')+num(c, 'discharge_port_cost_usd')) * (1 + port_cost_increase)
    # No canal data supplied. Zero reproduces CHECK-01, not a global route rule.
    canal = D(0)
    cashflow = revenue-commission-cost-port_cost-canal
    hire = days*num(v, 'hire_rate_usd_per_day')
    arrival = date(v['available_from_utc'])+timedelta(days=float(bd))
    slack = D(str((date(c['laycan_end_utc'])-date(v['available_from_utc'])).total_seconds()))/86400-bd
    return dict(vessel_id=vessel_id, cargo_id=cargo_id, selected_lift_tonnes=q,
        ballast_distance_nm=ballast_nm, laden_distance_nm=num(laden[cargo_id], 'route_distance_nm'),
        ballast_days=bd, laycan_wait_days=wait, loading_days=loading, laden_days=ld, discharge_days=discharge, voyage_days=days,
        vlsfo_consumption_tonnes=vf, mgo_consumption_tonnes=mg, vlsfo_purchase_tonnes=vp, mgo_purchase_tonnes=mp,
        bunker_price_period=period, bunker_pricing_location=location, bunker_cost_usd=cost,
        departure_deadweight_tonnes=dw, deadweight_margin_tonnes=num(v,'dwt_tonnes')-dw,
        estimated_sailing_draft_m=draft, draft_margin_m=limit-draft, freight_revenue_usd=revenue,
        commission_usd=commission, port_cost_usd=port_cost, voyage_cashflow_usd=cashflow, tce_usd_per_day=cashflow/days,
        hire_cost_usd=hire, voyage_contribution_usd=cashflow-hire, arrival_at_load_utc=arrival.isoformat(),
        laycan_slack_days=slack, quantity_pass=num(c,'minimum_quantity_tonnes')<=q<=num(c,'maximum_quantity_tonnes'),
        laycan_pass=slack>=0, deadweight_pass=dw<=num(v,'dwt_tonnes'), draft_pass=limit-draft>=num(assumptions,'minimum_draft_margin_m'))
