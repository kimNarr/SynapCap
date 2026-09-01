import re
import unittest
from pathlib import Path

from theme import DARK, on_change, palette, set_theme, t

_UI_DIR = Path(__file__).resolve().parents[1] / "ui"


class ThemeTests(unittest.TestCase):
    def tearDown(self):
        set_theme("dark")

    def test_active_palette_matches_dark_extraction(self):
        # The extraction step must be a visual no-op: every active value is the
        # exact hex that used to be hard-coded in ui/.
        self.assertEqual(palette(), DARK)
        for name, value in DARK.items():
            self.assertEqual(t(name), value)

    def test_palette_returns_a_copy(self):
        snapshot = palette()
        snapshot["ground"] = "#ffffff"
        self.assertNotEqual(t("ground"), "#ffffff")

    def test_unknown_theme_falls_back_to_dark(self):
        set_theme("does-not-exist")
        self.assertEqual(palette(), DARK)

    def test_on_change_fires_on_switch(self):
        hits = []
        on_change(lambda: hits.append(1))
        set_theme("dark")
        self.assertTrue(hits)

    def test_every_token_referenced_in_ui_exists(self):
        known = set(DARK)
        missing = {}
        for path in _UI_DIR.glob("*.py"):
            src = path.read_text(encoding="utf-8")
            pattern = r"%\((\w+)\)s|(?<![\w.])t\(\s*[\"'](\w+)[\"']\s*\)"
            for match in re.finditer(pattern, src):
                token = match.group(1) or match.group(2)
                if token not in known:
                    missing.setdefault(path.name, set()).add(token)
        self.assertEqual(missing, {})


if __name__ == "__main__":
    unittest.main()
