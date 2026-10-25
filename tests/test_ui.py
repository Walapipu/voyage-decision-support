import unittest
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest


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
        next(b for b in app.button if b.label == "New conversation").click().run()
        self.assertEqual(len(app.chat_message), 0)

    def test_dashboard_selection_theme_and_navigation(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
        self.assertEqual(app.selectbox(key="price_period").value, "2026-03")
        self.assertFalse(app.exception)
        self.assertTrue(app.toggle(key="dark_mode").value)
        app.toggle(key="dark_mode").set_value(False).run()
        self.assertFalse(app.toggle(key="dark_mode").value)
        app.selectbox(key="selected_cargo").set_value("CC-01").run()
        self.assertEqual(app.number_input(key="selected_lift").value, 178000)
        self.assertTrue(any("infeasible" in warning.value for warning in app.warning))
        next(r for r in app.radio if r.label == "Navigation").set_value("Voyages").run()
        self.assertFalse(app.exception)
        next(r for r in app.radio if r.label == "Navigation").set_value("Analytics").run()
        self.assertFalse(app.exception)
        self.assertTrue(any("threshold" in w.value for w in app.warning))


if __name__ == "__main__":
    unittest.main()
