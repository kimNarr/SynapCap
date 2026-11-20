import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from PySide6.QtCore import QRect

from macos_display import notch_rect


def rect(x, y, width, height):
    return SimpleNamespace(origin=SimpleNamespace(x=x, y=y),
                           size=SimpleNamespace(width=width, height=height))


def screen(x=0, y=0, width=1512, height=982, inset=38, notch_width=200):
    side_width = (width - notch_width) / 2
    return SimpleNamespace(
        frame=lambda: rect(x, y, width, height),
        respondsToSelector_=lambda _selector: True,
        safeAreaInsets=lambda: SimpleNamespace(top=inset),
        auxiliaryTopLeftArea=lambda: rect(x, y + height - inset, side_width, inset),
        auxiliaryTopRightArea=lambda: rect(x + side_width + notch_width, y + height - inset, side_width, inset),
    )


class MacDisplayTests(unittest.TestCase):
    def read(self, screens):
        cocoa = SimpleNamespace(NSScreen=SimpleNamespace(screens=lambda: screens))
        with patch("macos_display.sys.platform", "darwin"), patch.dict(sys.modules, {"AppKit": cocoa}):
            return notch_rect()

    def test_non_macos_never_imports_cocoa(self):
        with patch("macos_display.sys.platform", "win32"), patch.dict(sys.modules, {"AppKit": None}):
            self.assertIsNone(notch_rect())

    def test_missing_cocoa_falls_back_to_menu_bar(self):
        with patch("macos_display.sys.platform", "darwin"), patch.dict(sys.modules, {"AppKit": None}):
            self.assertIsNone(notch_rect())

    def test_builtin_camera_housing_maps_to_qt_top_left_coordinates(self):
        self.assertEqual(self.read([screen()]), QRect(656, 0, 200, 38))

    def test_external_primary_does_not_hide_builtin_notch(self):
        self.assertEqual(self.read([
            screen(width=1920, height=1080, inset=0), screen(x=-1512),
        ]), QRect(-856, 98, 200, 38))

    def test_screen_above_primary_keeps_negative_qt_y(self):
        self.assertEqual(self.read([
            screen(width=1920, height=1080, inset=0), screen(y=1080),
        ]), QRect(656, -982, 200, 38))

    def test_no_notch_no_screens_and_invalid_gap_fall_back(self):
        for screens in ([], [screen(inset=0)], [screen(notch_width=0)], [screen(notch_width=-10)]):
            with self.subTest(screens=screens):
                self.assertIsNone(self.read(screens))


if __name__ == "__main__":
    unittest.main()
