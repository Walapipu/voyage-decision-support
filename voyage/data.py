"""The data layer: read the tables from the configured source, validate them, hand out copies.

The source is the data-pack CSV files unless settings point at a database (voyage/sources.py).
Every read is validated before the app sees it, so a database with a missing route or price
fails the same way a broken CSV file would. A database is re-read every refresh_seconds; when
the data has actually changed, the cached results computed from it (plans, rankings, market
rates, the chat's tool lists) are cleared so the next request recomputes them. If a re-read
fails, the last good tables stay in use.
"""

import hashlib
import json
import logging
import threading
import time
from functools import lru_cache
from pathlib import Path

from voyage.sources import RAW, CsvSource, configured_source

log = logging.getLogger(__name__)

REQUIRED = {"managed_vessels", "market_vessels", "committed_cargoes", "market_cargoes",
            "ports", "ballast_distances", "laden_routes", "bunker_forward_curve",
            "commercial_assumptions", "validation_example"}

_lock = threading.Lock()
_state = {"key": None, "tables": None, "fingerprint": None, "read_at": 0.0}
_derived = []


def derived(cached):
    """Register an lru_cache'd function whose results come from the tables, so it is cleared
    when the data changes. Put it above @lru_cache."""
    _derived.append(cached)
    return cached


def index(rows, *columns):
    result = {}
    for row in rows:
        key = tuple(row[c] for c in columns)
        key = key[0] if len(key) == 1 else key
        if key in result:
            raise ValueError(f"Duplicate data key: {key}")
        result[key] = row
    return result


def validate(tables):
    """Required tables, unique keys and every join the engine relies on. Raises ValueError."""
    if REQUIRED - tables.keys():
        raise ValueError("Missing dataset tables: " + ", ".join(sorted(REQUIRED - tables.keys())))
    vessels = index(tables["managed_vessels"] + tables["market_vessels"], "vessel_id")
    cargoes = index(tables["committed_cargoes"] + tables["market_cargoes"], "cargo_id")
    ports = index(tables["ports"], "port_code")
    ballast = index(tables["ballast_distances"], "origin_port", "destination_port")
    routes = index(tables["laden_routes"], "cargo_id")
    prices = index(tables["bunker_forward_curve"], "period", "pricing_location", "fuel_grade")
    for vessel in vessels.values():
        if vessel["current_port"] not in ports:
            raise ValueError(f'Unknown port {vessel["current_port"]} for vessel {vessel["vessel_id"]}.')
        for cargo in cargoes.values():
            if (vessel["current_port"], cargo["load_port"]) not in ballast:
                raise ValueError(f'Missing ballast distance {vessel["current_port"]} to {cargo["load_port"]}.')
    for cargo in cargoes.values():
        if cargo["load_port"] not in ports or cargo["discharge_port"] not in ports:
            raise ValueError(f'Unknown port for cargo {cargo["cargo_id"]}.')
        if cargo["cargo_id"] not in routes:
            raise ValueError(f'Missing laden route for cargo {cargo["cargo_id"]}.')
        period = cargo["laycan_start_utc"][:7]
        for fuel in ("VLSFO", "MGO"):
            if (period, ports[cargo["load_port"]]["bunker_pricing_location"], fuel) not in prices:
                raise ValueError(f'Missing {fuel} price for {period} at {ports[cargo["load_port"]]["bunker_pricing_location"]}.')
    return tables


def _fingerprint(tables):
    return hashlib.sha256(json.dumps(tables, sort_keys=True).encode()).hexdigest()


def _current():
    source = configured_source()
    with _lock:
        due = source.refresh_seconds is not None and time.monotonic() - _state["read_at"] >= source.refresh_seconds
        if _state["tables"] is not None and _state["key"] == source.key and not due:
            return _state["tables"]
        try:
            tables = validate(source.read())
        except Exception as exc:
            if _state["tables"] is not None and _state["key"] == source.key:
                # Keep serving the last good data; try again after another interval.
                log.warning("Data refresh failed, keeping the last good tables: %s", type(exc).__name__)
                _state["read_at"] = time.monotonic()
                return _state["tables"]
            if isinstance(exc, ValueError):
                raise
            # Driver errors can carry the connection URL; name the error type only.
            raise RuntimeError(f"Could not read the voyage data ({type(exc).__name__}). "
                               "Check the database settings and that the database is reachable.") from None
        fingerprint = _fingerprint(tables)
        if _state["fingerprint"] not in (None, fingerprint):
            for cached in _derived:
                cached.cache_clear()
        _state.update(key=source.key, tables=tables, fingerprint=fingerprint, read_at=time.monotonic())
        return tables


def reset():
    """Forget the loaded tables and every result computed from them (tests, settings changes)."""
    with _lock:
        _state.update(key=None, tables=None, fingerprint=None, read_at=0.0)
        for cached in _derived:
            cached.cache_clear()


def load_tables(root=None):
    """Fresh copies of the current tables, so a caller's edits never leak into another's.
    root reads a specific folder of CSV files instead (tests)."""
    tables = _from_folder(Path(root)) if root is not None else _current()
    return {name: [dict(row) for row in rows] for name, rows in tables.items()}


@lru_cache(maxsize=4)
def _from_folder(root):
    return validate(CsvSource(root).read())


def catalog():
    tables = load_tables()
    return {
        "managed_vessels": [r["vessel_id"] for r in tables["managed_vessels"]],
        "market_vessels": [r["vessel_id"] for r in tables["market_vessels"]],
        "committed_cargoes": tables["committed_cargoes"],
        "market_cargoes": tables["market_cargoes"],
        "scope": "The engine prices every vessel and cargo. Market vessel hire and market cargo freight are stated assumptions derived from the pack's FFA references (Documents > Market rate assumptions).",
    }


__all__ = ["RAW", "derived", "index", "validate", "reset", "load_tables", "catalog"]
