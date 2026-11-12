import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class UITests(unittest.TestCase):
    def test_empty_selection_does_not_calculate_or_block_chat(self):
        with patch('voyage.dashboard_data.dashboard_case') as calculate:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
            self.assertFalse(app.exception)
            for key in ('selected_vessel', 'selected_cargo', 'selected_lift'):
                self.assertIsNone(app.session_state[key])
            self.assertTrue(any('Hello, Yi Heng.' in h.proto.body for h in app.get('html')))
            with patch('voyage.chat.chat_reply', return_value={'content': 'How can I help?', 'evidence': []}) as chat:
                app.chat_input[0].set_value('Hello').run()
            self.assertFalse(app.exception)
            context = chat.call_args.args[0][-2]['content']
            self.assertIn("'selected_vessel': None", context)
            self.assertEqual(len(app.chat_message), 2)
            for page in ('Voyages', 'Analytics', 'Reports', 'Fleet', 'Freight', 'Ports', 'Documents', 'Settings'):
                next(r for r in app.radio if r.label == 'Navigation').set_value(page).run()
                self.assertFalse(app.exception, page)
            self.assertEqual(app.selectbox(key='selected_vessel').options[0], 'Vessel')
            self.assertEqual(app.selectbox(key='selected_cargo').options[0], 'Cargo')
            self.assertEqual(app.number_input(key='selected_lift').proto.placeholder, 'Lift, tonnes')
            calculate.assert_not_called()

    def test_chat_calculation_updates_home_and_keeps_it_through_follow_up(self):
        from voyage.tools import execute_tool
        result = execute_tool("compare_vessels", '{"cargo_id":"CC-02","lift_tonnes":164000.5,"period":"2026-04"}')
        row = result["rows"][0]
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        evidence = [{"tool": "compare_vessels", "result": result}]
        with patch("voyage.chat.chat_reply", return_value={"content": "Comparison ready", "evidence": evidence}):
            app.chat_input[0].set_value("Compare CC-02 at 164000.5 tonnes in April 2026").run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state.selected_vessel, row["vessel_id"])
        self.assertEqual(app.session_state.selected_cargo, "CC-02")
        self.assertEqual(app.selectbox(key="price_period").value, "2026-04")
        self.assertEqual(app.session_state.selected_lift, 164000.5)
        self.assertTrue(any(f'{row["vessel_id"]} → CC-02</span>' in h.proto.body for h in app.get("html")))
        with patch("voyage.chat.chat_reply", return_value={"content": "Conceptual answer", "evidence": []}):
            app.chat_input[0].set_value("What is TCE?").run()
        self.assertEqual(app.session_state.selected_cargo, "CC-02")
        next(r for r in app.radio if r.label == "Navigation").set_value("Voyages").run()
        self.assertEqual(app.number_input(key="selected_lift").value, 164000.5)

    def test_selection_can_be_cleared_and_cargo_change_suggests_lift(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
        next(r for r in app.radio if r.label == 'Navigation').set_value('Reports').run()
        app.selectbox(key='selected_vessel').set_value('MF-02').run()
        app.selectbox(key='selected_cargo').set_value('CC-02').run()
        self.assertEqual(app.number_input(key='selected_lift').value, 171200)  # the ranking's suggested lift
        app.number_input(key='selected_lift').set_value(164000).run()
        self.assertFalse(app.exception)
        self.assertFalse(app.info)
        app.selectbox(key='selected_vessel').set_value(None).run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Select a vessel' in i.value for i in app.info))
        app.selectbox(key='selected_cargo').set_value(None).run()
        self.assertIsNone(app.number_input(key='selected_lift').value)
        self.assertFalse(app.exception)

    def test_new_chat_restores_initial_welcome_in_both_views(self):
        for page in ('Overview', 'AI Assistant'):
            with self.subTest(page=page):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
                app.session_state.profile_name = 'Yi Heng Test'
                next(r for r in app.radio if r.label == 'Navigation').set_value(page).run()
                welcome = next(h.proto.body for h in app.get('html') if 'chat-welcome' in h.proto.body)
                app.session_state.selected_vessel, app.session_state.selected_cargo, app.session_state.selected_lift = 'MF-02', 'CC-02', 164000.0
                app.run()
                old_key = app.chat_input[0].key
                with patch('voyage.chat.chat_reply', return_value={'content': 'Voyage analysis', 'evidence': []}):
                    app.chat_input[0].set_value('Compare this voyage').run()
                self.assertEqual(len(app.chat_message), 2)
                app.button(key='new_conversation').click().run()
                self.assertFalse(app.exception)
                self.assertFalse(app.chat_message)
                self.assertEqual(app.session_state.messages, [])
                self.assertIsNone(app.session_state.pending)
                self.assertIsNone(app.session_state.chat_error)
                for key in ('selected_vessel', 'selected_cargo', 'selected_lift'):
                    self.assertIsNone(app.session_state[key])
                self.assertIsNone(app.chat_input[0].value)
                self.assertNotEqual(old_key, app.chat_input[0].key)
                self.assertEqual(welcome, next(h.proto.body for h in app.get('html') if 'chat-welcome' in h.proto.body))
                self.assertIn('Hello, Yi Heng Test.', welcome)
                # The cleared state persists across reruns and navigation.
                other = 'AI Assistant' if page == 'Overview' else 'Overview'
                next(r for r in app.radio if r.label == 'Navigation').set_value(other).run()
                self.assertFalse(app.chat_message)
                self.assertTrue(any(welcome == h.proto.body for h in app.get('html')))

    def test_reset_during_request_discards_late_reply_or_error(self):
        from voyage.chat_view import clear_chat
        for fail in (False, True):
            with self.subTest(fail=fail):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
                def late_reply(*args, **kwargs):
                    clear_chat()
                    if fail:
                        raise ValueError('Old request failed')
                    return {'content': 'Old reply', 'evidence': []}
                with patch('voyage.chat.chat_reply', side_effect=late_reply):
                    app.chat_input[0].set_value('Old question').run()
                self.assertFalse(app.exception)
                self.assertFalse(app.chat_message)
                self.assertFalse(app.error)
                self.assertIsNone(app.session_state.pending)
                self.assertTrue(any('Hello, Yi Heng.' in h.proto.body for h in app.get('html')))

    def test_assistant_new_chat_clears_failed_question_and_replaces_composer(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
        next(r for r in app.radio if r.label == 'Navigation').set_value('AI Assistant').run()
        old_key = app.chat_input[0].key
        with patch('voyage.chat.chat_reply', side_effect=ValueError('Missing test key')):
            app.chat_input[0].set_value('Compare this voyage').run()
        self.assertTrue(app.error)
        app.button(key='new_conversation').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertFalse(app.chat_message)
        self.assertIsNone(app.session_state.pending)
        self.assertFalse(app.session_state.force_comparison)
        self.assertNotEqual(old_key, app.chat_input[0].key)
        self.assertFalse(app.chat_input[0].disabled)
        self.assertTrue(any('Hello, Yi Heng.' in h.proto.body for h in app.get('html')))
        self.assertFalse(app.success)

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
        self.assertIsNone(app.selectbox(key="price_period").value)
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state.dark_mode)
        app.button(key="theme_button").click().run()
        self.assertFalse(app.session_state.dark_mode)
        next(r for r in app.radio if r.label == "Navigation").set_value("Reports").run()
        app.selectbox(key="selected_cargo").set_value("CC-01").run()
        self.assertEqual(app.number_input(key="selected_lift").value, 169100)  # the ranking's suggested lift
        app.selectbox(key="selected_vessel").set_value("MF-02").run()
        app.number_input(key="selected_lift").set_value(178000).run()
        next(r for r in app.radio if r.label == "Navigation").set_value("Voyages").run()
        self.assertTrue(any("infeasible" in warning.value for warning in app.warning))
        self.assertFalse(app.exception)
        next(r for r in app.radio if r.label == "Navigation").set_value("Analytics").run()
        self.assertFalse(app.exception)
        self.assertIn("Fleet analytics", "".join(h.proto.body for h in app.get("html")))
        objective = next(s for s in app.selectbox if s.label == "Ranking objective")
        self.assertEqual(objective.value, "contribution")
        app.checkbox(key="optimise_rank_lift").check().run()
        next(s for s in app.selectbox if s.label == "Ranking objective").set_value("tce").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("169,100 t" in item.value and "MF-04" in item.value for item in app.get("html")))

    def test_plan_row_selection_and_all_workspace_pages(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        app.button(key="plan_pick_MF-01").click().run()
        self.assertEqual(app.session_state.plan_focus[0], "MF-01")
        next(r for r in app.radio if r.label == "Navigation").set_value("Voyages").run()
        app.selectbox(key="selected_vessel").set_value("MF-01").run()
        self.assertEqual(app.selectbox(key="selected_vessel").value, "MF-01")
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


if __name__ == "__main__":
    unittest.main()
