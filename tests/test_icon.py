import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from ui.icon import (
    _asset_bytes,
    _render_svg,
    create_app_icon_pixmap,
    create_app_pixmap,
    create_wordmark_pixmap,
)


def _painted_pixels(pixmap) -> int:
    image = pixmap.toImage()
    return sum(
        1
        for y in range(image.height())
        for x in range(image.width())
        if image.pixelColor(x, y).alpha() > 8
    )


class IconTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_brand_svgs_resolve_and_render(self):
        for name in ("logo.svg", "logo-icon.svg", "wordmark.svg"):
            data = _asset_bytes(name)
            self.assertTrue(data.startswith(b"<svg"), name)
            rendered = _render_svg(data, 64, 64)
            self.assertIsNotNone(rendered, name)
            assert rendered is not None
            self.assertGreater(_painted_pixels(rendered), 50, name)

    def test_render_svg_preserves_aspect_ratio(self):
        # wordmark viewBox is ~223.8 x 52; a 200x200 box must not stretch it.
        pixmap = _render_svg(_asset_bytes("wordmark.svg"), 200, 200)
        self.assertIsNotNone(pixmap)
        assert pixmap is not None
        image = pixmap.toImage()
        rows = [
            y
            for y in range(image.height())
            if any(image.pixelColor(x, y).alpha() > 8 for x in range(image.width()))
        ]
        drawn_height = rows[-1] - rows[0] + 1
        self.assertLess(drawn_height, 120)  # letters stay a horizontal strip

    def test_render_svg_returns_none_on_bad_input(self):
        self.assertIsNone(_render_svg(b"", 32, 32))
        self.assertIsNone(_render_svg(b"not an svg", 32, 32))

    def test_app_pixmaps_are_not_blank(self):
        for size in (16, 32, 64, 256):
            self.assertGreater(_painted_pixels(create_app_pixmap(size)), 10)
            self.assertGreater(_painted_pixels(create_app_icon_pixmap(size)), 30)
        self.assertGreater(_painted_pixels(create_wordmark_pixmap(96, 30)), 30)


if __name__ == "__main__":
    unittest.main()
