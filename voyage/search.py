"""Load-port and cargo search for the Voyages page.

This is the single seam between the page and the data source. It reads the
frozen tables today; a live database only needs to replace `search` and
`open_cargoes` with queries that return the same shapes. Only committed
cargoes are searched, because market cargoes cannot be evaluated yet.
"""
import re
from datetime import datetime
from difflib import SequenceMatcher

from voyage.data import index, load_tables


def _fold(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _word_score(word, haystack, tokens):
    """1 for a substring hit, else the best of an in-order subsequence or a close spelling."""
    if word in haystack or word in haystack.replace(" ", ""):
        return 1.0
    best = 0.0
    for token in tokens:
        letters = iter(token)
        if len(word) >= 2 and token[:1] == word[:1] and all(ch in letters for ch in word):
            best = max(best, .85)  # "mf1" → "mf 01", "rzh" → "rizhao"
        best = max(best, SequenceMatcher(None, word, token[:len(word) + 2]).ratio())
    return best


def fuzzy_score(query, text):
    """How well every typed word matches `text`, from 0 to 1. Typos and skipped
    letters still match: "rizao", "laem chabng" and "mf2" all find their row."""
    words = _fold(query).split()
    if not words:
        return 1.0
    haystack = _fold(text)
    parts = haystack.split()
    # Neighbouring words joined, so "mf2" can match "mf 02" and "cc2" can match "cc 02".
    tokens = parts + ["".join(parts[i:i + 3]) for i in range(len(parts))]
    scores = [_word_score(word, haystack, tokens) for word in words]
    return 0.0 if min(scores) < .82 else sum(scores) / len(scores)


def _laycan(cargo):
    opens = datetime.fromisoformat(cargo["laycan_start_utc"].replace("Z", "+00:00"))
    closes = datetime.fromisoformat(cargo["laycan_end_utc"].replace("Z", "+00:00"))
    return f'{opens:%d}–{closes:%d %b}' if opens.month == closes.month else f'{opens:%d %b}–{closes:%d %b}'


def open_cargoes(port_code, tables=None):
    """Committed and market cargoes loading at a port, earliest laycan first."""
    tables = tables or load_tables()
    rows = [c for c in tables["committed_cargoes"] + tables["market_cargoes"] if c["load_port"] == port_code]
    return sorted(rows, key=lambda c: (c["laycan_start_utc"], c["cargo_id"]))


def _results(tables):
    ports = index(tables["ports"], "port_code")
    by_port = {}
    for cargo in tables["committed_cargoes"] + tables["market_cargoes"]:
        by_port.setdefault(cargo["load_port"], []).append(cargo)
    results = []
    for code, cargoes in sorted(by_port.items(), key=lambda item: ports[item[0]]["port_name"]):
        port = ports[code]
        count = len(cargoes)
        results.append({"kind": "port", "id": code, "port_code": code,
                        "label": f'{port["port_name"]}, {port["country"]} ({code}) · {count} open cargo{"" if count == 1 else "es"}',
                        "terms": " ".join([port["port_name"], port["country"], port["region"], code,
                                           *(c["commodity"].replace("_", " ") for c in cargoes)])})
    for cargo in sorted(tables["committed_cargoes"] + tables["market_cargoes"], key=lambda c: c["cargo_id"]):
        load, discharge = ports[cargo["load_port"]], ports[cargo["discharge_port"]]
        commodity = cargo["commodity"].replace("_", " ")
        results.append({"kind": "cargo", "id": cargo["cargo_id"], "port_code": cargo["load_port"],
                        "label": f'{cargo["cargo_id"]} · {commodity} · {load["port_name"]} → {discharge["port_name"]} · {_laycan(cargo)}',
                        "terms": " ".join([cargo["cargo_id"], commodity, cargo["counterparty_id"], load["port_name"],
                                           load["country"], cargo["load_port"], discharge["port_name"], cargo["discharge_port"]])})
    return results


def search(text="", limit=50, tables=None):
    """Ports and cargoes matching every word typed across name, code, country, region, commodity or
    charterer. Rows containing every word come first; when none do, matching turns fuzzy so typos and
    skipped letters still find a row ("kamsr", "baxite", "qingdoa"). An exact code returns that row alone.
    Within a tier, name prefixes rank first, then closer matches."""
    words = text.lower().split()
    found = []
    for result in _results(tables or load_tables()):
        haystack = (result["label"] + " " + result["terms"]).lower()
        literal = all(word in haystack for word in words)
        score = 1.0 if literal else fuzzy_score(text, haystack)
        if score <= 0:
            continue
        exact = any(word == result["id"].lower() for word in words)
        prefix = bool(words) and result["label"].lower().startswith(words[0])
        found.append((not exact, not literal, not prefix, -round(score, 3), result["kind"] != "port", result["label"], result))
    for tier in (0, 1):  # an exact code, then literal matches, win over anything looser
        if any(not item[tier] for item in found):
            found = [item for item in found if not item[tier]]
            break
    return [item[-1] for item in sorted(found, key=lambda item: item[:6])][:limit]
