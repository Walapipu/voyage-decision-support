import unittest
from datetime import datetime
from voyage.dashboard_data import dashboard_case


class DashboardTests(unittest.TestCase):
    def test_selected_case_costs_margin_and_schedule_reconcile(self):
        case = dashboard_case("CC-02", 164000, "2026-03", "MF-02")
        r = case["row"]
        self.assertAlmostEqual(case["total_cost_usd"] + r["voyage_contribution_usd"], r["freight_revenue_usd"], places=6)
        self.assertAlmostEqual(case["margin_pct"], r["voyage_contribution_usd"] / r["freight_revenue_usd"] * 100)
        start = datetime.fromisoformat(case["timeline"][0]["time"])
        finish = datetime.fromisoformat(case["timeline"][-1]["time"])
        self.assertAlmostEqual((finish-start).total_seconds()/86400, r["voyage_days"], places=7)
        self.assertEqual(case["feasible_count"], 0)
        self.assertEqual(r["fuel_status"], "replenishment plan required")
        self.assertLess(datetime.fromisoformat(case["discharge_eta"]), finish)

    def test_controls_change_all_selected_metrics(self):
        a = dashboard_case("CC-02", 164000, "2026-03", "MF-01")
        b = dashboard_case("CC-02", 164000, "2026-03", "MF-02")
        self.assertNotEqual(a["row"]["bunker_cost_usd"], b["row"]["bunker_cost_usd"])
        self.assertNotEqual(a["timeline"], b["timeline"])
        self.assertFalse(dashboard_case("CC-01", 178000, "2026-03", "MF-01")["row"]["feasible"])
