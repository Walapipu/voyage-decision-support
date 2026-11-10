"""Slash shortcuts typed into the chat: /voyages, /compare, /analytics and /help.

They run on the voyage engine directly, so they answer instantly and never need the model.
Only what the user types is used; a missing lift becomes the cargo's contract (nominal) quantity.
"""
import re

from voyage.analysis import analyst_facts
from voyage.market import all_cargoes
from voyage.data import index, load_tables
from voyage.decision import compare_vessels, evaluate_voyage

MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}
CHECK_NAMES = {"quantity": "lift outside range", "laycan": "misses laycan", "deadweight": "over deadweight",
               "draft": "draft margin", "fuel": "fuel", "port_draft": "port draft"}

COMMANDS = [
    ("/voyages", "MF-01 CC-01 200k t", "Fill the voyage inputs and open Voyages"),
    ("/compare", "CC-02 · MF-01 · MF-01 MF-03 CC-01", "Compare vessels for a cargo, or one vessel across cargoes"),
    ("/analytics", "CC-03 Apr 2026", "Fill the inputs and open Analytics"),
    ("/help", "", "List these shortcuts"),
]


def mentions(text):
    """Every vessel and cargo named in the text, plus the first lift and month. Explicit mentions only."""
    tables = load_tables()
    lowered = text.lower()
    cargo_ids = {c["cargo_id"] for c in tables["committed_cargoes"] + tables["market_cargoes"]}
    vessel_ids = {v["vessel_id"] for v in tables["managed_vessels"] + tables["market_vessels"]}
    periods = {r["period"] for r in tables["bunker_forward_curve"]}
    found = {"vessels": [], "cargoes": [], "lift": None, "period": None}
    for match in re.finditer(r"\b(cc|mc)[\s-]?0*(\d{1,2})\b", lowered):
        cargo = f"{match[1].upper()}-{int(match[2]):02d}"
        if cargo in cargo_ids and cargo not in found["cargoes"]:
            found["cargoes"].append(cargo)
    for match in re.finditer(r"\b(mf|mv)[\s-]?0*(\d{1,2})\b", lowered):
        vessel = f"{match[1].upper()}-{int(match[2]):02d}"
        if vessel in vessel_ids and vessel not in found["vessels"]:
            found["vessels"].append(vessel)
    for match in re.finditer(r"(\d[\d,]*(?:\.\d+)?)\s*(k\b|kt\b|thousand\b)?\s*(t\b|mt\b|tonnes?\b|tons?\b)?", lowered):
        if not (match[2] or match[3] or "," in match[1]):
            continue
        amount = float(match[1].replace(",", "")) * (1000 if match[2] else 1)
        if 1000 <= amount <= 1_000_000:
            found["lift"] = amount
            break
    if match := re.search(r"\b(20\d\d)-(\d{2})\b", lowered):
        month = f"{match[1]}-{match[2]}"
    elif match := re.search(r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b\.?\s*(20\d\d)?", lowered):
        # "may" is only a month when a year follows it ("May 2026", not "may I").
        month = None if match[1] == "may" and not match[2] else f"{match[2] or '2026'}-{MONTHS[match[1][:3]]:02d}"
    else:
        month = None
    if month in periods:
        found["period"] = month
    return found


def _nominal(cargo_id):
    return float(all_cargoes()[cargo_id]["nominal_quantity_tonnes"])


def _money(value):
    # Escaped: replies are Markdown, where a pair of dollar signs would render as LaTeX.
    return f'{"−" if value < 0 else ""}\\${abs(value):,.0f}'


def _month(period):
    if period is None:
        return "Laycan month"
    year, month = period.split("-")
    return f'{list(MONTHS)[int(month) - 1].title()} {year}'


def _status(row):
    return "feasible" if row["feasible"] else ", ".join(CHECK_NAMES.get(c, c) for c in row["failed_checks"])


def help_text(note=None):
    lines = [f"`{name}{' ' + example if example else ''}` · {what}" for name, example, what in COMMANDS]
    lead = (note + "\n\n") if note else ""
    return lead + "**Shortcuts**\n\n" + "\n\n".join(lines) + (
        "\n\nVessels MF-01 to MF-04, cargoes CC-01 to CC-03. Lifts like `200k t` or `164,000 t`; "
        "months like `Apr 2026`. A missing lift uses the cargo's contract quantity.")


def _selection(found, state):
    """Explicit inputs over the current ones; a newly named cargo starts at its contract quantity."""
    cargo = found["cargoes"][0] if found["cargoes"] else state.get("selected_cargo")
    lift = found["lift"]
    if lift is None and cargo:
        lift = state.get("selected_lift") if cargo == state.get("selected_cargo") and state.get("selected_lift") else _nominal(cargo)
    return {"selected_vessel": found["vessels"][0] if found["vessels"] else None,
            "selected_cargo": cargo, "selected_lift": lift,
            "price_period": found["period"] or state.get("price_period")}


def _open_page(page, found, state):
    selection = _selection(found, state)
    parts = [p for p in (selection["selected_vessel"], selection["selected_cargo"],
                         f'{selection["selected_lift"]:,.0f} t' if selection["selected_lift"] else None,
                         _month(selection["price_period"])) if p]
    note = "" if selection["selected_cargo"] else " Pick a cargo there to evaluate the fleet."
    return {"reply": f"Opened **{page}** · {' · '.join(parts)}.{note}", "selection": selection, "page": page}


def _compare_vessels(found, state):
    cargo = found["cargoes"][0]
    lift = found["lift"] or _nominal(cargo)
    period = found["period"] or state.get("price_period")
    subset = found["vessels"] if len(found["vessels"]) > 1 else None
    result = compare_vessels(cargo, lift, period, vessel_ids=subset)
    if subset:
        result["scope"] = f'{", ".join(found["vessels"])} for one cargo at one lift. Feasible voyages first, then contribution.'
    rows = result["rows"]
    result["analysis"] = analyst_facts(rows)
    best = next((r for r in rows if r["feasible"]), None)
    head = f'**{cargo} at {lift:,.0f} t · {_month(rows[0]["bunker_price_period"])} bunkers.** '
    if best:
        head += (f'{best["vessel_id"]} has the highest contribution, {_money(best["voyage_contribution_usd"])} '
                 f'at {_money(best["tce_usd_per_day"])}/day TCE. ')
    else:
        head += "No vessel passes every check at this lift; figures are hypothetical. "
    head += f'{sum(r["feasible"] for r in rows)} of {len(rows)} feasible.'
    failing = [f'{r["vessel_id"]} ({_status(r)})' for r in rows if not r["feasible"]]
    if failing:
        head += " Excluded: " + "; ".join(failing) + "."
    if len(found["vessels"]) == 1:
        named = next(r for r in rows if r["vessel_id"] == found["vessels"][0])
        if best and named is not best and named["feasible"]:
            head += f' {named["vessel_id"]} trails by {_money(best["voyage_contribution_usd"] - named["voyage_contribution_usd"])}.'
        elif named is best:
            head += f' {named["vessel_id"]} is the pick.'
    lead = best or rows[0]
    selection = {"selected_vessel": lead["vessel_id"], "selected_cargo": cargo, "selected_lift": float(lift), "price_period": period}
    return {"reply": head, "evidence": [{"tool": "compare_vessels", "result": result}], "selection": selection}


def _compare_cargoes(found, state):
    vessels = found["vessels"]
    cargoes = found["cargoes"] or [c["cargo_id"] for c in load_tables()["committed_cargoes"]]
    period = found["period"] or state.get("price_period")
    # One typed lift only makes sense for one cargo; otherwise each cargo runs at its contract quantity.
    rows = [evaluate_voyage(v, c, found["lift"] if found["lift"] and len(cargoes) == 1 else _nominal(c), period)["rows"][0]
            for v in vessels for c in cargoes]
    rows.sort(key=lambda r: (not r["feasible"], -r["voyage_contribution_usd"]))
    best = next((r for r in rows if r["feasible"]), None)
    who = vessels[0] if len(vessels) == 1 else ", ".join(vessels)
    head = f'**{who} across {len(cargoes)} committed cargo{"" if len(cargoes) == 1 else "es"} · {_month(period)} bunkers.** '
    head += (f'Best fit is {best["vessel_id"]} on {best["cargo_id"]}: {_money(best["voyage_contribution_usd"])} contribution at '
             f'{_money(best["tce_usd_per_day"])}/day TCE.' if best else f"No pairing passes every check.")
    failing = [f'{r["vessel_id"]} on {r["cargo_id"]} ({_status(r)})' for r in rows if not r["feasible"]]
    if failing:
        head += " Fails: " + "; ".join(failing) + "."
    lead = best or rows[0]
    selection = {"selected_vessel": lead["vessel_id"], "selected_cargo": lead["cargo_id"],
                 "selected_lift": float(lead["selected_lift_tonnes"]), "price_period": period}
    return {"reply": head, "evidence": [{"tool": "compare_cargoes", "result": {"rows": rows}}], "selection": selection}


def run_command(text, state):
    """Handle a slash shortcut. Returns None when the text is not a shortcut, so it goes to the model."""
    if not text.startswith("/"):
        return None
    name, _, rest = text[1:].partition(" ")
    name = name.lower()
    found = mentions(rest)
    try:
        if name in ("voyages", "voyage", "v"):
            return _open_page("Voyages", found, state)
        if name in ("analytics", "a"):
            return _open_page("Analytics", found, state)
        if name in ("compare", "c"):
            vessels, cargoes = found["vessels"], found["cargoes"]
            if cargoes and (len(vessels) != 1 or len(cargoes) == 1):
                return _compare_vessels(found, state)  # the fleet (or the vessels named) on one cargo
            if vessels:
                return _compare_cargoes(found, state)  # the vessels named across cargoes
            if state.get("selected_cargo"):
                return _compare_vessels({**found, "cargoes": [state["selected_cargo"]],
                                         "lift": found["lift"] or state.get("selected_lift")}, state)
            return {"reply": help_text("Name a cargo or a vessel to compare, for example `/compare CC-02` or `/compare MF-01`.")}
        if name in ("help", "", "?"):
            return {"reply": help_text()}
    except ValueError as exc:
        return {"reply": str(exc)}
    return {"reply": help_text(f"`/{name}` is not a shortcut.")}
