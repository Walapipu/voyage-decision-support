import json
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from voyage.tour import MAX_COPY, TOURS

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class TourTests(unittest.TestCase):
    def test_tours_are_short_and_selective(self):
        self.assertEqual(set(TOURS), {"Overview", "Voyages", "AI Assistant", "Analytics"})
        for page, steps in TOURS.items():
            self.assertTrue(3 <= len(steps) <= 5, page)
            for selector, title, body in steps:
                self.assertLessEqual(len(body), MAX_COPY, (page, title))
                self.assertTrue(selector and title and body)
                self.assertFalse(body.endswith("!"))

    def test_each_page_starts_its_own_tour_and_replay_forces_it(self):
        app = AppTest.from_file(APP).run()
        script = next(h.proto.body for h in app.get("html") if "kfTour.start" in h.proto.body)
        self.assertIn('window.kfTour.start("Overview", ', script)
        self.assertTrue(script.rstrip().endswith('false);</script>'))
        self.assertNotIn("innerHTML", script)  # markup inside the script would be stripped by the sanitiser
        next(r for r in app.radio if r.label == "Navigation").set_value("Voyages").run()
        script = next(h.proto.body for h in app.get("html") if "kfTour.start" in h.proto.body)
        self.assertIn('window.kfTour.start("Voyages", ', script)
        self.assertIn(json.dumps(TOURS["Voyages"][0][0]), script)
        app.button(key="replay_tour").click().run()
        self.assertFalse(app.exception)
        script = next(h.proto.body for h in app.get("html") if "kfTour.start" in h.proto.body)
        self.assertTrue(script.rstrip().endswith('true);</script>'))

    def test_seen_state_is_tied_to_this_server_run(self):
        from voyage.tour import _server_boot
        boot = _server_boot()
        self.assertEqual(boot, _server_boot())  # stable across reruns and refreshes
        app = AppTest.from_file(APP).run()
        script = next(h.proto.body for h in app.get("html") if "kfTour.start" in h.proto.body)
        self.assertIn(json.dumps(boot) + ", false);", script)
        _server_boot.clear()  # what a restart does
        self.assertNotEqual(boot, _server_boot())

    def test_form_submit_buttons_follow_the_theme(self):
        css = (Path(__file__).resolve().parents[1] / "voyage" / "dashboard.css").read_text(encoding="utf-8")
        self.assertIn('[data-testid="stFormSubmitButton"] button{', css.replace(",", "{", 0))
        self.assertIn('button[kind="primaryFormSubmit"]', css)


if __name__ == "__main__":
    unittest.main()
