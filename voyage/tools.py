"""Allowlisted tool definitions and server-side argument validation."""

import json
from functools import lru_cache

from jsonschema import Draft202012Validator

from voyage.data import catalog, derived, load_tables
from voyage.decision import evaluate_voyage, compare_vessels, OBJECTIVES
from voyage.analysis import analyst_facts

LIFT = {"type": "number", "exclusiveMinimum": 0, "maximum": 1000000,
        "description": "Explicitly requested cargo lift in tonnes."}


def definition(name, description, properties, required):
    return {"type": "function", "function": {"name": name, "description": description,
            "parameters": {"type": "object", "properties": properties,
                           "required": required, "additionalProperties": False}}}


@derived
@lru_cache(maxsize=1)
def tool_definitions():
    """The allowlisted tools. Vessel, cargo and month choices come from the current data, so a
    vessel, cargo or price month added to the data is accepted without a code change."""
    tables = load_tables()
    committed, market_cargo = ([r["cargo_id"] for r in tables[t]] for t in ("committed_cargoes", "market_cargoes"))
    managed, market_vessel = ([r["vessel_id"] for r in tables[t]] for t in ("managed_vessels", "market_vessels"))
    cargo = {"type": "string", "enum": committed + market_cargo,
             "description": f"Committed cargoes ({', '.join(committed)}) use contract freight; "
                            f"market cargoes ({', '.join(market_cargo)}) use the assumed freight quote."}
    vessel = {"type": "string", "enum": managed + market_vessel,
              "description": f"Managed vessels ({', '.join(managed)}) use their own hire; "
                             f"market vessels ({', '.join(market_vessel)}) are chartered in at the assumed hire."}
    period = {"type": "string", "enum": sorted({r["period"] for r in tables["bunker_forward_curve"]}),
              "description": "Optional alternate pricing month. The default is the cargo laycan opening month."}
    return [
        definition("get_dataset_catalog", "List actual dataset vessels, cargoes, quantities and missing inputs.", {}, []),
        definition("calculate_voyage", "Calculate one vessel/cargo voyage in Python, including feasibility, TCE and contribution.",
                   {"vessel_id": vessel, "cargo_id": cargo, "lift_tonnes": LIFT, "period": period},
                   ["vessel_id", "cargo_id", "lift_tonnes"]),
        definition("compare_vessels", "Rank vessels for one cargo. Managed vessels always; set include_market_vessels to add "
                   "chartered-in market vessels for a committed cargo. Omit lift only when the user wants to optimise within cargo tolerance.",
                   {"cargo_id": cargo, "lift_tonnes": LIFT, "period": period,
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
    schema = next(t["function"]["parameters"] for t in tool_definitions() if t["function"]["name"] == name)
    if not Draft202012Validator(schema).is_valid(args):
        return {"error": "Invalid tool arguments. Check vessel/cargo IDs, positive lift in tonnes, and month. No calculation ran."}
    try:
        result = HANDLERS[name](**args)
        if result.get("rows"):
            result["analysis"] = analyst_facts(result["rows"], result.get("ranking"))
        return result
    except ValueError as exc:
        return {"error": str(exc)}
