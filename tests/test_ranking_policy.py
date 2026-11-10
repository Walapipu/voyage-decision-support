"""Checks ported from test_ranking_policy_updated.py, against the repo engine."""
import unittest
from copy import deepcopy
from decimal import Decimal as D
from unittest.mock import patch

from voyage.data import load_tables
from voyage.decision import compare_vessels, ranking_evidence
from voyage.engine import calculate, VoyageScenario


def row(vessel, contribution, tce, days, slack, margin=0.5, stress=None):
    return dict(vessel_id=vessel, selected_lift_tonnes=170000.0, speed="economical",
                voyage_contribution_usd=contribution, tce_usd_per_day=tce, voyage_days=days,
                laycan_slack_days=slack, required_summer_draft_margin_m=0.30,
                limiting_draft_margin_m=margin, stress_feasible=True,
                stress_contribution_usd=contribution if stress is None else stress)


class RankingPolicyTests(unittest.TestCase):
    def test_extra_ballast_is_absorbed_by_laycan_waiting(self):
        tables = deepcopy(load_tables())
        tables["managed_vessels"][0]["available_from_utc"] = "2026-02-20T00:00:00Z"
        with patch("voyage.engine.load_tables", return_value=tables):
            base = calculate("MF-01", "CC-02", 164000)
            longer = calculate("MF-01", "CC-02", 164000, scenario=VoyageScenario(additional_ballast_nm=1000))
        self.assertGreater(base["laycan_wait_days"], longer["laycan_wait_days"])
        self.assertGreater(longer["laycan_wait_days"], 0)
        self.assertAlmostEqual(longer["voyage_days"], base["voyage_days"], places=12)
        # Waiting fuel is counted once, at the idle rate, inside the engine.
        idle = D(tables["managed_vessels"][0]["port_idle_vlsfo_tpd"])
        wait_stage = next(x for x in base["fuel_ledger"]
                          if x["stage"] == "Waiting at load port" and x["fuel_grade"] == "VLSFO")
        self.assertEqual(wait_stage["consumed_tonnes"], base["laycan_wait_days"] * idle)

    def test_dominance_needs_every_metric_no_worse_and_one_better(self):
        winner = row("MF-01", 120, 20, 12, 3)
        self.assertEqual(ranking_evidence([winner, row("MF-02", 100, 20, 13, 2)], "contribution",
                                          {"contribution": "MF-01"})["status"], "Dominant")
        self.assertEqual(ranking_evidence([winner, row("MF-02", 100, 20, 13, 4)], "contribution",
                                          {"contribution": "MF-01"})["status"], "Trade-off")
        self.assertFalse(ranking_evidence([winner, dict(winner, vessel_id="MF-02")], "contribution",
                                          {"contribution": "MF-01"})["dominant_vs_runner_up"])

    def test_tight_draft_is_a_qualifier_not_the_status(self):
        tight = ranking_evidence([row("MF-01", 120, 20, 12, 3, margin=0.31), row("MF-02", 100, 20, 13, 2)],
                                 "contribution", {"contribution": "MF-01"})
        self.assertEqual(tight["status"], "Dominant")
        self.assertTrue(tight["draft_limited"])
        self.assertIn("draft-limited", tight["status_display"])
        stressed = ranking_evidence([row("MF-01", 120, 20, 12, 3, stress=-5)], "contribution", {})
        self.assertEqual(stressed["status"], "Scenario-sensitive")

    def test_real_cargo_reports_objective_dependence(self):
        ranking = compare_vessels("CC-01")["ranking"]
        self.assertEqual(ranking["winner"], "MF-01")
        self.assertEqual(ranking["status"], "Objective-dependent")
        self.assertTrue(ranking["draft_limited"])

    def test_every_cargo_and_objective_has_a_recommendation(self):
        for cargo in ("CC-01", "CC-02", "CC-03"):
            for objective in ("contribution", "tce", "stress_contribution"):
                with self.subTest(cargo=cargo, objective=objective):
                    output = compare_vessels(cargo, objective=objective)
                    self.assertIsNotNone(output["ranking"]["winner"])
                    for r in output["rows"]:
                        self.assertGreaterEqual(r["vlsfo_purchase_tonnes"], 0)
                        self.assertEqual(r["stress_feasible"], not r["stress_failed_checks"])


if __name__ == "__main__":
    unittest.main()
