"""Fuel inventory diagnostics and two-stop replenishment planning."""
from decimal import Decimal as D


def shortage_message(result):
    return " ".join(
        f'{item["fuel_grade"]}: {item["shortfall_tonnes"]:.3f} t short by the end of '
        f'{item["stage"].lower()} without replenishment.'
        for item in result.get("fuel_first_shortfalls", []))


def audit_fuel(opening, stages):
    """Project unsupplied balances through constant-burn stages, separately by grade.

    No replenishment is assumed. Negative balances after the first shortage are
    unmet demand, not a claim that the vessel can physically continue sailing.
    """
    balance = {grade: D(str(value)) for grade, value in opening.items()}
    ledger, first_shortfalls = [], []
    flagged = set()
    elapsed = D(0)
    for name, duration, consumption in stages:
        duration = D(str(duration))
        for grade, used in consumption.items():
            used = D(str(used))
            start = balance[grade]
            end = start - used
            ledger.append(dict(stage=name, fuel_grade=grade, opening_tonnes=start,
                               consumed_tonnes=used, closing_tonnes=end,
                               shortfall_tonnes=max(D(0), -end)))
            if end < 0 and grade not in flagged:
                # Constant burn: an exact zero at a stage end is not yet a deficit.
                depletion = elapsed + duration * max(D(0), start) / used if used else elapsed
                first_shortfalls.append(dict(fuel_grade=grade, stage=name,
                    depleted_after_days=depletion, shortfall_tonnes=-end))
                flagged.add(grade)
            balance[grade] = end
        elapsed += duration
    return dict(fuel_pass=not first_shortfalls,
                fuel_status="opening fuel sufficient" if not first_shortfalls else "replenishment plan required",
                fuel_ledger=ledger, fuel_first_shortfalls=first_shortfalls)



def plan_fuel(opening, reserves, stages):
    """Buy the minimum by grade at the current port and on arrival at loading."""
    plan = {}
    ballast, waiting, loading, laden, discharge = (stage[2] for stage in stages)
    for grade, reserve in reserves.items():
        at_origin = max(D(0), reserve + ballast[grade] - opening[grade])
        arrival = opening[grade] + at_origin - ballast[grade]
        at_load = max(D(0), reserve + waiting[grade] + loading[grade] + laden[grade] + discharge[grade] - arrival)
        departure = arrival + at_load - waiting[grade] - loading[grade]
        plan[grade] = {
            "opening_tonnes": opening[grade],
            "reserve_tonnes": reserve,
            "purchase_before_ballast_tonnes": at_origin,
            "load_arrival_tonnes": arrival,
            "purchase_at_load_tonnes": at_load,
            "laden_departure_tonnes": departure,
            "discharge_complete_tonnes": departure - laden[grade] - discharge[grade],
        }
    return plan
