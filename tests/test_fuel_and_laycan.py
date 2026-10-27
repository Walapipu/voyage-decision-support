import json
import unittest
from copy import deepcopy
from decimal import Decimal as D
from unittest.mock import patch

from voyage.data import load_tables
from voyage.decision import evaluate_voyage, compare_vessels
from voyage.engine import calculate
from voyage.fuel import audit_fuel
from voyage.briefing import calculated_briefing


class FuelAndLaycanTests(unittest.TestCase):
    def test_check01_shortage_is_not_cured_by_purchase_requirement(self):
        row = calculate("MF-01", "CC-02", 164000)
        first = row["fuel_first_shortfalls"][0]
        self.assertEqual(first["stage"], "Ballast passage")
        self.assertAlmostEqual(float(first["shortfall_tonnes"]), 20.829365079, places=6)
        self.assertLess(first["depleted_after_days"], row["ballast_days"])
        self.assertGreater(row["vlsfo_purchase_tonnes"], first["shortfall_tonnes"])
        self.assertFalse(row["fuel_pass"])
        for grade, metric in [("VLSFO", "vlsfo_consumption_tonnes"), ("MGO", "mgo_consumption_tonnes")]:
            self.assertAlmostEqual(float(sum(x["consumed_tonnes"] for x in row["fuel_ledger"] if x["fuel_grade"] == grade)), float(row[metric]), places=9)
        output = evaluate_voyage("MF-01", "CC-02", 164000)
        json.dumps(output, allow_nan=False)
        self.assertFalse(output["rows"][0]["feasible"])

    def test_each_stage_and_grade_can_independently_exhaust(self):
        stages = ["Ballast passage", "Waiting at load port", "Loading", "Laden passage", "Discharge"]
        for grade in ("VLSFO", "MGO"):
            for target in range(len(stages)):
                with self.subTest(grade=grade, stage=stages[target]):
                    opening = {"VLSFO": 100, "MGO": 100}
                    opening[grade] = D(target) + D("0.5")
                    result = audit_fuel(opening, [(name, 1, {"VLSFO": 1, "MGO": 1}) for name in stages])
                    self.assertFalse(result["fuel_pass"])
                    self.assertEqual(len(result["fuel_first_shortfalls"]), 1)
                    first = result["fuel_first_shortfalls"][0]
                    self.assertEqual(first["fuel_grade"], grade)
                    self.assertEqual(first["stage"], stages[target])
                    self.assertEqual(first["depleted_after_days"], D(target) + D("0.5"))

    def test_zero_inventory_boundary_and_no_cross_grade_offset(self):
        stage = [("Ballast", 2, {"VLSFO": 10, "MGO": 1})]
        self.assertTrue(audit_fuel({"VLSFO": 10, "MGO": 1}, stage)["fuel_pass"])
        self.assertFalse(audit_fuel({"VLSFO": 1000, "MGO": "0.99"}, stage)["fuel_pass"])
        stages = stage + [("Wait", 0, {"VLSFO": 0, "MGO": 0}), ("Laden", 1, {"VLSFO": 1, "MGO": 0})]
        first = audit_fuel({"VLSFO": 10, "MGO": 1}, stages)["fuel_first_shortfalls"][0]
        self.assertEqual(first["stage"], "Laden")
        self.assertEqual(first["depleted_after_days"], 2)

    def test_no_recommendation_when_all_opening_fuel_is_insufficient(self):
        result = compare_vessels("CC-02", 164000)
        self.assertFalse(any(r["feasible"] for r in result["rows"]))
        self.assertTrue(all("fuel" in r["failed_checks"] for r in result["rows"]))
        report = calculated_briefing([{"result": result}], {"assessment": "Proceed immediately."})
        self.assertNotIn("Proceed immediately", report)
        self.assertIn("No fuel deliveries are scheduled", report)

    def test_laycan_closing_boundary_is_hard_exclusion(self):
        # Construct an exact one-day ballast passage; no datetime rounding ambiguity.
        tables = deepcopy(load_tables())
        vessel = tables["managed_vessels"][0]
        vessel["available_from_utc"] = "2026-03-01T00:00:00Z"
        vessel["vlsfo_rob_tonnes"], vessel["mgo_rob_tonnes"] = "5000", "500"
        cargo = next(c for c in tables["committed_cargoes"] if c["cargo_id"] == "CC-02")
        cargo["laycan_start_utc"] = "2026-03-01T00:00:00Z"
        route = next(r for r in tables["ballast_distances"] if r["origin_port"] == vessel["current_port"] and r["destination_port"] == cargo["load_port"])
        route["route_distance_nm"] = str(D(vessel["economical_ballast_speed_knots"]) * 24)
        for closing, expected in [("2026-03-01T23:59:59Z", False), ("2026-03-02T00:00:00Z", True), ("2026-03-02T00:00:01Z", True)]:
            with self.subTest(closing=closing), patch("voyage.engine.load_tables", return_value=tables):
                cargo["laycan_end_utc"] = closing
                row = evaluate_voyage("MF-01", "CC-02", 164000)["rows"][0]
                self.assertEqual(row["laycan_pass"], expected)
                self.assertEqual(row["feasible"], expected)
                self.assertGreater(row["voyage_contribution_usd"], 0)
                if not expected:
                    self.assertIn("laycan", row["failed_checks"])


if __name__ == "__main__":
    unittest.main()
