"""Allowlisted tool definitions and server-side argument validation."""

import json
from jsonschema import Draft202012Validator

from voyage.data import catalog
from voyage.decision import evaluate_voyage, compare_vessels, OBJECTIVES
from voyage.analysis import analyst_facts

CARGO = {"type": "string", "enum": [f"CC-{i:02d}" for i in range(1, 4)] + [f"MC-{i:02d}" for i in range(1, 9)],
         "description": "CC = committed cargo (contract freight); MC = market cargo (assumed freight quote)."}
VESSEL = {"type": "string", "enum": [f"MF-{i:02d}" for i in range(1, 5)] + [f"MV-{i:02d}" for i in range(1, 12)],
          "description": "MF = managed vessel (own hire); MV = market vessel chartered in at its assumed hire."}
LIFT = {"type": "number", "exclusiveMinimum": 0, "maximum": 1000000,
        "description": "Explicitly requested cargo lift in tonnes."}
PERIOD = {"type": "string", "pattern": "^2026-(0[1-9]|1[0-2])$",
          "description": "Optional alternate pricing month. The default is the cargo laycan opening month."}


def definition(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required, "additionalProperties": False}}}


TOOLS = [
    definition("get_dataset_catalog", "List actual dataset vessels, cargoes, quantities and missing inputs.", {}, []),
    definition("calculate_voyage", "Calculate one vessel/cargo voyage in Python, including feasibility, TCE and contribution.",
               {"vessel_id": VESSEL, "cargo_id": CARGO, "lift_tonnes": LIFT, "period": PERIOD},
               ["vessel_id", "cargo_id", "lift_tonnes"]),
    definition("compare_vessels", "Rank vessels for one cargo. Managed vessels always; set include_market_vessels to add "
               "chartered-in market vessels for a committed cargo. Omit lift only when the user wants to optimise within cargo tolerance.",
               {"cargo_id": CARGO, "lift_tonnes": LIFT, "period": PERIOD,
                "objective": {"type": "string", "enum": list(OBJECTIVES)},
                "include_market_vessels": {"type": "boolean", "description": "Add chartered-in market vessels (committed cargoes only)."}},
               ["cargo_id"]),
]
def _compare(include_market_vessels=False, **args):
    return compare_vessels(include_market=include_market_vessels, **args)


HANDLERS = {"get_dataset_catalog": catalog, "calculate_voyage": evaluate_voyage, "compare_vessels": _compare}


def execute_tool(name, arguments):
    if name not in HANDLERS:
        return {"error": "Unknown tool. No action was executed."}
    try:
        args = json.loads(arguments, parse_constant=lambda value: (_ for _ in ()).throw(ValueError("Non-finite number")))
    except (ValueError, TypeError):
        return {"error": "Tool arguments must be valid JSON with finite numbers."}
    schema = next(t["function"]["parameters"] for t in TOOLS if t["function"]["name"] == name)
    if not Draft202012Validator(schema).is_valid(args):
        return {"error": "Invalid tool arguments. Check vessel/cargo IDs, positive lift in tonnes, and month. No calculation ran."}
    try:
        result = HANDLERS[name](**args)
        if result.get("rows"):
            result["analysis"] = analyst_facts(result["rows"], result.get("ranking"))
        return result
    except ValueError as exc:
        return {"error": str(exc)}
