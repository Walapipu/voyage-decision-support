import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from voyage.chat_view import selection_from_prompt
from voyage.data import index, load_tables
from voyage.plan import TIGHT_SLACK_DAYS, build_plan
from voyage.search import fuzzy_score

APP = str(Path(__file__).resolve().parents[1] / "app.py")
EMPTY = {"selected_vessel": None, "selected_cargo": None, "selected_lift": None, "price_period": "2026-03"}


def html(app):
    return "".join(h.proto.body for h in app.get("html"))


class FuzzySearchTests(unittest.TestCase):
    def test_typos_and_skipped_letters_match(self):
        self.assertGreater(fuzzy_score("rizao", "MF-01 CNRIZ Rizhao"), 0)
        self.assertGreater(fuzzy_score("laem chabng", "MF-02 THLCH Laem Chabang"), 0)
        self.assertGreater(fuzzy_score("mf2", "MF-02 THLCH Laem Chabang"), 0)

    def test_unrelated_words_do_not_match(self):
        self.assertEqual(fuzzy_score("kandla", "MF-01 CNRIZ Rizhao"), 0)
        self.assertEqual(fuzzy_score("mf2", "MF-01 CNRIZ Rizhao"), 0)


class PromptSelectionTests(unittest.TestCase):
    def test_reads_cargo_lift_and_month(self):
        found = selection_from_prompt("Compare CC-02 at 164,000 t in Mar 2026", EMPTY)
        self.assertEqual((found["selected_cargo"], found["selected_lift"], found["price_period"]), ("CC-02", 164000.0, "2026-03"))
        self.assertEqual(found["selected_vessel"], "MF-02")  # the engine's top feasible candidate

    def test_reads_vessel_and_shorthand_lift(self):
        found = selection_from_prompt("how does MF-03 do on cc 3 with 170k tonnes in April", EMPTY)
        self.assertEqual((found["selected_vessel"], found["selected_cargo"], found["selected_lift"], found["price_period"]),
                         ("MF-03", "CC-03", 170000.0, "2026-04"))

    def test_ignores_conceptual_questions_and_false_months(self):
        self.assertIsNone(selection_from_prompt("What is TCE?", EMPTY))
        self.assertNotIn("price_period", selection_from_prompt("may I see CC-01 margin", EMPTY))


class PlanTests(unittest.TestCase):
    def test_plan_covers_committed_cargoes_with_feasible_engine_voyages(self):
        plan = build_plan("2026-03")
        tables = load_tables()
        cargoes = index(tables["committed_cargoes"] + tables["market_cargoes"], "cargo_id")
        self.assertEqual(plan["uncovered"], [])
        self.assertTrue({"CC-01", "CC-02", "CC-03"} <= {v["cargo_id"] for v in plan["voyages"]})
        self.assertEqual(len({v["vessel_id"] for v in plan["voyages"]}), len(plan["voyages"]))
        self.assertEqual(len({v["cargo_id"] for v in plan["voyages"]}), len(plan["voyages"]))
        for v in plan["voyages"]:
            if not v["owned"]:
                self.assertTrue(v["cargo_id"].startswith("CC"), "market vessels only cover committed cargoes")
            self.assertTrue(v["row"]["feasible"], v["vessel_id"])
            cargo = cargoes[v["cargo_id"]]
            self.assertLessEqual(float(cargo["minimum_quantity_tonnes"]), v["lift"])
            self.assertLessEqual(v["lift"], float(cargo["maximum_quantity_tonnes"]))
            self.assertEqual(v["tight"], v["slack"] < TIGHT_SLACK_DAYS)
        self.assertAlmostEqual(plan["contribution"], sum(v["row"]["voyage_contribution_usd"] for v in plan["voyages"]))

    def test_availability_is_ordered_and_lists_every_owned_vessel(self):
        plan = build_plan("2026-03")
        frees = [a["free"] for a in plan["availability"]]
        self.assertEqual(frees, sorted(frees))
        self.assertEqual({a["vessel_id"] for a in plan["availability"]}, {"MF-01", "MF-02", "MF-03", "MF-04"})


class OverviewTests(unittest.TestCase):
    def test_overview_shows_plan_kpis_and_closed_drawer(self):
        app = AppTest.from_file(APP).run()
        self.assertFalse(app.exception)
        plan = build_plan("2026-03")
        body = html(app)
        for text in ("Portfolio contribution", "Avg TCE", "Committed cargoes covered", "Bunker cost", "Tightest laycan slack",
                     "Fleet timeline", "Next availability", "Chartered redelivery", "Alternatives",
                     "Ask Shippy", "Whole plan"):
            self.assertIn(text, body)
        self.assertIn(f'${plan["voyages"][0]["contribution"]:,.0f}', body)
        self.assertIn("data-shippy-open", body)

    def test_plan_row_focuses_voyage_and_second_click_returns_to_whole_plan(self):
        app = AppTest.from_file(APP).run()
        voyage = build_plan("2026-03")["voyages"][0]
        key = f'plan_pick_{voyage["vessel_id"]}'
        app.button(key=key).click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.plan_focus, (voyage["vessel_id"], voyage["cargo_id"]))
        self.assertEqual(app.session_state.map_view, "Selected")
        body = html(app)
        self.assertIn("plan-row picked", body)
        self.assertIn("tl-row picked", body)
        app.button(key=key).click().run()
        self.assertIsNone(app.session_state.plan_focus)
        self.assertIn("Whole plan", html(app))

    def test_every_plan_row_sets_the_top_bar(self):
        from voyage.overview import focus_row
        state = {}
        with patch("voyage.overview.st") as st:
            st.session_state = type("S", (dict,), {"__getattr__": dict.get, "__setattr__": dict.__setitem__})(state)
            focus_row("MF-02", "CC-02", 171200.0)
            self.assertEqual((st.session_state.selected_vessel, st.session_state.selected_lift), ("MF-02", 171200.0))
            focus_row("MV-04", "MC-01", 171700.0)
            self.assertEqual(st.session_state.plan_focus, ("MV-04", "MC-01"))
            self.assertEqual((st.session_state.selected_vessel, st.session_state.selected_cargo), ("MV-04", "MC-01"))

    def test_alternatives_toggle_and_chartered_redelivery(self):
        app = AppTest.from_file(APP).run()
        app.session_state.plan_view = "Alternatives"
        app.run()
        self.assertFalse(app.exception)
        self.assertIn("Cost of dropping each pairing", html(app))
        app.button(key="alt_pick_MF-03").click().run()
        self.assertIn("Other uses of MF-03", html(app))
        app.button(key="alt_clear").click().run()
        self.assertIsNone(app.session_state.plan_focus)
        self.assertFalse(app.exception)
        body = html(app)
        self.assertIn("Next availability", body)
        self.assertIn("Chartered redelivery", body)

    def test_selection_survives_pages_without_selectors(self):
        app = AppTest.from_file(APP).run()
        nav = lambda page: next(r for r in app.radio if r.label == "Navigation").set_value(page).run()
        nav("Voyages")
        app.selectbox(key="selected_vessel").set_value("MF-01").run()
        nav("Overview")
        nav("Voyages")
        self.assertEqual(app.selectbox(key="selected_vessel").value, "MF-01")

    def test_typed_question_focuses_the_plan_even_when_the_model_fails(self):
        app = AppTest.from_file(APP).run()
        with patch("voyage.chat.chat_reply", side_effect=ValueError("No model reply was returned.")):
            app.chat_input[0].set_value("Compare CC-02 at 164,000 t in Mar 2026").run()
        self.assertFalse(app.exception)
        self.assertEqual((app.session_state.selected_vessel, app.session_state.selected_cargo), ("MF-02", "CC-02"))

    def test_suggestion_asks_and_compact_answer_opens_voyages(self):
        from voyage.tools import execute_tool
        result = execute_tool("compare_vessels", '{"cargo_id":"CC-02","lift_tonnes":164000,"period":"2026-03"}')
        app = AppTest.from_file(APP).run()
        question = app.button(key="suggest_1").label
        with patch("voyage.chat.chat_reply", return_value={"content": "Here are the options.",
                                                            "evidence": [{"tool": "compare_vessels", "result": result}]}) as chat:
            app.button(key="suggest_1").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(chat.call_args.args[0][-1]["content"], question)
        self.assertIn("Recommended plan from the voyage engine", chat.call_args.args[0][-2]["content"])
        self.assertIn("answer-table", html(app))
        self.assertFalse(app.get("plotly_chart"))  # drawer answers stay compact
        app.button(key="reply_1_0_open").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.page, "Voyages")
        self.assertEqual(app.selectbox(key="selected_cargo").value, "CC-02")


if __name__ == "__main__":
    unittest.main()
