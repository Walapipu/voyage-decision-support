import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from voyage.dashboard_data import candidates_case, suggested_lift, _reference_period
from voyage.decision import compare_vessels


def open_voyages():
    app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
    next(r for r in app.radio if r.label == "Navigation").set_value("Voyages").run()
    return app


def html(app):
    return " ".join(h.proto.body for h in app.get("html"))


class VoyagesTests(unittest.TestCase):
    def test_candidates_rank_lead_and_market_context(self):
        cc = candidates_case("CC-02", 164000, "2026-03")
        self.assertEqual([r["vessel_id"] for r in cc["rows"]][:2], ["MF-02", "MF-01"])
        self.assertEqual(cc["feasible_count"], 7)  # chartered market vessels are candidates for a committed cargo
        self.assertEqual(len(cc["rows"]), 15)
        self.assertEqual(len(candidates_case("MC-07", 166000, "2026-03")["rows"]), 4)  # owned fleet only for market cargo
        best, runner = cc["rows"][0], cc["rows"][1]
        self.assertAlmostEqual(cc["lead"]["usd"], best["voyage_contribution_usd"] - runner["voyage_contribution_usd"])
        self.assertEqual(cc["baltic"]["route"], "C5")
        self.assertEqual(cc["baltic"]["usd_per_tonne"], 9.05)
        self.assertEqual(cc["bunker_prices"], {"VLSFO": 499.0, "MGO": 664.0})
        self.assertIsNone(candidates_case("CC-01", 178000, "2026-03")["baltic"])
        none = candidates_case("CC-01", 178000, "2026-03")
        self.assertIsNone(none["best"])
        self.assertIsNone(none["lead"])

    def test_suggested_lift_is_the_winners_best_lift_for_each_rank_method(self):
        for objective in ("contribution", "tce", "stress_contribution"):
            optimised = compare_vessels("CC-01", None, None, objective=objective, include_market=True)
            winner = next(r for r in optimised["rows"] if r["ranking_eligible"])
            lift = suggested_lift("CC-01", None, objective)
            self.assertEqual(lift, winner["selected_lift_tonnes"], objective)
            cc = candidates_case("CC-01", lift, None, objective)
            self.assertEqual(cc["best"]["vessel_id"], winner["vessel_id"], objective)  # still top at its own lift
            self.assertEqual(cc["suggested_lift"], lift)
        self.assertEqual((suggested_lift("CC-01", None, "contribution"), suggested_lift("CC-01", None, "tce")), (169100, 171600))

    def test_per_vessel_case_uses_each_vessels_best_lift(self):
        cc = candidates_case("CC-01", 169100, None, "contribution", per_vessel=True)
        lifts = {r["vessel_id"]: r["selected_lift_tonnes"] for r in cc["rows"]}
        self.assertEqual((lifts["MF-04"], lifts["MF-01"]), (169100, 170600))
        self.assertEqual(cc["best"]["vessel_id"], "MF-04")
        self.assertEqual(cc["feasible_count"], 15)  # at its own best lift every vessel passes; at 169,100 t only 14 do

    def test_rank_method_orders_candidates_by_its_metric(self):
        cc = candidates_case("CC-01", 171600, None, "tce")
        self.assertEqual(cc["objective"]["label"], "TCE before hire")
        ranked = [r["tce_usd_per_day"] for r in cc["rows"] if r["ranking_eligible"]]
        self.assertEqual(ranked, sorted(ranked, reverse=True))
        self.assertAlmostEqual(cc["lead"]["usd"], ranked[0] - ranked[1])

    def test_cargo_alone_shows_ranked_candidates_at_suggested_lift(self):
        app = open_voyages()
        app.selectbox(key="selected_cargo").set_value("CC-01").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.selected_lift, 169100)
        body = html(app)
        self.assertIn("Best per vessel", body)  # suggested lift: each vessel at its own best lift
        self.assertIn("Best lift <span class=\"num\">170,600</span> t", body)  # MF-01's own best, not the winner's
        self.assertIn("Highest contribution after hire", body)
        app.button(key="pick_MF-01").click().run()
        self.assertFalse(app.exception)
        self.assertIn("170,600 tonnes", html(app))  # the selected voyage uses that vessel's best lift
        # A new rank method re-suggests the lift while it is still the suggestion.
        app.selectbox(key="ranking_objective").set_value("tce").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.selected_lift, 171600)
        self.assertIn("Highest TCE before hire", html(app))
        # A typed lift is kept when the rank method changes, and can be reset to the suggestion.
        app.number_input(key="selected_lift").set_value(165000).run()
        app.selectbox(key="ranking_objective").set_value("contribution").run()
        self.assertEqual(app.session_state.selected_lift, 165000)
        body = html(app)
        self.assertNotIn("Best per vessel", body)
        self.assertIn("CC-01 · 165,000 t", body)  # a typed lift applies to every vessel
        app.button(key="use_suggested_lift").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.selected_lift, 169100)

    def test_cleared_lift_is_suggested_again(self):
        app = open_voyages()
        app.selectbox(key="selected_cargo").set_value("CC-02").run()
        app.number_input(key="selected_lift").set_value(None).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.selected_lift, 171200)

    def test_reference_period_falls_back_to_quarter(self):
        available = {"2026-03": 1, "2026-Q2": 1}
        self.assertEqual(_reference_period("2026-03", available), "2026-03")
        self.assertEqual(_reference_period("2026-05", available), "2026-Q2")
        self.assertIsNone(_reference_period("2026-11", available))

    def test_cargo_and_lift_show_candidates_without_a_vessel(self):
        app = open_voyages()
        self.assertIn("Find a voyage", html(app))
        app.selectbox(key="selected_cargo").set_value("CC-02").run()
        app.number_input(key="selected_lift").set_value(164000).run()
        self.assertFalse(app.exception)
        body = html(app)
        for text in ("$21,612/day", "$186,749", "+2.78 days", "Laycan missed", "Baltic C5", "+$44,987"):
            self.assertIn(text, body)
        self.assertIn("Focused: MF-02 (top ranked) · top 3 of 15 on map", body)

    def test_select_vessel_and_feasible_filter(self):
        app = open_voyages()
        app.selectbox(key="selected_cargo").set_value("CC-02").run()
        app.number_input(key="selected_lift").set_value(164000).run()
        app.button(key="pick_MF-01").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="selected_vessel").value, "MF-01")
        self.assertIn("Selected voyage · MF-01", html(app))
        app.radio(key="voyage_filter").set_value("feasible").run()
        self.assertFalse(app.exception)
        self.assertNotIn('class="cand-head"><span class="cand-id"><i class="dot bad"', html(app))
        self.assertFalse([b for b in app.button if b.key == "pick_MF-04"])

    def test_all_infeasible_cargo_renders_hypothetical_cards(self):
        app = open_voyages()
        app.selectbox(key="selected_cargo").set_value("CC-01").run()
        app.number_input(key="selected_lift").set_value(178000).run()
        self.assertFalse(app.exception)
        body = html(app)
        self.assertIn("No vessel is feasible at this lift", body)
        self.assertIn("Economics hypothetical", body)
        app.radio(key="voyage_filter").set_value("feasible").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("No vessel passes" in c.value for c in app.caption))


class SearchTests(unittest.TestCase):
    def test_search_matches_every_word_across_fields(self):
        from voyage.search import search
        labels = lambda q: [r["id"] for r in search(q)]
        self.assertEqual(labels("brazil"), ["BRIGI", "BRPDM", "BRTUB", "CC-03", "MC-02", "MC-08"])
        self.assertEqual(labels("cc-02"), ["CC-02"])
        self.assertEqual(labels("principal-03"), ["CC-03"])  # charterer is searchable, not shown
        self.assertEqual(labels("hedland ore"), ["AUPHE", "CC-02", "MC-07"])
        self.assertEqual(labels("zzz"), [])
        self.assertEqual(len(search("")), 20)  # 9 load ports, 3 committed and 8 market cargoes

    def test_pick_port_with_one_cargo_selects_it_at_suggested_lift(self):
        app = open_voyages()
        app.selectbox(key="voyage_search").set_value("port:BRIGI").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.selected_cargo, "CC-03")
        self.assertEqual(app.session_state.selected_lift, 167800)
        self.assertEqual(app.selectbox(key="voyage_search").value, "port:BRIGI")

    def test_free_text_search_lists_results_and_opens_one(self):
        app = open_voyages()
        app.session_state.voyage_query = "iron"  # what Enter on free text stores (see test below)
        app.run()
        self.assertFalse(app.exception)
        self.assertIn('Results for &quot;iron&quot;', html(app))
        from voyage.search import search
        self.assertEqual(sorted(b.key for b in app.button if b.key and b.key.startswith("open_")),
                         sorted(f'open_{r["kind"]}_{r["id"]}' for r in search("iron")))
        app.button(key="open_cargo_CC-03").click().run()
        self.assertEqual((app.session_state.selected_cargo, app.session_state.selected_lift), ("CC-03", 167800))
        self.assertIsNone(app.session_state.voyage_query)

    def test_enter_on_free_text_runs_server_search(self):
        # AppTest cannot type an unlisted value, so the selectbox callback is driven directly.
        from unittest.mock import patch
        from voyage import voyages_view

        class State(dict):
            __getattr__, __setattr__ = dict.get, dict.__setitem__

        for typed, expected in [("iron", ("query", "iron")), ("principal-02", ("cargo", "CC-02")), ("zzz", ("query", "zzz"))]:
            state = State(voyage_search=typed, voyage_port=None, voyage_query=None, selected_cargo=None, selected_lift=None)
            with patch.object(voyages_view.st, "session_state", state):
                voyages_view._on_search()
            got = ("query", state.voyage_query) if state.voyage_query else ("cargo", state.selected_cargo)
            self.assertEqual(got, expected, typed)
        self.assertEqual(state.selected_lift, None)
        state = State(voyage_search=None, voyage_port=None, voyage_query="iron", selected_cargo="CC-02", selected_lift=164000)
        with patch.object(voyages_view.st, "session_state", state):
            voyages_view._on_search()  # clearing a search keeps the cargo being viewed
        self.assertEqual((state.voyage_query, state.selected_cargo), (None, "CC-02"))

    def test_port_with_several_cargoes_lists_them(self):
        from unittest.mock import patch
        from voyage.data import load_tables
        tables = load_tables()
        extra = dict(next(c for c in tables["committed_cargoes"] if c["cargo_id"] == "CC-02"), cargo_id="CC-09",
                     laycan_start_utc="2026-04-02T00:00:00Z", laycan_end_utc="2026-04-08T00:00:00Z")
        tables["committed_cargoes"].append(extra)
        app = open_voyages()
        with patch("voyage.search.load_tables", return_value=tables), patch("voyage.voyages_view.load_tables", return_value=tables):
            app.selectbox(key="voyage_search").set_value("port:AUPHE").run()
            self.assertFalse(app.exception)
            self.assertIsNone(app.session_state.selected_cargo)
            self.assertIn("Open cargoes at Port Hedland", html(app))
            self.assertEqual(sorted(b.key for b in app.button if b.key and b.key.startswith("open_")),
                             ["open_cargo_CC-02", "open_cargo_CC-09", "open_cargo_MC-07"])

    def test_map_shows_top_three_plus_a_lower_selected_vessel(self):
        app = open_voyages()
        app.selectbox(key="voyage_search").set_value("cargo:CC-02").run()
        self.assertIn("top 3 of 15 on map", html(app))
        app.button(key="pick_MF-03").click().run()
        self.assertFalse(app.exception)
        self.assertIn("Focused: MF-03 · top 3 of 15 on map", html(app))  # the picked vessel is drawn as well

    def test_top_bar_cargo_change_ends_a_search(self):
        app = open_voyages()
        app.session_state.voyage_query = "iron"
        app.run()
        app.selectbox(key="selected_cargo").set_value("CC-01").run()
        self.assertIsNone(app.session_state.voyage_query)
        self.assertNotIn('Results for &quot;iron&quot;', html(app))
