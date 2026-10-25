"""Allowlisted tool definitions and server-side argument validation."""

import json
from jsonschema import Draft202012Validator

from voyage.data import catalog
from voyage.decision import evaluate_voyage, compare_vessels

CARGO = {"type": "string", "enum": ["CC-01", "CC-02", "CC-03"]}
LIFT = {"type": "number", "exclusiveMinimum": 0, "maximum": 1000000,
        "description": "Explicitly requested cargo lift in tonnes. Ask the user if unspecified."}
PERIOD = {"type": "string", "pattern": "^2026-(0[1-9]|1[0-2])$",
          "description": "Bunker pricing month. Default March 2026; always disclose it."}


def definition(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required, "additionalProperties": False}}}


TOOLS = [
    definition("get_dataset_catalog", "List actual dataset vessels, cargoes, quantities and missing inputs.", {}, []),
    definition("calculate_voyage", "Calculate one managed-vessel/committed-cargo voyage in Python, including feasibility, TCE and contribution.",
               {"vessel_id": {"type": "string", "enum": ["MF-01", "MF-02", "MF-03", "MF-04"]},
                "cargo_id": CARGO, "lift_tonnes": LIFT, "period": PERIOD},
               ["vessel_id", "cargo_id", "lift_tonnes"]),
    definition("compare_vessels", "Compare all four managed vessels for one committed cargo at the requested lift. Not fleet optimisation.",
               {"cargo_id": CARGO, "lift_tonnes": LIFT, "period": PERIOD}, ["cargo_id", "lift_tonnes"]),
]
HANDLERS = {"get_dataset_catalog": catalog, "calculate_voyage": evaluate_voyage, "compare_vessels": compare_vessels}


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
        return HANDLERS[name](**args)
    except ValueError as exc:
        return {"error": str(exc)}
