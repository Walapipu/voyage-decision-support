"""Read the frozen source files without changing them."""

import csv
from pathlib import Path

RAW = Path(__file__).resolve().parent.parent / "data" / "raw"


def index(rows, *columns):
    result = {}
    for row in rows:
        key = tuple(row[c] for c in columns)
        key = key[0] if len(key) == 1 else key
        if key in result:
            raise ValueError(f"Duplicate data key: {key}")
        result[key] = row
    return result


def load_tables(root=RAW):
    tables = {}
    for path in sorted(root.rglob("*.csv")):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            tables[path.stem] = list(csv.DictReader(handle))
    required = {"managed_vessels", "market_vessels", "committed_cargoes", "market_cargoes",
                "ports", "ballast_distances", "laden_routes", "bunker_forward_curve",
                "commercial_assumptions", "validation_example"}
    if required - tables.keys():
        raise ValueError("Missing dataset files: " + ", ".join(sorted(required - tables.keys())))
    vessels = index(tables["managed_vessels"] + tables["market_vessels"], "vessel_id")
    cargoes = index(tables["committed_cargoes"] + tables["market_cargoes"], "cargo_id")
    ports = index(tables["ports"], "port_code")
    ballast = index(tables["ballast_distances"], "origin_port", "destination_port")
    routes = index(tables["laden_routes"], "cargo_id")
    prices = index(tables["bunker_forward_curve"], "period", "pricing_location", "fuel_grade")
    for vessel in vessels.values():
        if vessel["current_port"] not in ports:
            raise ValueError("Unknown vessel port.")
        for cargo in cargoes.values():
            if (vessel["current_port"], cargo["load_port"]) not in ballast:
                raise ValueError("Missing ballast route.")
    for cargo in cargoes.values():
        if cargo["load_port"] not in ports or cargo["discharge_port"] not in ports:
            raise ValueError("Unknown cargo port.")
        if cargo["cargo_id"] not in routes:
            raise ValueError("Missing laden route.")
        for fuel in ("VLSFO", "MGO"):
            if ("2026-03", ports[cargo["load_port"]]["bunker_pricing_location"], fuel) not in prices:
                raise ValueError("Missing baseline bunker price.")
    return tables


def catalog():
    tables = load_tables()
    return {
        "managed_vessels": [r["vessel_id"] for r in tables["managed_vessels"]],
        "market_vessels": [r["vessel_id"] for r in tables["market_vessels"]],
        "committed_cargoes": tables["committed_cargoes"],
        "market_cargoes": tables["market_cargoes"],
        "scope": "Calculations currently support managed vessels and committed cargoes only.",
        "missing_inputs": "11 market hire offers and 8 market freight quotes must be supplied; zero market freight is a placeholder.",
    }
