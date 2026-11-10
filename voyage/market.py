"""Stated market assumptions: hire offers for market vessels, freight quotes for market cargoes.

The data pack leaves both blank on purpose. Both are derived here from the pack's own FFA
references so they are reproducible and move with the forward curve, not typed in by hand.
Parameters live in config/market_rates.toml; the reasoning is in docs/assumptions.md.
"""
import tomllib
from functools import lru_cache
from pathlib import Path
from statistics import mean

from voyage.data import index, load_tables

CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "market_rates.toml"
SPEC = ("economical_laden_speed_knots", "economical_laden_vlsfo_tpd", "economical_laden_mgo_tpd",
        "economical_ballast_speed_knots", "economical_ballast_vlsfo_tpd", "economical_ballast_mgo_tpd",
        "port_working_vlsfo_tpd")
FUEL_REFERENCE_PORT = "SGSIN"


def load_config():
    return tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def ffa_period(period):
    """FFA months run to 2026-03; later months use their quarter."""
    year, month = period.split("-")
    return period if month in ("02", "03") and year == "2026" else f"{year}-Q{(int(month) - 1) // 3 + 1}"


def _round(value, step):
    return round(round(value / step) * step, 2)


def reference_vessel(tables):
    """Pack-average Capesize across all 15 managed and market vessels, economical speed."""
    fleet = tables["managed_vessels"] + tables["market_vessels"]
    return {key: mean(float(v[key]) for v in fleet) for key in SPEC}


def benchmark_voyage(cargo, laden_nm, ship, prices, period, location):
    """Round voyage for a reference ship: ballast back over the laden distance, nominal lift.

    Returns days and the costs a freight rate must cover before the ship earns anything."""
    q = float(cargo["nominal_quantity_tonnes"])
    ballast = laden_nm / ship["economical_ballast_speed_knots"] / 24
    laden = laden_nm / ship["economical_laden_speed_knots"] / 24
    port = (q / float(cargo["load_rate_tonnes_per_day"]) + float(cargo["load_turn_time_hours"]) / 24
            + q / float(cargo["discharge_rate_tonnes_per_day"]) + float(cargo["discharge_turn_time_hours"]) / 24)
    vlsfo = (ballast * ship["economical_ballast_vlsfo_tpd"] + laden * ship["economical_laden_vlsfo_tpd"]
             + port * ship["port_working_vlsfo_tpd"])
    mgo = ballast * ship["economical_ballast_mgo_tpd"] + laden * ship["economical_laden_mgo_tpd"]
    bunkers = vlsfo * prices[period, location, "VLSFO"] + mgo * prices[period, location, "MGO"]
    ports = float(cargo["load_port_cost_usd"]) + float(cargo["discharge_port_cost_usd"])
    return {"days": ballast + laden + port, "bunkers": bunkers, "ports": ports,
            "net_tonnes": q * (1 - float(cargo["commission_rate"]))}


@lru_cache(maxsize=1)
def market_rates():
    tables, config = load_tables(), load_config()
    ports = index(tables["ports"], "port_code")
    laden = {k: float(r["route_distance_nm"]) for k, r in index(tables["laden_routes"], "cargo_id").items()}
    prices = {k: float(r["price_usd_per_tonne"]) for k, r in
              index(tables["bunker_forward_curve"], "period", "pricing_location", "fuel_grade").items()}
    ffa = {(r["route_code"], r["period"]): float(r["reference_value"]) for r in tables["ffa_reference"]}
    ship = reference_vessel(tables)
    cargoes = index(tables["committed_cargoes"] + tables["market_cargoes"], "cargo_id")

    def voyage(cargo, period):
        location = ports[cargo["load_port"]]["bunker_pricing_location"]
        return benchmark_voyage(cargo, laden[cargo["cargo_id"]], ship, prices, period, location)

    route_of = {cid: name for name, r in config["index_routes"].items() for cid in r["cargoes"]}

    def target_tce(cargo, period):
        """Daily earnings the quote must pay a reference ship, with the index it came from."""
        name = route_of.get(cargo["cargo_id"])
        if name is None:
            return ffa[config["default_tce_index"], ffa_period(period)], config["default_tce_index"], None
        route = config["index_routes"][name]
        rate = ffa[route["ffa_route"], ffa_period(period)]
        v = voyage(cargoes[route["anchor_cargo"]], period)
        return (rate * v["net_tonnes"] - v["bunkers"] - v["ports"]) / v["days"], route["ffa_route"], rate

    quotes = {}
    for cargo in tables["market_cargoes"]:
        period = cargo["laycan_start_utc"][:7]
        tce, source, route_rate = target_tce(cargo, period)
        v = voyage(cargo, period)
        exact = (tce * v["days"] + v["bunkers"] + v["ports"]) / v["net_tonnes"]
        quotes[cargo["cargo_id"]] = {
            "rate_usd_per_tonne": _round(exact, config["quote_rounding_usd"]),
            "tce_source": source, "ffa_period": ffa_period(period), "route_rate_usd_per_tonne": route_rate,
            "target_tce_usd_per_day": tce, "benchmark_days": v["days"], "pricing_period": period,
            "c3_usd_per_tonne": ffa["C3_USD_PER_TONNE", ffa_period(period)],
            "c5_usd_per_tonne": ffa["C5_USD_PER_TONNE", ffa_period(period)]}

    fuel_ref = mean((ship["economical_laden_vlsfo_tpd"], ship["economical_ballast_vlsfo_tpd"]))
    mgo_ref = mean((ship["economical_laden_mgo_tpd"], ship["economical_ballast_mgo_tpd"]))
    offers = {}
    for vessel in tables["market_vessels"]:
        period = vessel["available_from_utc"][:7]
        base = ffa[config["hire_index"], ffa_period(period)]
        adjustment = 0.0
        if config["hire_fuel_adjustment"]:
            vlsfo = mean((float(vessel["economical_laden_vlsfo_tpd"]), float(vessel["economical_ballast_vlsfo_tpd"])))
            mgo = mean((float(vessel["economical_laden_mgo_tpd"]), float(vessel["economical_ballast_mgo_tpd"])))
            adjustment = ((fuel_ref - vlsfo) * prices[period, FUEL_REFERENCE_PORT, "VLSFO"]
                          + (mgo_ref - mgo) * prices[period, FUEL_REFERENCE_PORT, "MGO"])
        offers[vessel["vessel_id"]] = {
            "hire_usd_per_day": _round(base + adjustment, config["hire_rounding_usd"]),
            "index_usd_per_day": base, "fuel_adjustment_usd_per_day": adjustment,
            "ffa_period": ffa_period(period), "delivery_month": period}
    return {"quotes": quotes, "offers": offers, "reference_vessel": ship}


def priced_vessel(row):
    """A market vessel row with its assumed hire filled in; managed rows pass through."""
    offer = market_rates()["offers"].get(row["vessel_id"])
    return {**row, "hire_rate_usd_per_day": str(offer["hire_usd_per_day"])} if offer else row


def priced_cargo(row):
    """A market cargo row with its assumed freight quote filled in; committed rows pass through."""
    quote = market_rates()["quotes"].get(row["cargo_id"])
    return {**row, "contract_freight_rate_usd_per_tonne": str(quote["rate_usd_per_tonne"])} if quote else row


def offer_table():
    rates = market_rates()
    return [{"Vessel": vid, "Delivery month": o["delivery_month"], "5TC index (USD/day)": f'{o["index_usd_per_day"]:,.0f}',
             "Fuel adjustment (USD/day)": f'{o["fuel_adjustment_usd_per_day"]:+,.0f}',
             "Assumed hire (USD/day)": f'{o["hire_usd_per_day"]:,.0f}'} for vid, o in rates["offers"].items()]


def quote_table():
    names = {"5TC_USD_PER_DAY": "5TC average", "C5_USD_PER_TONNE": "C5 route", "C3_USD_PER_TONNE": "C3 route"}
    return [{"Cargo": cid, "Laycan month": q["pricing_period"], "Target TCE from": names.get(q["tce_source"], q["tce_source"]),
             "Target TCE (USD/day)": f'{q["target_tce_usd_per_day"]:,.0f}',
             "Benchmark voyage days": f'{q["benchmark_days"]:.1f}',
             "Assumed freight (USD/t)": f'{q["rate_usd_per_tonne"]:.2f}',
             "vs C3": f'{q["rate_usd_per_tonne"] / q["c3_usd_per_tonne"]:.2f}×',
             "vs C5": f'{q["rate_usd_per_tonne"] / q["c5_usd_per_tonne"]:.2f}×'} for cid, q in market_rates()["quotes"].items()]



@lru_cache(maxsize=1)
def all_vessels():
    """Managed and market vessels by id; market rows carry the assumed hire."""
    tables = load_tables()
    return index(tables["managed_vessels"] + [priced_vessel(v) for v in tables["market_vessels"]], "vessel_id")


@lru_cache(maxsize=1)
def all_cargoes():
    """Committed and market cargoes by id; market rows carry the assumed freight."""
    tables = load_tables()
    return index(tables["committed_cargoes"] + [priced_cargo(c) for c in tables["market_cargoes"]], "cargo_id")
