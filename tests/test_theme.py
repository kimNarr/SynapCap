import re
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtCore import Qt

from theme import (
    DARK,
    LIGHT,
    apply_theme_setting,
    current_setting,
    on_change,
    palette,
    resolve_system_theme,
    set_theme,
    t,
)

_UI_DIR = Path(__file__).resolve().parents[1] / "ui"


class ThemeTests(unittest.TestCase):
    def tearDown(self):
        apply_theme_setting("dark")

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

    def test_light_palette_has_the_same_token_contract(self):
        self.assertEqual(set(LIGHT), set(DARK))
        set_theme("light")
        self.assertEqual(t("ground"), LIGHT["ground"])
        self.assertEqual(palette(), LIGHT)

    def test_light_brand_choices_keep_gemini_white_and_logo_contrasted(self):
        self.assertEqual(LIGHT["provider_gemini_bg"], "#FFFFFF")
        self.assertEqual(LIGHT["logo_mark"], "#3B6FD4")

    @patch("theme.QApplication.instance", return_value=None)
    def test_system_theme_without_an_app_falls_back_to_dark(self, _instance):
        self.assertEqual(resolve_system_theme(), "dark")

    @patch("theme.QApplication.instance")
    def test_unknown_system_scheme_falls_back_to_dark(self, instance):
        app = MagicMock()
        app.styleHints.return_value.colorScheme.return_value = Qt.ColorScheme.Unknown
        instance.return_value = app

        self.assertEqual(resolve_system_theme(), "dark")

    def test_apply_theme_setting_tracks_direct_and_auto_preferences(self):
        apply_theme_setting("light")
        self.assertEqual(current_setting(), "light")
        self.assertEqual(palette(), LIGHT)

        with patch("theme.resolve_system_theme", return_value="light"):
            apply_theme_setting("auto")
        self.assertEqual(current_setting(), "auto")
        self.assertEqual(palette(), LIGHT)

        apply_theme_setting("unsupported")
        self.assertEqual(current_setting(), "dark")
        self.assertEqual(palette(), DARK)

    def test_light_body_and_semantic_text_meet_wcag_aa(self):
        def luminance(value: str) -> float:
            channels = [int(value[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [
                channel / 12.92
                if channel <= 0.04045
                else ((channel + 0.055) / 1.055) ** 2.4
                for channel in channels
            ]
            return sum(
                weight * channel
                for weight, channel in zip((0.2126, 0.7152, 0.0722), linear)
            )

        def contrast(first: str, second: str) -> float:
            high, low = sorted((luminance(first), luminance(second)), reverse=True)
            return (high + 0.05) / (low + 0.05)

        for token in (
            "ink",
            "ink_mid",
            "ink_dim",
            "ink_faintest",
            "accent",
            "usage_warn",
            "usage_crit",
            "good",
        ):
            self.assertGreaterEqual(
                contrast(LIGHT[token], LIGHT["ground"]),
                4.5,
                token,
            )

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
