"""The database schema: one table per data-pack file, with the same column names.

This is the data contract. A database the app reads must offer these tables and columns (as
tables, or as views over the company's own tables), and the CSV files in data/raw follow the
same contract. Columns are text so every source hands the engine identical values: the engine
parses numbers as Decimal and timestamps as ISO 8601, exactly as written in the files.
Column meanings are in data/raw/DATA_DICTIONARY.md.

Primary keys mirror the unique keys the loader checks, so the database rejects duplicates too.
Generated from the CSV headers; tests/test_data_sources.py keeps the two in step.
"""
from sqlalchemy import Column, MetaData, Table, Text

metadata = MetaData()


def _table(name, columns, key=()):
    return Table(name, metadata, *(Column(c, Text, primary_key=c in key) for c in columns))


BALLAST_DISTANCES = _table("ballast_distances", [
    "origin_port", "destination_port", "route_distance_nm", "distance_basis",
], key=('origin_port', 'destination_port'))

BUNKER_FORWARD_CURVE = _table("bunker_forward_curve", [
    "period", "pricing_location", "fuel_grade", "price_usd_per_tonne", "curve_status",
], key=('period', 'pricing_location', 'fuel_grade'))

COMMERCIAL_ASSUMPTIONS = _table("commercial_assumptions", [
    "speed_basis", "ballast_days_formula", "laden_days_formula", "arrival_at_load_formula",
    "laycan_wait_formula", "loading_days_formula", "discharge_days_formula",
    "voyage_days_formula", "fuel_scope", "bunker_cost_formula", "bunker_purchase_formula",
    "vlsfo_reserve_tonnes", "mgo_reserve_tonnes", "other_deadweight_tonnes",
    "departure_deadweight_formula", "draft_formula", "minimum_draft_margin_m", "tce_formula",
    "voyage_contribution_formula", "managed_vessel_rule", "market_vessel_rule",
    "committed_cargo_rule", "market_cargo_rule",
])

COMMITTED_CARGOES = _table("committed_cargoes", [
    "cargo_id", "counterparty_id", "commodity", "nominal_quantity_tonnes",
    "quantity_tolerance_fraction", "quantity_option", "load_port", "discharge_port",
    "laycan_start_utc", "laycan_end_utc", "contract_freight_rate_usd_per_tonne",
    "load_rate_tonnes_per_day", "load_turn_time_hours", "discharge_rate_tonnes_per_day",
    "discharge_turn_time_hours", "load_port_cost_usd", "discharge_port_cost_usd",
    "commission_rate", "special_freight_rule", "special_freight_threshold_tonnes",
    "minimum_quantity_tonnes", "maximum_quantity_tonnes", "cargo_role",
], key=('cargo_id',))

FFA_REFERENCE = _table("ffa_reference", [
    "route_code", "period", "reference_value", "unit", "use",
])

LADEN_ROUTES = _table("laden_routes", [
    "cargo_id", "origin_port", "destination_port", "route_distance_nm", "distance_basis",
], key=('cargo_id',))

MANAGED_VESSELS = _table("managed_vessels", [
    "vessel_id", "dwt_tonnes", "ballast_draft_m", "summer_draft_m", "hire_rate_usd_per_day",
    "warranted_laden_speed_knots", "warranted_laden_vlsfo_tpd", "warranted_laden_mgo_tpd",
    "warranted_ballast_speed_knots", "warranted_ballast_vlsfo_tpd",
    "warranted_ballast_mgo_tpd", "economical_laden_speed_knots", "economical_laden_vlsfo_tpd",
    "economical_laden_mgo_tpd", "economical_ballast_speed_knots",
    "economical_ballast_vlsfo_tpd", "economical_ballast_mgo_tpd", "port_idle_vlsfo_tpd",
    "port_working_vlsfo_tpd", "current_port", "available_from_utc", "vlsfo_rob_tonnes",
    "mgo_rob_tonnes", "vessel_class",
], key=('vessel_id',))

MARKET_CARGOES = _table("market_cargoes", [
    "cargo_id", "counterparty_id", "commodity", "nominal_quantity_tonnes",
    "quantity_tolerance_fraction", "quantity_option", "load_port", "discharge_port",
    "laycan_start_utc", "laycan_end_utc", "contract_freight_rate_usd_per_tonne",
    "load_rate_tonnes_per_day", "load_turn_time_hours", "discharge_rate_tonnes_per_day",
    "discharge_turn_time_hours", "load_port_cost_usd", "discharge_port_cost_usd",
    "commission_rate", "special_freight_rule", "special_freight_threshold_tonnes",
    "minimum_quantity_tonnes", "maximum_quantity_tonnes", "cargo_role",
], key=('cargo_id',))

MARKET_VESSELS = _table("market_vessels", [
    "vessel_id", "dwt_tonnes", "ballast_draft_m", "summer_draft_m",
    "warranted_laden_speed_knots", "warranted_laden_vlsfo_tpd", "warranted_laden_mgo_tpd",
    "warranted_ballast_speed_knots", "warranted_ballast_vlsfo_tpd",
    "warranted_ballast_mgo_tpd", "economical_laden_speed_knots", "economical_laden_vlsfo_tpd",
    "economical_laden_mgo_tpd", "economical_ballast_speed_knots",
    "economical_ballast_vlsfo_tpd", "economical_ballast_mgo_tpd", "port_idle_vlsfo_tpd",
    "port_working_vlsfo_tpd", "current_port", "available_from_utc", "vlsfo_rob_tonnes",
    "mgo_rob_tonnes", "vessel_class", "hire_offer_status",
], key=('vessel_id',))

PORTS = _table("ports", [
    "port_code", "port_name", "country", "coursework_max_draft_m", "region",
    "bunker_pricing_location", "draft_reference", "bunker_price_basis",
], key=('port_code',))

SOURCE_REGISTER = _table("source_register", [
    "source_name", "url", "included_as_file", "application", "limitation",
])

VALIDATION_EXAMPLE = _table("validation_example", [
    "example_id", "vessel_id", "cargo_id", "selected_lift_tonnes", "ballast_distance_nm",
    "laden_distance_nm", "ballast_days", "laycan_wait_days", "loading_days", "laden_days",
    "discharge_days", "voyage_days", "vlsfo_consumption_tonnes", "mgo_consumption_tonnes",
    "vlsfo_purchase_tonnes", "mgo_purchase_tonnes", "bunker_price_period",
    "bunker_pricing_location", "bunker_cost_usd", "departure_deadweight_tonnes",
    "deadweight_margin_tonnes", "estimated_sailing_draft_m", "draft_margin_m",
    "freight_revenue_usd", "commission_usd", "port_cost_usd", "voyage_cashflow_usd",
    "tce_usd_per_day", "hire_cost_usd", "voyage_contribution_usd", "result_scope",
])

VESSEL_CLASS_RANGES = _table("vessel_class_ranges", [
    "vessel_class", "minimum_dwt_tonnes", "maximum_dwt_tonnes", "minimum_cargo_tonnes",
    "maximum_cargo_tonnes", "range_use",
])
