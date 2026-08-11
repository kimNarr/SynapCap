import os
import unittest
from datetime import datetime
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar

from providers import CodexProvider, ModelUsage, UsageWindow
from ui.widget import SynapCapWidget, UsageRing
from version import APP_VERSION


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
        self.assertEqual(tooltip, "8/12 09:49 초기화")

    def test_bar_and_ring_views_can_be_toggled(self):
        self.widget.update_data([self.usage])
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        labels = [label.text() for label in row.findChildren(QLabel)]

        self.assertIn("49%", labels)
        self.assertNotIn("사용 49%", labels)
        self.assertEqual(len(row.findChildren(QProgressBar)), 1)
        usage_label = next(
            label for label in row.findChildren(QLabel) if label.text() == "49%"
        )
        self.assertIn("font-weight: 700", usage_label.styleSheet())

        self.widget._toggle_usage_view()
        self.app.processEvents()
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]

        self.assertEqual(self.widget.usage_view, "ring")
        rings = row.findChildren(UsageRing)
        self.assertEqual(len(rings), 1)
        self.assertEqual(rings[0].value_text, "49%")
        self.assertEqual(len(self.widget.findChildren(QProgressBar)), 0)
        self.assertEqual(
            self.widget.config_data["settings"]["usage_view"], "ring"
        )

        self.widget._toggle_usage_view()
        self.app.processEvents()
        self.assertEqual(self.widget.usage_view, "bar")
        self.assertEqual(len(self.widget.findChildren(UsageRing)), 0)

    def test_usage_value_bold_can_be_disabled(self):
        self.widget.config_data["settings"]["usage_value_bold"] = False
        self.widget.update_data([self.usage])

        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        usage_label = next(
            label for label in row.findChildren(QLabel) if label.text() == "49%"
        )
        self.assertIn("font-weight: 400", usage_label.styleSheet())

    def test_missing_cli_is_labeled_as_install_required(self):
        usage = ModelUsage(
            "codex",
            "Codex",
            "Codex",
            0,
            100,
            "%",
            error="codex CLI를 찾을 수 없음",
        )

        self.widget.update_data([usage])

        status = self.widget.provider_ui_map["codex"]["status"]
        self.assertEqual(status.text(), "설치 필요")
        self.assertEqual(status.toolTip(), usage.error)

    def test_progress_tooltip_is_shown_on_enter(self):
        self.widget.update_data([self.usage])
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        progress = row.findChild(QProgressBar)

        self.assertEqual(progress.toolTip(), "49% 사용 · 51% 남음")
        with patch("ui.widget.QToolTip.showText") as show_text:
            self.widget.eventFilter(
                progress, QEvent(QEvent.Type.Enter)
            )

        show_text.assert_called_once()

    def test_instant_tooltip_is_anchored_below_hovered_widget(self):
        expected_position = self.widget.version_btn.mapToGlobal(
            QPoint(0, self.widget.version_btn.height() + 4)
        )

        with patch("ui.widget.QToolTip.showText") as show_text:
            self.widget.eventFilter(
                self.widget.version_btn, QEvent(QEvent.Type.Enter)
            )

        self.assertEqual(show_text.call_args.args[0], expected_position)
        self.assertEqual(
            show_text.call_args.args[1], f"현재 버전 v{APP_VERSION}"
        )

    def test_usage_windows_can_be_filtered_per_provider(self):
        ui = {"show_five_hour": False, "show_weekly": True}
        windows = [
            UsageWindow("5시간", 10, "", 90),
            UsageWindow("주간", 50, "", 50),
        ]

        visible = self.widget._visible_usage_windows(ui, windows)

        self.assertEqual([window.label for window in visible], ["주간"])

    def test_version_badge_opens_available_update(self):
        requested_urls = []
        self.widget.update_requested.connect(requested_urls.append)

        self.assertEqual(self.widget.version_btn.text(), f"v{APP_VERSION}")
        self.widget.set_update_available(
            "0.1.1",
            "https://github.com/kimNarr/SynapCap/releases/tag/v0.1.1",
        )
        self.widget.version_btn.click()

        self.assertEqual(self.widget.version_btn.text(), "v0.1.1 ↑")
        self.assertEqual(
            requested_urls,
            ["https://github.com/kimNarr/SynapCap/releases/tag/v0.1.1"],
        )

    def test_header_uses_minimize_and_exit_controls(self):
        quit_requests = []
        self.widget.quit_requested.connect(lambda: quit_requests.append(True))

        self.assertEqual(self.widget.windowType(), Qt.WindowType.Window)
        self.assertEqual(self.widget.version_btn.height(), 20)
        self.widget.minimize_btn.click()
        self.app.processEvents()
        self.assertTrue(self.widget.isMinimized())

        self.widget.showNormal()
        self.widget.close_btn.click()
        self.assertEqual(quit_requests, [True])

    def test_confirmed_shutdown_does_not_request_quit_again(self):
        quit_requests = []
        self.widget.quit_requested.connect(lambda: quit_requests.append(True))

        self.widget.begin_shutdown()
        self.assertTrue(self.widget.close())
        self.app.processEvents()

        self.assertEqual(quit_requests, [])
        self.assertFalse(self.widget.isVisible())

    def test_cached_usage_does_not_rebuild_existing_rows(self):
        self.widget.update_data([self.usage])
        original_row = self.widget.provider_ui_map["codex"]["window_rows"][0]

        self.widget.update_data([self.usage])

        current_row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        self.assertIs(current_row, original_row)

    def test_missing_reset_is_shown_explicitly(self):
        self.widget.provider_ui_map["codex"]["show_five_hour"] = True
        self.usage.windows = [UsageWindow("5시간", 0, "", 100)]
        self.widget.update_data([self.usage])

        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        labels = [label.text() for label in row.findChildren(QLabel)]
        self.assertIn("5시간 · 리셋 시각 미상", labels)

    def test_visual_rebuild_reuses_latest_usage(self):
        self.widget.update_data([self.usage])
        new_config = {
            "settings": {
                "widget_size": "Large",
                "widget_width": 350,
                "always_on_top": False,
                "usage_view": "bar",
                "usage_value_bold": False,
            }
        }

        self.widget.rebuild_ui(
            new_config,
            [CodexProvider({"id": "codex", "name": "Codex"})],
        )

        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        usage_label = next(
            label for label in row.findChildren(QLabel) if label.text() == "49%"
        )
        self.assertIn("font-weight: 400", usage_label.styleSheet())


if __name__ == "__main__":
    unittest.main()
