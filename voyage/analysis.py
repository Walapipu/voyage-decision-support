"""Deterministic analyst facts shared by the model and its embedded dashboard."""
import numpy as np
import pandas as pd

COSTS = {"Commission": "commission_usd", "Bunkers": "bunker_cost_usd",
         "Ports": "port_cost_usd", "Hire": "hire_cost_usd"}
STAGES = {"Ballast": "ballast_days", "Waiting": "laycan_wait_days",
          "Loading": "loading_days", "Laden": "laden_days", "Discharge": "discharge_days"}


def result_frame(rows):
    frame = pd.DataFrame(rows).copy()
    revenue = frame["freight_revenue_usd"].to_numpy(dtype=float)
    contribution = frame["voyage_contribution_usd"].to_numpy(dtype=float)
    frame["profit_margin_pct"] = np.divide(100 * contribution, revenue,
        out=np.full(len(frame), np.nan), where=revenue != 0)
    return frame


def analyst_facts(rows):
    """Describe only executed results. Never turn an infeasible result into a pick."""
    frame = result_frame(rows)
    feasible = frame[frame["feasible"]].sort_values("voyage_contribution_usd", ascending=False, kind="stable")
    focus = (feasible.iloc[0] if len(feasible) else frame.iloc[0]).to_dict()
    focus_margin = focus["profit_margin_pct"]
    facts = {
        "feasible_count": int(frame["feasible"].sum()), "evaluated_count": len(frame),
        "highest_contribution_feasible_vessel": str(focus["vessel_id"]) if len(feasible) else None,
        "focus_vessel": str(focus["vessel_id"]), "focus_is_feasible": bool(focus["feasible"]),
        "focus_margin_pct": float(focus_margin) if np.isfinite(focus_margin) else None,
        "cost_breakdown_usd": {name: float(focus[key]) for name, key in COSTS.items()},
        "duration_breakdown_days": {name: float(focus[key]) for name, key in STAGES.items()},
        "scope": "One cargo and lift. Rank feasible voyages by contribution after hire; voyage durations differ.",
        "chart_sections": ["Earnings comparison", "Revenue to contribution", "Voyage duration"],
    }
    facts["largest_cost"] = max(facts["cost_breakdown_usd"], key=facts["cost_breakdown_usd"].get)
    revenue = float(focus["freight_revenue_usd"])
    facts["cost_share_of_revenue_pct"] = {name: value / revenue * 100 if revenue else None
        for name, value in facts["cost_breakdown_usd"].items()}
    facts["ballast_share_of_days_pct"] = float(focus["ballast_days"] / focus["voyage_days"] * 100)
    if len(feasible) > 1:
        runner = feasible.iloc[1]
        facts["runner_up"] = str(runner["vessel_id"])
        facts["contribution_advantage_usd"] = float(focus["voyage_contribution_usd"] - runner["voyage_contribution_usd"])
        facts["tce_advantage_usd_per_day"] = float(focus["tce_usd_per_day"] - runner["tce_usd_per_day"])
        facts["ballast_days_saved_vs_runner_up"] = float(runner["ballast_days"] - focus["ballast_days"])
    return facts


def profit_tone(margin, dark=True):
    """Symmetric visual scale capped at +/-25 percentage points, not a rating."""
    if margin is None or not np.isfinite(margin):
        return "#9bb0c7" if dark else "#62768e", 0.0
    strength = float(np.clip(abs(margin) / 25, 0, 1))
    if margin == 0:
        return ("#f5c274" if dark else "#976315"), strength
    start, end = (([151, 213, 184], [31, 224, 148]) if margin > 0 else
                  ([235, 160, 168], [255, 75, 103])) if dark else (
                  ([54, 126, 88], [0, 112, 65]) if margin > 0 else
                  ([166, 74, 82], [188, 24, 48]))
    rgb = np.rint(np.array(start) + strength * (np.array(end) - start)).astype(int)
    return "#" + "".join(f"{value:02x}" for value in rgb), strength
