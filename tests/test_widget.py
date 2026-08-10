import os
import unittest
from datetime import datetime

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QProgressBar

from providers import CodexProvider, ModelUsage, UsageWindow
from ui.widget import SynapCapWidget, UsageRing


class WidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        provider = CodexProvider({"id": "codex", "name": "Codex"})
        self.widget = SynapCapWidget(
            {
                "settings": {
                    "widget_size": "Medium",
                    "widget_width": 300,
                    "always_on_top": False,
                    "usage_view": "bar",
                }
            },
            [provider],
        )
        self.usage = ModelUsage(
            "codex",
            "Codex",
            "Codex",
            49,
            100,
            "%",
            windows=[UsageWindow("주간", 49, "8/12 09:49", 51)],
        )
        self.widget.show()
        self.app.processEvents()

    def tearDown(self):
        self.widget.close()
        self.widget.deleteLater()
        self.app.processEvents()

    def test_reset_time_is_presented_relatively(self):
        relative, tooltip = self.widget._reset_presentation(
            "8/12 09:49",
            now=datetime(2026, 8, 10, 17, 0),
        )

        self.assertEqual(relative, "1일 16시간 후")
        self.assertEqual(tooltip, "정확한 리셋: 8/12 09:49")

    def test_bar_and_ring_views_can_be_toggled(self):
        self.widget.update_data([self.usage])
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        labels = [label.text() for label in row.findChildren(QLabel)]

        self.assertIn("사용 49%", labels)
        self.assertEqual(len(row.findChildren(QProgressBar)), 1)

        self.widget._toggle_usage_view()
        self.app.processEvents()
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]

        self.assertEqual(self.widget.usage_view, "ring")
        self.assertEqual(len(row.findChildren(UsageRing)), 1)
        self.assertEqual(len(self.widget.findChildren(QProgressBar)), 0)
        self.assertEqual(
            self.widget.config_data["settings"]["usage_view"], "ring"
        )

        self.widget._toggle_usage_view()
        self.app.processEvents()
        self.assertEqual(self.widget.usage_view, "bar")
        self.assertEqual(len(self.widget.findChildren(UsageRing)), 0)


if __name__ == "__main__":
    unittest.main()
