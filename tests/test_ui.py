import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


class UITests(unittest.TestCase):
    def test_new_chat_restores_initial_welcome_in_both_views(self):
        for page in ('Dashboard', 'AI Assistant'):
            with self.subTest(page=page):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'app.py')).run()
                app.session_state.profile_name = 'Yi Heng Test'
                next(r for r in app.radio if r.label == 'Navigation').set_value(page).run()
                welcome = next(h.proto.body for h in app.get('html') if 'chat-welcome' in h.proto.body)
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
                self.assertIsNone(app.chat_input[0].value)
                self.assertNotEqual(old_key, app.chat_input[0].key)
                self.assertEqual(welcome, next(h.proto.body for h in app.get('html') if 'chat-welcome' in h.proto.body))
                self.assertIn('Hello, Yi Heng Test.', welcome)
                # The cleared state persists across reruns and navigation.
                other = 'AI Assistant' if page == 'Dashboard' else 'Dashboard'
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
        self.assertEqual(app.selectbox(key="price_period").value, "2026-03")
        self.assertFalse(app.exception)
        self.assertTrue(app.session_state.dark_mode)
        app.button(key="theme_button").click().run()
        self.assertFalse(app.session_state.dark_mode)
        app.selectbox(key="selected_cargo").set_value("CC-01").run()
        self.assertEqual(app.number_input(key="selected_lift").value, 178000)
        next(r for r in app.radio if r.label == "Navigation").set_value("Voyages").run()
        self.assertTrue(any("infeasible" in warning.value for warning in app.warning))
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


if __name__ == "__main__":
    unittest.main()
