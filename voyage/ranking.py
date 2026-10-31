"""Quantity search adapted from rank_any_cargo_with_tonnes.py; no file side effects."""
from decimal import Decimal
from math import isfinite

from voyage.data import load_tables, index
from voyage.decision import present
from voyage.engine import calculate


def quantity_options(cargo, step=1000):
    lo, mid, hi = (Decimal(cargo[k]) for k in
                   ('minimum_quantity_tonnes', 'nominal_quantity_tonnes', 'maximum_quantity_tonnes'))
    step = Decimal(str(step))
    if not all(v.is_finite() for v in (lo, mid, hi, step)) or not (0 < lo <= mid <= hi) or step <= 0:
        raise ValueError('Invalid quantity limits/step')
    count = int((hi - lo) // step)
    if count > 10000:
        raise ValueError('Quantity step is too small; choose at most 10,001 grid points.')
    values = {lo, mid, hi, *(lo + n * step for n in range(count + 1))}
    threshold = Decimal(cargo.get('special_freight_threshold_tonnes') or '0')
    if lo <= threshold <= hi:
        values.add(threshold)
    return sorted(values)


def rank_cargo(cargo_id, period='2026-03', quantity_step=1000, *,
               bunker_increase=.20, port_delay_days=3, port_cost_increase=.15,
               additional_ballast_nm=0, risk_weight=.5, lift_tonnes=None):
    """Search permitted quantities, or rank vessels at one exact user-supplied lift."""
    cargo_id = cargo_id.strip().upper()
    tables = load_tables()
    cargoes = index(tables['committed_cargoes'], 'cargo_id')
    if cargo_id not in cargoes:
        raise ValueError(f'Unknown committed cargo: {cargo_id}')
    if not isfinite(risk_weight) or not 0 <= risk_weight <= 1:
        raise ValueError('risk_weight must be between 0 and 1')
    stress_inputs = dict(bunker_increase=bunker_increase, port_delay_days=port_delay_days,
                         port_cost_increase=port_cost_increase, additional_ballast_nm=additional_ballast_nm)
    if any(not isfinite(v) or v < 0 for v in stress_inputs.values()):
        raise ValueError('Stress inputs must be finite and nonnegative')
    if lift_tonnes is None:
        quantities = quantity_options(cargoes[cargo_id], quantity_step)
    else:
        lift = Decimal(str(lift_tonnes))
        if not lift.is_finite() or not 0 < lift <= 1000000:
            raise ValueError('Lift must be finite and positive, at most 1,000,000 tonnes.')
        quantities = [lift]
    feasible, excluded = [], []
    for vessel in tables['managed_vessels']:
        for lift in quantities:
            identity = dict(vessel_id=vessel['vessel_id'], speed='economical', lift_tonnes=float(lift))
            base = present(calculate(vessel['vessel_id'], cargo_id, lift, period))
            if not base['feasible']:
                excluded.append({**identity, 'reason': ', '.join(base['failed_checks'])})
                continue
            stress = present(calculate(vessel['vessel_id'], cargo_id, lift, period, **stress_inputs))
            profit, downside = base['voyage_contribution_usd'], stress['voyage_contribution_usd']
            notes = []
            if not stress['laycan_pass']:
                notes.append('Extra ballast would miss laycan under stress')
            if downside < 0:
                notes.append('Stress scenario produces negative contribution')
            minimum_margin = float(tables['commercial_assumptions'][0]['minimum_draft_margin_m'])
            if base['draft_margin_m'] < minimum_margin + .1:
                notes.append('Tight draft clearance')
            notes.append(f"{base['ballast_days']:.1f} ballast days included")
            feasible.append({**base, **identity, 'recommended_tonnes': float(lift),
                             'profit_usd': profit, 'stress_profit_usd': downside,
                             'stress_loss_usd': profit - downside,
                             'risk_adjusted_score': (1-risk_weight)*profit + risk_weight*downside,
                             'stress_misses_laycan': not stress['laycan_pass'],
                             'considerations': '; '.join(notes)})
    feasible.sort(key=lambda r: (-r['profit_usd'], -r['tce_usd_per_day'], r['vessel_id']))
    for rank, row in enumerate(feasible, 1):
        row['profit_rank'] = rank
    for rank, row in enumerate(sorted(feasible, key=lambda r: (-r['risk_adjusted_score'], -r['profit_usd'])), 1):
        row['risk_rank'] = rank
    best = {}
    for row in feasible:
        best.setdefault(row['vessel_id'], row.copy())
    per_vessel = list(best.values())
    for rank, row in enumerate(per_vessel, 1):
        row['vessel_rank'] = rank
    top = feasible[0] if feasible else None
    recommendation = None if top is None else dict(cargo_id=cargo_id,
        recommended_vessel=top['vessel_id'], recommended_tonnes=top['recommended_tonnes'],
        recommended_speed='economical', expected_profit_usd=top['profit_usd'],
        stress_profit_usd=top['stress_profit_usd'], considerations=top['considerations'])
    return dict(cargo_id=cargo_id, recommendation=recommendation, all_options=feasible,
                best_per_vessel=per_vessel, excluded=excluded,
                assumptions={**stress_inputs, 'risk_weight': risk_weight, 'quantity_step': float(quantity_step),
                             'period': period, 'stress_is_not_probability': True,
                             'quantity_mode': 'optimal' if lift_tonnes is None else 'selected',
                             'selected_lift_tonnes': None if lift_tonnes is None else float(lift_tonnes)})
