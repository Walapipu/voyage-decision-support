import unittest
from decimal import Decimal

from voyage.data import load_tables
from voyage.engine import calculate
from voyage.decision import compare_vessels
from voyage.tools import execute_tool


class EngineTests(unittest.TestCase):
    def test_supplied_reference_at_published_precision(self):
        tables = load_tables()
        self.assertEqual(len(tables), 13)
        numeric_checks = 0
        for ref in tables["validation_example"]:
            result = calculate(ref["vessel_id"], ref["cargo_id"], ref["selected_lift_tonnes"], ref["bunker_price_period"])
            for key, value in ref.items():
                if key in ("example_id", "result_scope"):
                    continue
                with self.subTest(metric=key):
                    if isinstance(result[key], Decimal):
                        expected = Decimal(value)
                        tolerance = Decimal("0.5") * Decimal(10) ** expected.as_tuple().exponent
                        self.assertLessEqual(abs(result[key] - expected), tolerance)
                        numeric_checks += 1
                    else:
                        self.assertEqual(result[key], value)
        self.assertEqual(numeric_checks, 25)

    def test_comparison_and_feasibility(self):
        result = compare_vessels("CC-02", 164000)
        self.assertEqual([r["vessel_id"] for r in result["rows"] if r["feasible"]], [])
        self.assertEqual(result["rows"][0]["failed_checks"], ["fuel"])
        row = result["rows"][0]
        self.assertAlmostEqual(row["tce_usd_per_day"], 21612.05, places=2)
        self.assertAlmostEqual(row["voyage_contribution_usd"], 186748.50, places=2)
        self.assertFalse(calculate("MF-01", "CC-01", 178000)["draft_pass"])

    def test_missing_quotes_and_invalid_inputs_not_zeroed(self):
        for args in [("MV-01", "CC-02", 164000), ("MF-01", "MC-01", 164000), ("MF-01", "CC-02", "NaN"), ("MF-01", "CC-02", -1)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                calculate(*args)

    def test_tool_boundary(self):
        self.assertIn("error", execute_tool("exec", '{}'))
        self.assertIn("error", execute_tool("calculate_voyage", '{"vessel_id":"MF-01"}'))
        self.assertIn("error", execute_tool("calculate_voyage", '{"lift_tonnes":NaN}'))
        self.assertIn("error", execute_tool("compare_vessels", '{"cargo_id":"CC-02","lift_tonnes":true}'))


if __name__ == "__main__":
    unittest.main()
