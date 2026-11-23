import re
import unittest
from datetime import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

from voyage.patch_notes import PATCHES, label, patch_html

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class PatchNotesTests(unittest.TestCase):
    def test_one_patch_per_push_newest_first(self):
        versions = [p[0] for p in PATCHES]
        self.assertEqual(len(versions), len(set(versions)))
        times = [datetime.strptime(p[1], "%Y-%m-%d %H:%M") for p in PATCHES]
        self.assertEqual(times, sorted(times, reverse=True))
        keys = [tuple(int(n) for n in v.split(".")) for v in versions]
        self.assertEqual(keys, sorted(keys, reverse=True))
        for patch in PATCHES:
            self.assertTrue(patch[4], patch[0])

    def test_patch_renders_date_sections_and_escapes_text(self):
        body = patch_html("1.6")
        self.assertIn('<h2 class="pn-date">November 9, 2026</h2>', body)
        self.assertIn('<h3 class="pn-section">ASK SHIPPY</h3>', body)
        self.assertIn("<code>/voyages</code>", body)
        self.assertNotIn("<script", body)
        self.assertTrue(label(PATCHES[0][0]).endswith("Latest"))

    def test_documents_button_opens_patch_notes_and_picker_switches(self):
        app = AppTest.from_file(APP).run()
        next(r for r in app.radio if r.label == "Navigation").set_value("Documents").run()
        app.button(key="open_patch_notes").click().run()
        self.assertFalse(app.exception)
        html = " ".join(h.proto.body for h in app.get("html"))
        self.assertIn(f'v{PATCHES[0][0]}', html)
        app.selectbox(key="patch_version").set_value("0.1").run()
        html = " ".join(h.proto.body for h in app.get("html"))
        self.assertIn("October 26, 2026", html)
        app.button(key="patch_back").click().run()
        self.assertIsNotNone(app.button(key="open_patch_notes"))


if __name__ == "__main__":
    unittest.main()
