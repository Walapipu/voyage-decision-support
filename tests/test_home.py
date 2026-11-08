import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from voyage.chat_view import selection_from_prompt
from voyage.dashboard_data import tce_matrix
from voyage.search import fuzzy_score

APP = str(Path(__file__).resolve().parents[1] / "app.py")
EMPTY = {"selected_vessel": None, "selected_cargo": None, "selected_lift": None, "price_period": "2026-03"}


class FuzzySearchTests(unittest.TestCase):
    def test_typos_and_skipped_letters_match(self):
        self.assertGreater(fuzzy_score("rizao", "MF-01 CNRIZ Rizhao"), 0)
        self.assertGreater(fuzzy_score("laem chabng", "MF-02 THLCH Laem Chabang"), 0)
        self.assertGreater(fuzzy_score("mf2", "MF-02 THLCH Laem Chabang"), 0)
        self.assertGreater(fuzzy_score("rotterdm", "MV-03 NLRTM Rotterdam"), 0)

    def test_unrelated_words_do_not_match(self):
        self.assertEqual(fuzzy_score("kandla", "MF-01 CNRIZ Rizhao"), 0)
        self.assertEqual(fuzzy_score("mf2", "MF-01 CNRIZ Rizhao"), 0)
        self.assertEqual(fuzzy_score("rizhao xyz", "MF-01 CNRIZ Rizhao"), 0)

    def test_exact_match_ranks_above_fuzzy(self):
        self.assertGreater(fuzzy_score("rizhao", "Rizhao"), fuzzy_score("rizao", "Rizhao"))


class PromptSelectionTests(unittest.TestCase):
    def test_reads_cargo_lift_and_month(self):
        found = selection_from_prompt("Compare CC-02 at 164,000 t in Mar 2026", EMPTY)
        self.assertEqual((found["selected_cargo"], found["selected_lift"], found["price_period"]), ("CC-02", 164000.0, "2026-03"))
        self.assertEqual(found["selected_vessel"], "MF-02")  # the engine's top feasible candidate

    def test_reads_vessel_and_shorthand_lift(self):
        found = selection_from_prompt("how does MF-03 do on cc 3 with 170k tonnes in April", EMPTY)
        self.assertEqual((found["selected_vessel"], found["selected_cargo"], found["selected_lift"], found["price_period"]),
                         ("MF-03", "CC-03", 170000.0, "2026-04"))

    def test_follow_up_keeps_current_cargo(self):
        state = {**EMPTY, "selected_cargo": "CC-02", "selected_lift": 164000.0, "selected_vessel": "MF-02"}
        found = selection_from_prompt("what about 150,000 tonnes", state)
        self.assertEqual((found["selected_cargo"], found["selected_lift"]), ("CC-02", 150000.0))

    def test_ignores_conceptual_questions_and_false_months(self):
        self.assertIsNone(selection_from_prompt("What is TCE?", EMPTY))
        self.assertNotIn("price_period", selection_from_prompt("may I see CC-01 margin", EMPTY))


class HomeTests(unittest.TestCase):
    def test_heat_map_covers_every_vessel_and_cargo(self):
        matrix = tce_matrix("2026-03")
        self.assertEqual(len(matrix["columns"]), 3)
        for column in matrix["columns"]:
            self.assertEqual(set(column["rows"]), set(matrix["vessels"]))

    def test_typed_question_updates_kpis_even_when_the_model_fails(self):
        app = AppTest.from_file(APP).run()
        with patch("voyage.chat.chat_reply", side_effect=ValueError("No model reply was returned.")):
            app.chat_input[0].set_value("Compare CC-02 at 164,000 t in Mar 2026").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="selected_cargo").value, "CC-02")
        self.assertEqual(app.number_input(key="selected_lift").value, 164000)
        self.assertTrue(any("$453,201" in h.proto.body for h in app.get("html")))
        self.assertTrue(any("heat-pick" in h.proto.body for h in app.get("html")))

    def test_heat_cell_selects_that_voyage(self):
        app = AppTest.from_file(APP).run()
        app.button(key="heat_MF-01_CC-02").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.selectbox(key="selected_vessel").value, "MF-01")
        self.assertEqual(app.selectbox(key="selected_cargo").value, "CC-02")
        self.assertEqual(app.number_input(key="selected_lift").value, 164000)


if __name__ == "__main__":
    unittest.main()
