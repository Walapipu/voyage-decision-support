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
    port_draft_policy: str = "exclude"
    port_draft_margin_m: str = "0.30"

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
        "fuel": ("Plan purchases before ballast departure at the current port and on arrival at the loading port, with no added time, charges or diversion. The opening-ROB ledger remains a diagnostic."
                 if policy.fuel_policy == "planning_purchase" else
                 "Opening-ROB-only diagnostic. Exclude voyages that need replenishment to maintain reserves."),
        "bunker_pricing": "Value consumption using the load-port regional price proxy. The base month is the cargo's laycan opening month. An explicit month runs an alternate price scenario.",
        "draft": "Compare laden-departure draft with summer draft and both port limits. The default requires at least 0.30 m below each limit.",
        "port_draft": f"{policy.port_draft_policy}; separate port margin {policy.port_draft_margin_m} m; current-port draft is not evaluated",
        "reserves": "Maintain 300 t VLSFO and 25 t MGO through discharge. Departure deadweight includes all fuel on board at laden departure, including discharge fuel and surplus.",
        "canal_cost": "zero provisional: no canal inputs supplied",
        "tce": "net voyage cashflow before hire divided by total voyage days, including ballast",
        "contribution": "net voyage cashflow less hire for that voyage; different voyage horizons",
    }
