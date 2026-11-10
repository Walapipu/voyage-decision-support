import unittest

from voyage.plan import _options, alternatives, build_plan, optimise, what_if


class AllocationTests(unittest.TestCase):
    def test_every_committed_cargo_is_covered_and_owned_ships_take_at_most_one_voyage(self):
        (covered, total), assignment = optimise(None)
        self.assertEqual(covered, 3)
        self.assertEqual(len(set(assignment.values())), len(assignment))
        plan = build_plan(None)
        self.assertAlmostEqual(plan["contribution"], total, places=2)
        self.assertEqual({c["vessel_id"] for c in plan["chartered"]}, {v for v in assignment if v.startswith("MV")})

    def test_plan_beats_or_equals_owned_fleet_only(self):
        options, owned, hired, committed = _options(None)
        no_market = frozenset(p for p in options if p[0] in hired or p[1].startswith("MC"))
        owned_only = optimise(None, exclude=no_market)
        self.assertGreaterEqual(optimise(None)[0][1], owned_only[0][1])

    def test_exhaustive_search_has_no_better_single_change(self):
        base = optimise(None)[0][1]
        options, owned, hired, committed = _options(None)
        for vessel, cargo in options:
            result = what_if(None, vessel, cargo)
            if result["feasible"] and result["covers_all"]:
                self.assertLessEqual(result["delta"], 1e-6, (vessel, cargo))

    def test_dropping_a_pairing_costs_what_the_replan_says(self):
        base = optimise(None)
        for w in alternatives(None)["worth"]:
            other = optimise(None, exclude=frozenset({(w["vessel_id"], w["cargo_id"])}))
            if w["given_up"] is not None:
                self.assertAlmostEqual(w["given_up"], base[0][1] - other[0][1], places=4)
                self.assertGreaterEqual(w["given_up"], -1e-6)

    def test_infeasible_what_if_names_the_failed_check(self):
        result = what_if(None, "MF-03", "MC-02")
        self.assertFalse(result["feasible"])
        self.assertIn("laycan", result["reasons"])

    def test_swaps_cover_every_pair_of_owned_voyages(self):
        alts = alternatives(None)
        owned = [v for v in optimise(None)[1] if v.startswith("MF")]
        self.assertEqual(len(alts["swaps"]), len(owned) * (len(owned) - 1) // 2)
        for swap in alts["swaps"]:
            self.assertIn("delta" if swap["feasible"] else "reasons", swap)


class MarketToolTests(unittest.TestCase):
    def test_shippy_tools_accept_market_vessels_and_cargoes(self):
        from voyage.tools import execute_tool
        spot = execute_tool("compare_vessels", '{"cargo_id":"MC-05"}')
        self.assertNotIn("error", spot)
        self.assertEqual({r["vessel_id"] for r in spot["rows"]}, {"MF-01", "MF-02", "MF-03", "MF-04"})
        hired = execute_tool("compare_vessels", '{"cargo_id":"CC-02","lift_tonnes":164000,"include_market_vessels":true}')
        self.assertEqual(len(hired["rows"]), 15)
        one = execute_tool("calculate_voyage", '{"vessel_id":"MV-04","cargo_id":"CC-02","lift_tonnes":170200}')
        self.assertNotIn("error", one)

    def test_typed_market_ids_are_read(self):
        from voyage.commands import mentions
        found = mentions("compare mv-4 and MF02 on mc 5 at 160kt")
        self.assertEqual((found["vessels"], found["cargoes"], found["lift"]), (["MV-04", "MF-02"], ["MC-05"], 160000.0))


if __name__ == "__main__":
    unittest.main()
