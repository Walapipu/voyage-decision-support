"""Central, versioned working assumptions; separate from source arithmetic."""
from dataclasses import dataclass, asdict
from decimal import Decimal
from pathlib import Path
import tomllib

POLICY_PATH = Path(__file__).resolve().parents[1] / "config" / "modelling.toml"


@dataclass(frozen=True)
class ModellingPolicy:
    fuel_policy: str = "planning_purchase"
    laycan_policy: str = "exclude_late"
    port_draft_policy: str = "report_only"
    port_draft_margin_m: str = "0.00"

    def __post_init__(self):
        if self.fuel_policy not in ("planning_purchase", "opening_rob_only"):
            raise ValueError("Unknown fuel policy")
        if self.laycan_policy != "exclude_late":
            raise ValueError("Laycan extensions and penalties are not implemented")
        if self.port_draft_policy not in ("report_only", "exclude"):
            raise ValueError("Unknown port draft policy")
        margin = Decimal(self.port_draft_margin_m)
        if not margin.is_finite() or margin < 0:
            raise ValueError("Port draft margin must be finite and nonnegative")


def load_policy():
    return ModellingPolicy(**tomllib.loads(POLICY_PATH.read_text(encoding="utf-8")))


def conventions(policy):
    return {
        "working_assumptions": asdict(policy),
        "speed": "economical",
        "laycan": "Load-port arrival at or before closing (UTC); early arrival waits until opening. Late arrivals excluded outright. No separate NOR or readiness milestone, extensions or penalties modelled.",
        "fuel": ("Shortfalls assumed covered by the voyage planning purchase, with no added bunkering days, charges or diversion. Stage ledger is an opening-ROB-only diagnostic, not an actual delivery schedule."
                 if policy.fuel_policy == "planning_purchase" else
                 "Opening-ROB-only diagnostic: shortages exclude recommendations; no replenishment assumed."),
        "bunker_pricing": "Consumption × load-port regional price proxy for explicitly selected month (default March 2026); not purchase × price or a bunkering-stop recommendation.",
        "draft": "Required CSV margin applies to summer draft at laden departure. Port limits are separate comparisons using that same departure draft, not stage-specific drafts.",
        "port_draft": f"{policy.port_draft_policy}; separate port margin {policy.port_draft_margin_m} m; current-port draft is not evaluated",
        "reserves": "Included in voyage-end purchase balance and departure deadweight; continuous reserve maintenance remains unresolved.",
        "canal_cost": "zero provisional: no canal inputs supplied",
        "tce": "net voyage cashflow before hire divided by total voyage days, including ballast",
        "contribution": "net voyage cashflow less hire for that voyage; different voyage horizons",
    }
