import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from voyage.commands import mentions, run_command

APP = str(Path(__file__).resolve().parents[1] / "app.py")
EMPTY = {"selected_vessel": None, "selected_cargo": None, "selected_lift": None, "price_period": "2026-03"}


class ShortcutParsingTests(unittest.TestCase):
    def test_reads_compact_ids_shorthand_lift_and_month(self):
        found = mentions("MF01 cc 1 200k tons Apr 2026")
        self.assertEqual(found, {"vessels": ["MF-01"], "cargoes": ["CC-01"], "lift": 200000.0, "period": "2026-04"})

    def test_plain_text_is_not_a_shortcut(self):
        self.assertIsNone(run_command("Compare CC-02", EMPTY))

    def test_voyages_fills_inputs_and_opens_page(self):
        result = run_command("/voyages MF01 CC01 200k tons", EMPTY)
        self.assertEqual(result["page"], "Voyages")
        self.assertEqual(result["selection"], {"selected_vessel": "MF-01", "selected_cargo": "CC-01",
                                               "selected_lift": 200000.0, "price_period": "2026-03"})

    def test_new_cargo_without_lift_uses_contract_quantity(self):
        self.assertEqual(run_command("/voyages cc2", EMPTY)["selection"]["selected_lift"], 164000.0)

    def test_compare_cargo_ranks_the_fleet(self):
        result = run_command("/compare CC-02", EMPTY)
        rows = result["evidence"][0]["result"]["rows"]
        self.assertEqual(result["evidence"][0]["tool"], "compare_vessels")
        self.assertEqual(len(rows), 4)
        self.assertEqual(result["selection"]["selected_vessel"], rows[0]["vessel_id"])
        self.assertIn("2 of 4 feasible", result["reply"])

    def test_compare_vessel_runs_it_across_every_cargo(self):
        result = run_command("/compare mf 01", EMPTY)
        rows = result["evidence"][0]["result"]["rows"]
        self.assertEqual(result["evidence"][0]["tool"], "compare_cargoes")
        self.assertEqual({r["cargo_id"] for r in rows}, {"CC-01", "CC-02", "CC-03"})
        self.assertEqual({r["vessel_id"] for r in rows}, {"MF-01"})

    def test_compare_named_vessels_keeps_only_them(self):
        rows = run_command("/compare mf1 mf3 cc1", EMPTY)["evidence"][0]["result"]["rows"]
        self.assertEqual({r["vessel_id"] for r in rows}, {"MF-01", "MF-03"})

    def test_unknown_and_empty_shortcuts_explain_usage(self):
        self.assertIn("not a shortcut", run_command("/foo", EMPTY)["reply"])
        self.assertIn("/compare", run_command("/compare", EMPTY)["reply"])


class ShortcutAppTests(unittest.TestCase):
    def test_voyages_shortcut_switches_page_without_the_model(self):
        app = AppTest.from_file(APP).run()
        with patch("voyage.chat.chat_reply") as model:
            app.chat_input[0].set_value("/voyages MF01 CC01 200k tons").run()
        self.assertFalse(app.exception)
        model.assert_not_called()
        self.assertEqual(app.session_state.page, "Voyages")
        self.assertEqual(app.selectbox(key="selected_cargo").value, "CC-01")
        self.assertEqual(app.number_input(key="selected_lift").value, 200000.0)

    def test_compare_shortcut_answers_in_the_drawer(self):
        app = AppTest.from_file(APP).run()
        app.chat_input[0].set_value("/compare mf 01").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.page, "Overview")
        self.assertIn("MF-01 across 3 committed cargoes", app.session_state.messages[-1]["content"])
        self.assertIn("answer-table", "".join(h.proto.body for h in app.get("html")))



class StylesheetTests(unittest.TestCase):
    def test_stylesheet_has_no_angle_brackets(self):
        # st.html sanitises the injected style block; a "<" anywhere in it drops the whole sheet.
        from voyage.dashboard import _stylesheet
        self.assertNotIn("<", _stylesheet())


if __name__ == "__main__":
    unittest.main()
