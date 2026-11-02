import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from voyage.dashboard_data import candidates_case, _reference_period


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
        self.assertEqual(cc["feasible_count"], 2)
        best, runner = cc["rows"][0], cc["rows"][1]
        self.assertAlmostEqual(cc["lead"]["usd"], best["voyage_contribution_usd"] - runner["voyage_contribution_usd"])
        self.assertEqual(cc["baltic"]["route"], "C5")
        self.assertEqual(cc["baltic"]["usd_per_tonne"], 9.05)
        self.assertEqual(cc["bunker_prices"], {"VLSFO": 499.0, "MGO": 664.0})
        self.assertIsNone(candidates_case("CC-01", 178000, "2026-03")["baltic"])
        none = candidates_case("CC-01", 178000, "2026-03")
        self.assertIsNone(none["best"])
        self.assertIsNone(none["lead"])

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
        for text in ("$21,612/day", "$186,749", "+2.78 d", "Laycan missed", "Baltic C5", "+$44,987"):
            self.assertIn(text, body)
        self.assertIn("Focused: MF-02 (top ranked) · top 3 of 4 on map", body)

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
        self.assertIn("No managed vessel is feasible at this lift", body)
        self.assertIn("Economics hypothetical", body)
        app.radio(key="voyage_filter").set_value("feasible").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("No managed vessel passes" in c.value for c in app.caption))


class SearchTests(unittest.TestCase):
    def test_search_matches_every_word_across_fields(self):
        from voyage.search import search
        labels = lambda q: [r["id"] for r in search(q)]
        self.assertEqual(labels("brazil"), ["BRIGI", "CC-03"])
        self.assertEqual(labels("cc-02"), ["CC-02"])
        self.assertEqual(labels("principal-03"), ["CC-03"])  # charterer is searchable, not shown
        self.assertEqual(labels("hedland ore"), ["AUPHE", "CC-02"])
        self.assertEqual(labels("zzz"), [])
        self.assertEqual(len(search("")), 6)

    def test_pick_port_with_one_cargo_selects_it_at_nominal_lift(self):
        app = open_voyages()
        app.selectbox(key="voyage_search").set_value("port:AUPHE").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.selected_cargo, "CC-02")
        self.assertEqual(app.session_state.selected_lift, 164000)
        self.assertEqual(app.selectbox(key="voyage_search").value, "port:AUPHE")
        self.assertIn("$186,749", html(app))

    def test_free_text_search_lists_results_and_opens_one(self):
        app = open_voyages()
        app.session_state.voyage_query = "iron"  # what Enter on free text stores (see test below)
        app.run()
        self.assertFalse(app.exception)
        self.assertIn('Results for &quot;iron&quot;', html(app))
        self.assertEqual(sorted(b.key for b in app.button if b.key and b.key.startswith("open_")),
                         ["open_cargo_CC-02", "open_cargo_CC-03", "open_port_AUPHE", "open_port_BRIGI"])
        app.button(key="open_cargo_CC-03").click().run()
        self.assertEqual((app.session_state.selected_cargo, app.session_state.selected_lift), ("CC-03", 177000))
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
                             ["open_cargo_CC-02", "open_cargo_CC-09"])

    def test_map_shows_top_three_plus_a_lower_selected_vessel(self):
        app = open_voyages()
        app.selectbox(key="voyage_search").set_value("cargo:CC-02").run()
        self.assertIn("top 3 of 4 on map", html(app))
        app.button(key="pick_MF-03").click().run()
        self.assertFalse(app.exception)
        self.assertNotIn("on map", html(app))

    def test_top_bar_cargo_change_ends_a_search(self):
        app = open_voyages()
        app.session_state.voyage_query = "iron"
        app.run()
        app.selectbox(key="selected_cargo").set_value("CC-01").run()
        self.assertIsNone(app.session_state.voyage_query)
        self.assertNotIn('Results for &quot;iron&quot;', html(app))
