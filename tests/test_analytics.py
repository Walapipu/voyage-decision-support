import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from voyage import analytics_data as data
from voyage.plan import build_plan

APP = str(Path(__file__).resolve().parents[1] / "app.py")


def html(app):
    return "".join(h.proto.body for h in app.get("html"))


class AnalyticsDataTests(unittest.TestCase):
    def test_grid_covers_every_vessel_and_cargo(self):
        rows = data.grid("2026-03")
        self.assertEqual(len(rows), len(data.vessel_ids()) * len(data.cargo_ids()))

    def test_best_lift_matches_the_overview_plan(self):
        plan = build_plan("2026-03")
        rows = {(r["vessel_id"], r["cargo_id"]): r for r in data.grid("2026-03", "best")}
        for v in plan["voyages"]:
            row = rows[(v["vessel_id"], v["cargo_id"])]
            self.assertTrue(row["feasible"])
            self.assertEqual(row["selected_lift_tonnes"], v["lift"])

    def test_contract_basis_uses_the_contract_quantity(self):
        for r in data.grid("2026-03", "nominal", cargoes=["CC-02"]):
            self.assertEqual(r["selected_lift_tonnes"], 164000)

    def test_filters_and_feasible_only(self):
        rows = data.grid("2026-03", "nominal", vessels=["MF-01", "MF-02"], cargoes=["CC-02"], feasible_only=True)
        self.assertEqual({r["vessel_id"] for r in rows}, {"MF-01", "MF-02"})
        self.assertTrue(all(r["feasible"] for r in rows))

    def test_lift_curve_spans_contract_range(self):
        curve = data.lift_curve("MF-02", "CC-02", "2026-03")
        self.assertEqual((curve[0]["selected_lift_tonnes"], curve[-1]["selected_lift_tonnes"]), (147600, 180400))
        self.assertIn(164000, [r["selected_lift_tonnes"] for r in curve])


class AnalyticsPageTests(unittest.TestCase):
    def open(self):
        app = AppTest.from_file(APP).run()
        next(r for r in app.radio if r.label == "Navigation").set_value("Analytics").run()
        self.assertFalse(app.exception)
        return app

    def test_dashboard_renders_without_a_selection(self):
        app = self.open()
        self.assertIn("Feasible pairings", html(app))
        self.assertGreaterEqual(len(app.get("plotly_chart")), 6)
        self.assertIn("Focus · MF-04 → CC-01", html(app))  # best feasible pairing by contribution

    def test_feasible_only_and_basis_filters(self):
        app = self.open()
        app.pills(key="an_show").set_value("Feasible only").run()
        app.segmented_control(key="an_basis").set_value("nominal").run()
        self.assertFalse(app.exception)
        self.assertIn("2 of 2", html(app))

    def test_strip_selection_sets_the_focus(self):
        app = self.open()
        app.selectbox(key="selected_vessel").set_value("MF-01").run()
        app.selectbox(key="selected_cargo").set_value("CC-02").run()
        self.assertIn("Focus · MF-01 → CC-02", html(app))


if __name__ == "__main__":
    unittest.main()
