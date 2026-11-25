import unittest
from datetime import datetime
from pathlib import Path

from streamlit.testing.v1 import AppTest

from voyage.patch_notes import DATES_PER_PAGE, PATCHES, day_html, days, pages

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

    def test_same_date_pushes_share_one_note(self):
        dated = days()
        self.assertEqual(len(dated), len({p[1][:10] for p in PATCHES}))
        self.assertEqual(sum(len(p) for _, p in dated), len(PATCHES))
        date, patches = next((d, p) for d, p in dated if len(p) > 1)
        body = day_html(date, patches)
        self.assertEqual(body.count('class="pn-date"'), 1)
        self.assertIn(f'<p class="pn-v">v{patches[-1][0]} to v{patches[0][0]}</p>', body)
        self.assertNotIn("SGT", body)
        names = [n for p in patches for n, _ in p[4]]
        for name in set(names):
            self.assertEqual(body.count(f'<h3 class="pn-section">{name}</h3>'), 1)

    def test_pages_hold_five_dates_and_render_safely(self):
        book = pages()
        self.assertTrue(all(len(p) == DATES_PER_PAGE for p in book[:-1]))
        self.assertEqual(sum(len(p) for p in book), len(days()))
        body = day_html("2026-11-09", next(p for d, p in days() if d == "2026-11-09"))
        self.assertIn('<h2 class="pn-date">November 9, 2026</h2>', body)
        self.assertIn('<h3 class="pn-section">ASK SHIPPY</h3>', body)
        self.assertIn("<code>/voyages</code>", body)
        self.assertNotIn("<script", body)
        self.assertNotIn("OceanFlow", body)

    def test_documents_button_opens_patch_notes_and_pager_moves(self):
        app = AppTest.from_file(APP).run()
        next(r for r in app.radio if r.label == "Navigation").set_value("Documents").run()
        app.button(key="open_patch_notes").click().run()
        self.assertFalse(app.exception)
        html = " ".join(h.proto.body for h in app.get("html"))
        self.assertIn(f'v{PATCHES[0][0]}<', html)
        self.assertTrue(app.button(key="patch_newer").disabled)
        last = len(pages()) - 1
        app.button(key=f"patch_pg_{last}").click().run()
        html = " ".join(h.proto.body for h in app.get("html"))
        self.assertIn("October 26, 2026", html)
        self.assertTrue(app.button(key="patch_older").disabled)
        app.button(key="patch_newer").click().run()
        self.assertTrue(app.button(key=f"patch_pg_{last - 1}").disabled)
        app.button(key="patch_back").click().run()
        self.assertIsNotNone(app.button(key="open_patch_notes"))


if __name__ == "__main__":
    unittest.main()
