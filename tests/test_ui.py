import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from voyage.ranking import rank_cargo
from voyage.data import load_tables


class UITests(unittest.TestCase):
    def test_chat_retry_and_clear_without_network(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        self.assertFalse(app.exception)
        with patch("voyage.chat.chat_reply", side_effect=ValueError("Free quota reached")):
            app.chat_input[0].set_value("What is TCE?").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.error[0].value, "Free quota reached")
        with patch("voyage.chat.chat_reply", return_value={"content": "TCE is daily voyage earnings before hire.", "model": "test", "truncated": False, "evidence": []}) as chat:
            next(b for b in app.button if b.label == "Retry question").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(chat.call_count, 1)
        self.assertEqual(len(app.chat_message), 2)
        app.button(key="new_conversation").click().run()
        self.assertEqual(len(app.chat_message), 0)

    def test_dashboard_selection_theme_and_navigation(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        self.assertEqual(app.selectbox(key="price_period").value, "2026-03")
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state.dark_mode)
        app.button(key="theme_button").click().run()
        self.assertFalse(app.session_state.dark_mode)
        app.selectbox(key="selected_cargo").set_value("CC-01").run()
        pick = rank_cargo("CC-01")["recommendation"]
        self.assertEqual(app.number_input(key="selected_lift").value, int(pick["recommended_tonnes"]))
        self.assertEqual(app.selectbox(key="selected_vessel").value, pick["recommended_vessel"])
        next(r for r in app.radio if r.label == "Navigation").set_value("Voyages").run()
        self.assertFalse(app.exception)
        next(r for r in app.radio if r.label == "Navigation").set_value("Analytics").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("threshold" in w.value for w in app.warning))

    def test_vessel_name_selection_and_all_workspace_pages(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        self.assertEqual(app.button(key="inspect_MF-01").label, "MF-01")
        app.button(key="inspect_MF-01").click().run()
        self.assertEqual(app.selectbox(key="selected_vessel").value, "MF-01")
        self.assertFalse(any(b.label.startswith("Inspect ") for b in app.button))
        for page in ["AI Assistant", "Voyages", "Fleet", "Freight", "Ports", "Analytics", "Reports", "Documents", "Settings"]:
            next(r for r in app.radio if r.label == "Navigation").set_value(page).run()
            self.assertFalse(app.exception, page)

    def test_profile_and_local_logout(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        next(b for b in app.button if b.label == "Profile settings").click().run()
        self.assertFalse(app.exception)
        next(t for t in app.text_input if t.label == "Display name").set_value("Yi Heng Test")
        next(b for b in app.button if b.label == "Save profile").click().run()
        self.assertEqual(app.session_state.profile_name, "Yi Heng Test")
        next(b for b in app.button if b.label == "Log out").click().run()
        self.assertTrue(app.session_state.logged_out)
        self.assertFalse(app.exception)
        next(b for b in app.button if b.label == "Start new session").click().run()
        self.assertFalse(app.session_state.logged_out)
        self.assertFalse(app.exception)

    def test_ranking_cards_and_quantity_selection(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        pick = rank_cargo("CC-02")["recommendation"]
        self.assertEqual(pick["recommended_tonnes"], 170600)
        self.assertEqual(app.number_input(key="selected_lift").value, 170600)
        next(r for r in app.radio if r.label == "Navigation").set_value("Voyages").run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.dataframe), 0)
        self.assertEqual([tab.label for tab in app.tabs], ["Cargo ranking", "Selected voyage details"])
        app.number_input(key="selected_lift").set_value(164000).run()
        self.assertEqual(app.number_input(key="selected_lift").value, 164000)
        app.button(key="restore_optimal_quantity").click().run()
        self.assertEqual(app.number_input(key="selected_lift").value, 170600)
        alternative = rank_cargo("CC-02")["best_per_vessel"][1]
        app.button(key="use_ranked_" + alternative["vessel_id"]).click().run()
        self.assertEqual(app.selectbox(key="selected_vessel").value, alternative["vessel_id"])
        self.assertEqual(app.number_input(key="selected_lift").value, int(alternative["recommended_tonnes"]))
        app.number_input(key="ranking_step").set_value(500).run()
        refreshed = rank_cargo("CC-02", quantity_step=500)["recommendation"]
        self.assertEqual(app.number_input(key="selected_lift").value, int(refreshed["recommended_tonnes"]))
        self.assertFalse(app.exception)

    def test_manual_tonnes_updates_ranking_and_flags_range(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        next(r for r in app.radio if r.label == "Navigation").set_value("Voyages").run()
        app.number_input(key="selected_lift").set_value(160500).run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.ranking_quantity_mode, 'selected')
        self.assertTrue(any('160,500 tonnes' in item.value for item in app.get('html')))
        fixed = rank_cargo('CC-02', lift_tonnes=160500)
        self.assertEqual(len([b for b in app.button if b.key and b.key.startswith('use_ranked_')]), len(fixed['best_per_vessel']))
        app.number_input(key='ranking_bunker').set_value(30.).run()
        self.assertEqual(app.number_input(key='selected_lift').value, 160500)
        next(r for r in app.radio if r.label == 'Navigation').set_value('Dashboard').run()
        next(r for r in app.radio if r.label == 'Navigation').set_value('Voyages').run()
        self.assertEqual(app.number_input(key='selected_lift').value, 160500)
        cargo = next(c for c in load_tables()['committed_cargoes'] if c['cargo_id'] == 'CC-02')
        for quantity in (int(cargo['minimum_quantity_tonnes']) - 1, int(cargo['maximum_quantity_tonnes']) + 1):
            app.number_input(key='selected_lift').set_value(quantity).run()
            self.assertFalse(app.exception)
            self.assertTrue(any('outside accepted range' in e.value for e in app.error))
            self.assertFalse(any(b.key and b.key.startswith('use_ranked_') for b in app.button))
        app.button(key='restore_optimal_quantity').click().run()
        self.assertEqual(app.number_input(key='selected_lift').value, 170600)
        self.assertFalse(app.error)
        app.number_input(key='selected_lift').set_value(160500).run()
        app.selectbox(key='selected_cargo').set_value('CC-01').run()
        self.assertEqual(app.session_state.ranking_quantity_mode, 'optimal')
        self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
