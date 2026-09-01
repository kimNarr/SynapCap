import os
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from providers import (
    AntigravityProvider,
    BaseAIProvider,
    ClaudeProvider,
    CodexProvider,
    ModelUsage,
    UsageWindow,
)
from ui.widget import SynapCapWidget, UsageBar, UsageRing
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
            now=datetime(2026, 8, 10, 17, 0, tzinfo=UTC),
        )

        self.assertEqual(relative, "1일 16시간 후")
        self.assertEqual(tooltip, "8/12 09:49 초기화")

    def test_expanded_header_uses_horizontal_wordmark(self):
        self.assertTrue(hasattr(self.widget, "wordmark_label"))
        self.assertFalse(self.widget.wordmark_label.pixmap().isNull())
        self.assertFalse(hasattr(self.widget, "title_label"))

    def test_past_reset_does_not_roll_over_to_next_year(self):
        relative, tooltip = self.widget._reset_presentation(
            "8/26 13:00",
            now=datetime(2026, 8, 26, 14, 2, tzinfo=UTC),
        )

        self.assertEqual(relative, "초기화 확인 중")
        self.assertEqual(tooltip, "8/26 13:00 초기화")

    def test_reset_rolls_over_only_near_year_boundary(self):
        relative, tooltip = self.widget._reset_presentation(
            "1/1 00:30",
            now=datetime(2026, 12, 31, 23, 30, tzinfo=UTC),
        )

        self.assertEqual(relative, "1시간 후")
        self.assertEqual(tooltip, "1/1 00:30 초기화")

    def test_condensed_reset_drops_the_relative_suffix(self):
        self.assertEqual(self.widget._condensed_reset("3시간 17분 후"), "3h 17m")
        self.assertEqual(self.widget._condensed_reset("6일 16시간 후"), "6d 16h")
        # Long status strings collapse to short forms that fit the reset column.
        self.assertEqual(self.widget._condensed_reset(""), "미상")
        self.assertEqual(self.widget._condensed_reset("리셋 시각 미상"), "미상")
        self.assertEqual(self.widget._condensed_reset("초기화 확인 중"), "확인 중")
        self.assertEqual(self.widget._usage_window_marker("5시간"), "5h")
        self.assertEqual(self.widget._usage_window_marker("주간"), "7d")

    def test_bar_and_ring_views_can_be_toggled(self):
        self.widget.update_data([self.usage])
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        labels = [label.text() for label in row.findChildren(QLabel)]

        self.assertNotIn("사용 49%", labels)
        self.assertIn("7d", labels)
        self.assertIn("49%", labels)
        usage_bar = row.findChild(UsageBar)
        self.assertIsNotNone(usage_bar)
        assert usage_bar is not None
        self.assertEqual(usage_bar.usage_used, 49)
        value_label = next(
            label for label in row.findChildren(QLabel) if label.text() == "49%"
        )
        # A normal (< 60%) value is demibold — calmer than the bold provider
        # name and the bold warning/critical values.
        self.assertEqual(value_label.font().weight(), 600)
        marker_label = next(
            label for label in row.findChildren(QLabel) if label.text() == "7d"
        )
        self.assertEqual(marker_label.font().weight(), 400)

        self.widget._toggle_usage_view()
        self.app.processEvents()
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]

        self.assertEqual(self.widget.usage_view, "ring")
        rings = row.findChildren(UsageRing)
        self.assertEqual(len(rings), 1)
        self.assertEqual(rings[0].value_text, "49%")
        self.assertEqual(len(self.widget.findChildren(UsageBar)), 0)
        self.assertEqual(self.widget.config_data["settings"]["usage_view"], "ring")

        self.widget._toggle_usage_view()
        self.app.processEvents()
        self.assertEqual(self.widget.usage_view, "bar")
        self.assertEqual(len(self.widget.findChildren(UsageRing)), 0)

    def test_usage_bar_keeps_a_minimum_fill_for_nonzero_usage(self):
        self.usage.windows = [UsageWindow("5시간", 1, "8/12 09:49", 99)]
        self.widget.update_data([self.usage], force=True)
        self.app.processEvents()

        usage_bar = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(
            UsageBar
        )
        self.assertIsNotNone(usage_bar)
        assert usage_bar is not None
        usage_bar.grab()
        self.assertGreaterEqual(usage_bar.fill_width, 3)

        self.usage.windows = [UsageWindow("5시간", 0, "8/12 09:49", 100)]
        self.widget.update_data([self.usage], force=True)
        self.app.processEvents()
        usage_bar = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(
            UsageBar
        )
        self.assertIsNotNone(usage_bar)
        assert usage_bar is not None
        usage_bar.grab()
        self.assertEqual(usage_bar.fill_width, 0)

    def test_usage_scale_uses_blue_peach_red(self):
        self.assertEqual(self.widget._usage_color(10), "#89B4FA")
        self.assertEqual(self.widget._usage_color(65), "#FAB387")
        self.assertEqual(self.widget._usage_color(88), "#F38BA8")

    def test_warning_and_critical_values_have_non_color_signals(self):
        self.widget.config_data["settings"]["expanded_font_bold"] = False
        self.usage.windows = [UsageWindow("5시간", 65, "8/12 09:49", 35)]
        self.widget.update_data([self.usage], force=True)

        value_label = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(
            QLabel, "usageValue"
        )
        self.assertIsNotNone(value_label)
        assert value_label is not None
        self.assertEqual(value_label.text(), "65%")
        self.assertEqual(value_label.font().weight(), 700)
        self.assertIn("#FAB387", value_label.styleSheet())

        self.usage.windows = [UsageWindow("5시간", 85, "8/12 09:49", 15)]
        self.widget.update_data([self.usage], force=True)
        value_label = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(
            QLabel, "usageValue"
        )
        self.assertIsNotNone(value_label)
        assert value_label is not None
        self.assertEqual(value_label.text(), "▲ 85%")
        self.assertEqual(value_label.font().weight(), 700)

    def test_bar_reset_countdown_uses_secondary_visual_weight(self):
        self.widget.update_data([self.usage])
        reset_label = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(
            QLabel, "resetCountdown"
        )

        self.assertIsNotNone(reset_label)
        assert reset_label is not None
        self.assertIn("color: #8087A0", reset_label.styleSheet())
        preset = self.widget._expanded_preset(self.widget.config_data["settings"])
        self.assertEqual(
            reset_label.font().pointSize(),
            max(9, preset["val_size"] - 2),
        )
        self.assertGreaterEqual(reset_label.width(), 48)

    def test_codex_defaults_to_five_hour_and_weekly_windows(self):
        self.usage.windows = [
            UsageWindow("5시간", 38, "8/26 14:07", 62),
            UsageWindow("주간", 6, "9/2 09:07", 94),
        ]

        self.widget.update_data([self.usage])

        rows = self.widget.provider_ui_map["codex"]["window_rows"]
        self.assertEqual(len(rows), 2)
        values = [
            next(
                label.text()
                for label in row.findChildren(QLabel)
                if label.text().endswith("%")
            )
            for row in rows
        ]
        self.assertEqual(values, ["38%", "6%"])

    def test_usage_value_bold_can_be_disabled(self):
        self.widget.config_data["settings"]["expanded_font_bold"] = False
        self.widget.update_data([self.usage])

        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        value_label = next(
            label for label in row.findChildren(QLabel) if label.text().endswith("%")
        )
        self.assertEqual(value_label.font().weight(), 400)

    def test_compact_usage_bold_option_changes_the_rendered_font_weight(self):
        self.widget.config_data["settings"]["compact_font_bold"] = False
        self.widget.update_data([self.usage])
        self.widget.enter_compact_mode()
        self.app.processEvents()

        compact_value = self.widget.compact_ui_map["codex"]["value"]
        self.assertEqual(compact_value.font().weight(), 400)

        self.widget.config_data["settings"]["compact_font_bold"] = True
        self.widget.rebuild_ui(self.widget.config_data, self.widget.providers)
        self.app.processEvents()
        compact_value = self.widget.compact_ui_map["codex"]["value"]
        self.assertEqual(compact_value.font().weight(), 700)

    def test_medium_widget_scale_sets_a_roomier_default_width(self):
        self.widget.rebuild_ui(
            {
                "settings": {
                    "widget_scale": "medium",
                    "always_on_top": False,
                    "usage_view": "bar",
                }
            },
            [CodexProvider({"id": "codex", "name": "Codex"})],
            preserve_usage=False,
        )

        self.assertEqual(self.widget.width(), 360)
        self.assertEqual(self.widget._expanded_preset({"widget_scale": "medium"})["val_size"], 13)

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
        self.assertIn(usage.error, status.toolTip())
        self.assertIn("진단 정보 보기", status.toolTip())

    def test_progress_tooltip_is_shown_on_enter(self):
        self.widget.update_data([self.usage])
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        usage_bar = row.findChild(UsageBar)
        self.assertIsNotNone(usage_bar)
        assert usage_bar is not None

        self.assertEqual(usage_bar.toolTip(), "49% 사용 · 51% 남음")
        with patch("ui.widget.QToolTip.showText") as show_text:
            self.widget.eventFilter(usage_bar, QEvent(QEvent.Type.Enter))

        show_text.assert_called_once()

    def test_claude_discloses_cli_source_and_query_time(self):
        provider = ClaudeProvider({"id": "claude", "name": "Claude"})
        self.widget.rebuild_ui(
            {
                "settings": {
                    "widget_size": "Medium",
                    "always_on_top": False,
                    "usage_view": "bar",
                }
            },
            [provider],
        )
        usage = ModelUsage(
            "claude",
            "Claude",
            "Claude Code",
            100,
            100,
            "%",
            windows=[
                UsageWindow("5시간", 100, "8/14 14:40", 0),
                UsageWindow("주간", 34, "8/19 04:00", 66),
            ],
            fetched_at=datetime(2026, 8, 14, 13, 20, 30, tzinfo=UTC),
        )

        self.widget.update_data([usage])

        ui = self.widget.provider_ui_map["claude"]
        self.assertEqual(ui["status"].text(), "CLI 기준")
        self.assertFalse(ui["status"].isHidden())
        self.assertTrue(ui["status"].property("instantTooltip"))
        self.assertIn("마지막 조회: 8/14 13:20:30", ui["status"].toolTip())
        self.assertIn("일시적으로 차이가 날 수 있습니다", ui["status"].toolTip())
        usage_bar = ui["window_rows"][0].findChild(UsageBar)
        self.assertIsNotNone(usage_bar)
        assert usage_bar is not None
        self.assertIn("Claude CLI 기준 사용량", usage_bar.toolTip())

        self.widget.enter_compact_mode()
        compact_item = self.widget.compact_ui_map["claude"]["item"]
        compact_tooltip = compact_item.toolTip()
        self.assertIn("마지막 조회: 8/14 13:20:30", compact_tooltip)
        self.assertTrue(compact_item.property("instantTooltip"))
        self.assertFalse(
            self.widget.compact_ui_map["claude"]["value"].property("instantTooltip")
        )

    def test_old_usage_tooltip_recommends_refresh(self):
        text = self.widget._data_freshness_text(
            datetime(2026, 8, 27, 8, 0, tzinfo=UTC),
            30,
            now=datetime(2026, 8, 27, 8, 12, tzinfo=UTC),
        )

        self.assertIn("12분 전", text)
        self.assertIn("새로고침 권장", text)

    def test_status_badge_requests_provider_diagnostics(self):
        usage = ModelUsage(
            "codex",
            "Codex",
            "Codex",
            0,
            100,
            "%",
            error="codex CLI를 찾을 수 없음",
        )
        requested = []
        self.widget.diagnostics_requested.connect(requested.append)
        self.widget.update_data([usage])

        self.widget.provider_ui_map["codex"]["status"].click()

        self.assertEqual(requested, ["codex"])

    def test_instant_tooltip_is_anchored_below_hovered_widget(self):
        expected_position = self.widget.version_btn.mapToGlobal(
            QPoint(0, self.widget.version_btn.height() + 8)
        )

        with patch("ui.widget.QToolTip.showText") as show_text:
            self.widget.eventFilter(self.widget.version_btn, QEvent(QEvent.Type.Enter))

        self.assertEqual(show_text.call_args.args[0], expected_position)
        self.assertEqual(show_text.call_args.args[1], f"현재 버전 v{APP_VERSION}")

    def test_instant_tooltip_moves_above_widgets_near_screen_bottom(self):
        screen = QApplication.primaryScreen()
        self.assertIsNotNone(screen)
        assert screen is not None
        available = screen.availableGeometry()
        watched = QWidget()
        watched.resize(100, 20)
        watched.move(available.left() + 20, available.bottom() - 10)

        position = self.widget._instant_tooltip_position(
            watched,
            "Provider\n5시간 10% 사용\n주간 20% 사용",
        )

        self.assertLess(position.y(), watched.mapToGlobal(QPoint(0, 0)).y())

    def test_usage_windows_can_be_filtered_per_provider(self):
        ui = {"show_five_hour": False, "show_weekly": True}
        windows = [
            UsageWindow("5시간", 10, "", 90),
            UsageWindow("현재 세션", 20, "", 80),
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

    def test_version_badge_shows_download_progress_and_recovers(self):
        url = "https://github.com/kimNarr/SynapCap/releases/tag/v0.2.0"
        self.widget.set_update_available("0.2.0", url)

        self.widget.set_update_progress("0.2.0", 42)

        self.assertEqual(self.widget.version_btn.text(), "↓ 42%")
        self.assertFalse(self.widget.version_btn.isEnabled())

        self.widget.restore_update_available("0.2.0", url)

        self.assertEqual(self.widget.version_btn.text(), "v0.2.0 ↑")
        self.assertTrue(self.widget.version_btn.isEnabled())

    def test_header_uses_compact_and_exit_controls(self):
        quit_requests = []
        self.widget.quit_requested.connect(lambda: quit_requests.append(True))

        self.assertEqual(self.widget.windowType(), Qt.WindowType.Tool)
        self.assertTrue(self.widget.windowFlags() & Qt.WindowType.Tool)
        self.assertEqual(self.widget.version_btn.height(), 20)
        self.widget.minimize_btn.click()
        self.app.processEvents()
        self.assertTrue(self.widget.is_compact)
        self.assertTrue(self.widget.compact_bar.isVisible())
        self.assertFalse(self.widget.cards_frame.isVisible())
        self.assertFalse(self.widget.isMinimized())

        self.widget.expand_btn.click()
        self.app.processEvents()
        self.assertFalse(self.widget.is_compact)
        self.assertTrue(self.widget.cards_frame.isVisible())
        self.widget.close_btn.click()
        self.assertEqual(quit_requests, [True])

    def test_macos_tool_window_stays_visible_when_application_deactivates(self):
        provider = CodexProvider({"id": "codex", "name": "Codex"})
        with patch("ui.widget.sys.platform", "darwin"):
            widget = SynapCapWidget(
                {
                    "settings": {
                        "widget_size": "Medium",
                        "always_on_top": True,
                    }
                },
                [provider],
            )

        self.assertTrue(
            widget.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        )
        self.assertTrue(widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)

        widget.set_always_on_top(False)
        self.assertTrue(
            widget.testAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow)
        )
        self.assertFalse(widget.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        widget.close()
        widget.deleteLater()

    def test_compact_bar_shows_latest_provider_usage(self):
        self.widget.update_data([self.usage])
        self.widget.enter_compact_mode()
        self.app.processEvents()

        compact_value = self.widget.compact_ui_map["codex"]["value"]
        compact_item = self.widget.compact_ui_map["codex"]["item"]
        self.assertEqual(compact_value.text(), "49%")
        self.assertIn("Codex", compact_item.toolTip())
        self.assertEqual(compact_value.font().pointSize(), 12)
        self.assertIn("color: #F8FAFC", compact_value.styleSheet())
        self.assertEqual(self.widget.compact_logo.size().width(), 18)
        self.assertEqual(self.widget.expand_btn.height(), 22)
        self.assertLess(self.widget.frame.height(), 40)
        self.assertTrue(self.widget.frame.property("compactMode"))
        self.assertIn("border: 2px solid #4A5266", self.widget.frame.styleSheet())
        self.assertIn("QFrame#rootFrame", self.widget.frame.styleSheet())
        self.assertIn("border-radius: 6px", self.widget.frame.styleSheet())

    def test_loading_uses_animation_and_keeps_existing_rows(self):
        ui = self.widget.provider_ui_map["codex"]

        self.assertEqual(ui["status"].text(), "")
        self.assertTrue(ui["spinner"].is_spinning())

        self.widget.update_data([self.usage])
        existing_rows = len(ui["window_rows"])
        self.assertFalse(ui["spinner"].is_spinning())

        self.widget.set_loading()

        self.assertTrue(ui["spinner"].is_spinning())
        self.assertFalse(self.widget.refresh_btn.isEnabled())
        self.assertEqual(len(ui["window_rows"]), existing_rows)

        self.widget.update_data([self.usage])
        self.assertFalse(ui["spinner"].is_spinning())
        self.assertTrue(self.widget.refresh_btn.isEnabled())

    def test_compact_bar_shows_both_enabled_usage_windows(self):
        provider = AntigravityProvider(
            {
                "id": "gemini",
                "name": "Gemini",
                "show_five_hour": True,
                "show_weekly": True,
            }
        )
        self.widget.rebuild_ui(
            self.widget.config_data,
            [provider],
            preserve_usage=False,
        )
        usage = ModelUsage(
            "gemini",
            "Gemini",
            "Gemini",
            49,
            100,
            "%",
            windows=[
                UsageWindow("주간", 49, "", 51),
                UsageWindow("5시간", 15, "", 85),
            ],
        )

        self.widget.update_data([usage])
        self.widget.enter_compact_mode()
        self.app.processEvents()

        compact_value = self.widget.compact_ui_map["gemini"]["value"]
        compact_item = self.widget.compact_ui_map["gemini"]["item"]
        self.assertEqual(compact_value.text(), "15%/49%")
        self.assertGreaterEqual(compact_value.width(), compact_value.sizeHint().width())
        self.assertIn("5시간 15% 사용", compact_item.toolTip())
        self.assertIn("주간 49% 사용", compact_item.toolTip())

        self.widget.provider_ui_map["gemini"]["show_five_hour"] = False
        self.widget._refresh_compact_values()
        self.assertEqual(compact_value.text(), "49%")

    def test_expanded_bar_stacks_cli_rows_and_ring_arranges_tiles_side_by_side(self):
        self.usage.windows = [
            UsageWindow("5시간", 41, "8/12 09:49", 59),
            UsageWindow("주간", 12, "8/18 09:49", 88),
        ]
        self.widget.update_data([self.usage])
        self.app.processEvents()

        first, second = self.widget.provider_ui_map["codex"]["window_rows"]
        self.assertLess(first.geometry().top(), second.geometry().top())
        self.assertEqual(first.geometry().left(), second.geometry().left())

        self.widget._toggle_usage_view()
        self.app.processEvents()
        first, second = self.widget.provider_ui_map["codex"]["window_rows"]
        self.assertEqual(first.geometry().top(), second.geometry().top())
        self.assertLess(first.geometry().left(), second.geometry().left())

    def test_compact_bar_uses_white_normally_and_warning_colors_at_thresholds(self):
        self.widget.update_data([self.usage])
        self.widget.enter_compact_mode()
        self.app.processEvents()

        compact_value = self.widget.compact_ui_map["codex"]["value"]
        self.assertIn("color: #F8FAFC", compact_value.styleSheet())

        high_usage = ModelUsage("codex", "Codex", "Codex", 92, 100, "%")
        self.widget.update_data([high_usage])
        self.assertEqual(compact_value.text(), "92%")
        self.assertIn("color: #F38BA8", compact_value.styleSheet())

    def test_dock_above_taskbar_uses_the_bottom_of_available_geometry(self):
        self.widget.config_data["settings"]["dock_above_taskbar"] = True
        available = QRect(100, 80, 900, 600)
        self.widget.resize(300, 90)
        with patch.object(self.widget, "_available_geometry", return_value=available):
            self.widget._dock_above_taskbar_if_enabled()

        self.assertEqual(self.widget.frameGeometry().bottom(), available.bottom())

    def test_docked_widget_can_be_moved_away_from_the_bottom_edge(self):
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QMouseEvent

        self.widget.config_data["settings"]["dock_above_taskbar"] = True
        available = QRect(0, 0, 1000, 700)
        with patch.object(self.widget, "_available_geometry", return_value=available):
            self.widget._dock_above_taskbar_if_enabled()
            self.assertEqual(self.widget.frameGeometry().bottom(), available.bottom())

            # Drag the widget up near the top of the screen and release it.
            self.widget.move(300, 10)
            release = QMouseEvent(
                QEvent.Type.MouseButtonRelease,
                QPointF(0, 0),
                QPointF(300, 10),
                Qt.MouseButton.LeftButton,
                Qt.MouseButton.NoButton,
                Qt.KeyboardModifier.NoModifier,
            )
            self.widget.mouseReleaseEvent(release)
            self.assertFalse(self.widget._docked_to_bottom)
            self.assertLess(self.widget.frameGeometry().top(), 100)

            # A later usage refresh must not yank it back down.
            self.usage.windows = [
                UsageWindow("5시간", 41, "8/12 09:49", 59),
                UsageWindow("주간", 12, "8/18 09:49", 88),
            ]
            self.widget.update_data([self.usage])
            self.app.processEvents()
            self.assertLess(self.widget.frameGeometry().top(), 100)

    def test_docked_widget_keeps_bottom_edge_when_usage_rows_grow(self):
        self.widget.config_data["settings"]["dock_above_taskbar"] = True
        available = QRect(0, 0, 1000, 700)
        with patch.object(self.widget, "_available_geometry", return_value=available):
            self.widget._dock_above_taskbar_if_enabled()
            self.usage.windows = [
                UsageWindow("5시간", 41, "8/12 09:49", 59),
                UsageWindow("주간", 12, "8/18 09:49", 88),
            ]
            self.widget.update_data([self.usage])
            self.app.processEvents()

        self.assertEqual(self.widget.frameGeometry().bottom(), available.bottom())

    def test_legacy_size_setting_uses_responsive_minimum_and_compact_fits_content(self):
        widget = SynapCapWidget(
            {
                "settings": {
                    "widget_size": "Small",
                    "widget_width": 260,
                    "always_on_top": False,
                    "usage_view": "bar",
                }
            },
            [
                CodexProvider({"id": "codex", "name": "Codex"}),
                AntigravityProvider({"id": "gemini", "name": "Gemini"}),
                ClaudeProvider({"id": "claude", "name": "Claude"}),
            ],
        )
        widget.show()
        self.app.processEvents()
        self.assertEqual(widget.width(), 300)

        widget.enter_compact_mode()
        self.app.processEvents()

        self.assertLess(widget.width(), 300)
        self.assertGreaterEqual(
            widget.width(),
            widget.compact_bar.sizeHint().width()
            + widget.frame_layout.contentsMargins().left()
            + widget.frame_layout.contentsMargins().right(),
        )
        widget.exit_compact_mode()
        self.app.processEvents()
        self.assertEqual(widget.width(), 300)
        widget.close()
        widget.deleteLater()

    def test_responsive_font_width_survives_compact_round_trip(self):
        self.widget.rebuild_ui(
            {
                "settings": {
                    "always_on_top": False,
                    "usage_view": "bar",
                    "expanded_font_size": 18,
                }
            },
            [CodexProvider({"id": "codex", "name": "Codex"})],
            preserve_usage=False,
        )
        self.widget.update_data([self.usage])
        self.app.processEvents()
        expected_width = self.widget._expanded_width
        self.assertGreater(expected_width, 300)
        self.assertEqual(self.widget.width(), expected_width)

        self.widget.enter_compact_mode()
        self.app.processEvents()
        self.assertLess(self.widget.width(), expected_width)

        self.widget.exit_compact_mode()
        self.app.processEvents()

        self.assertEqual(self.widget.width(), expected_width)

        # A deferred Qt content-fit pass must not replace the responsive width
        # with a transient compact/content size hint.
        self.widget.setFixedWidth(300)
        self.widget._fit_to_content()
        self.assertEqual(self.widget.width(), expected_width)

    def test_root_frame_fills_large_window_after_view_and_compact_round_trips(self):
        providers: list[BaseAIProvider] = [
            CodexProvider({"id": "codex", "name": "Codex"}),
            AntigravityProvider({"id": "gemini", "name": "Gemini"}),
            ClaudeProvider({"id": "claude", "name": "Claude"}),
        ]
        usages = [
            ModelUsage(
                provider.provider_id,
                provider.name,
                provider.name,
                49,
                100,
                "%",
                windows=[
                    UsageWindow("5시간", 49, "8/27 18:00", 51),
                    UsageWindow("주간", 32, "9/1 09:00", 68),
                ],
            )
            for provider in providers
        ]
        self.widget.rebuild_ui(
            {
                "settings": {
                    "always_on_top": False,
                    "usage_view": "bar",
                    "expanded_font_size": 18,
                }
            },
            providers,
            preserve_usage=False,
        )
        self.widget.update_data(usages)
        self.app.processEvents()

        for action in (
            self.widget._toggle_usage_view,
            self.widget._toggle_usage_view,
            self.widget.enter_compact_mode,
            self.widget.exit_compact_mode,
        ):
            action()
            self.app.processEvents()

        self.widget._fit_to_content()
        self.app.processEvents()

        self.assertEqual(self.widget.width(), self.widget._expanded_width)
        self.assertEqual(self.widget.frame.width(), self.widget.width())
        self.assertEqual(
            self.widget.cards_frame.width(),
            self.widget.frame_layout.contentsRect().width(),
        )

    def test_compact_width_follows_visible_provider_count(self):
        provider_sets: list[list[BaseAIProvider]] = [
            [CodexProvider({"id": "codex", "name": "Codex"})],
            [
                CodexProvider({"id": "codex", "name": "Codex"}),
                AntigravityProvider({"id": "gemini", "name": "Gemini"}),
            ],
            [
                CodexProvider({"id": "codex", "name": "Codex"}),
                AntigravityProvider({"id": "gemini", "name": "Gemini"}),
                ClaudeProvider({"id": "claude", "name": "Claude"}),
            ],
        ]

        widths = []
        for providers in provider_sets:
            self.widget.rebuild_ui(
                self.widget.config_data,
                providers,
                preserve_usage=False,
            )
            self.widget.enter_compact_mode()
            self.app.processEvents()
            widths.append(self.widget.width())
            self.widget.exit_compact_mode()
            self.app.processEvents()

        self.assertLess(widths[0], widths[1])
        self.assertLess(widths[1], widths[2])
        self.assertEqual(self.widget.width(), 300)

    def test_compact_toggle_expands_downward_near_top_edge(self):
        available = self.widget.screen().availableGeometry()
        self.widget.move(available.left() + 64, available.top() + 64)
        self.app.processEvents()
        expanded_top_left = self.widget.frameGeometry().topLeft()

        self.widget.enter_compact_mode()
        self.app.processEvents()
        compact_top_left = self.widget.frameGeometry().topLeft()

        self.assertEqual(compact_top_left, expanded_top_left)

        self.widget.exit_compact_mode()
        self.app.processEvents()

        self.assertEqual(self.widget.frameGeometry().topLeft(), compact_top_left)
        self.assertGreaterEqual(self.widget.frameGeometry().top(), available.top())

    def test_compact_toggle_expands_upward_near_bottom_edge(self):
        available = self.widget.screen().availableGeometry()
        self.widget.move(
            available.right() - self.widget.width() - 64,
            available.bottom() - self.widget.height() - 64,
        )
        self.app.processEvents()
        expanded_bottom_right = self.widget.frameGeometry().bottomRight()

        self.widget.enter_compact_mode()
        self.app.processEvents()
        compact_bottom_right = self.widget.frameGeometry().bottomRight()

        self.assertEqual(compact_bottom_right, expanded_bottom_right)

        self.widget.exit_compact_mode()
        self.app.processEvents()

        self.assertEqual(self.widget.frameGeometry().bottomRight(), compact_bottom_right)
        self.assertLessEqual(self.widget.frameGeometry().bottom(), available.bottom())

    def test_expanding_from_compact_settles_before_the_next_event_cycle(self):
        available = self.widget.screen().availableGeometry()
        self.widget.config_data["settings"]["dock_above_taskbar"] = True
        self.widget._docked_to_bottom = True
        self.widget.move(
            available.right() - self.widget.width() - 40,
            available.bottom() - self.widget.height() + 1,
        )
        self.widget.enter_compact_mode()
        self.app.processEvents()

        self.widget.exit_compact_mode()

        self.assertFalse(self.widget._fit_timer.isActive())
        self.assertEqual(self.widget.frameGeometry().bottom(), available.bottom())

    def test_drag_release_snaps_widget_to_nearby_screen_edges(self):
        available = self.widget.screen().availableGeometry()
        self.widget.move(available.left() + 40, available.top() + 36)

        self.widget._snap_to_screen_edges()

        self.assertEqual(self.widget.frameGeometry().left(), available.left())
        self.assertEqual(self.widget.frameGeometry().top(), available.top())

    def test_resize_reapplies_edge_snap_without_leaving_a_gap(self):
        available = self.widget.screen().availableGeometry()
        self.widget.move(available.left() + 36, available.top() + 32)

        self.widget.enter_compact_mode()
        self.app.processEvents()
        self.widget.exit_compact_mode()
        self.app.processEvents()

        self.assertEqual(self.widget.frameGeometry().left(), available.left())
        self.assertEqual(self.widget.frameGeometry().top(), available.top())

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
        self.assertIn("5h", labels)
        reset_label = row.findChild(QLabel, "resetCountdown")
        self.assertIsNotNone(reset_label)
        assert reset_label is not None
        # Column is narrow, so the label is short but the tooltip is explicit.
        self.assertEqual(reset_label.text(), "미상")
        self.assertIn("알 수 없", reset_label.toolTip())
        self.assertGreaterEqual(reset_label.width(), reset_label.sizeHint().width())

    def test_stale_reset_shows_short_label_with_full_tooltip(self):
        self.widget.provider_ui_map["codex"]["show_five_hour"] = True
        self.usage.windows = [UsageWindow("5시간", 40, "8/12 13:00", 60)]
        self.widget.update_data([self.usage])

        reset_label = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(
            QLabel, "resetCountdown"
        )
        self.assertIsNotNone(reset_label)
        assert reset_label is not None
        self.assertEqual(reset_label.text(), "확인 중")
        self.assertIn("8/12 13:00", reset_label.toolTip())
        self.assertGreaterEqual(reset_label.width(), reset_label.sizeHint().width())

    def test_visual_rebuild_reuses_latest_usage(self):
        self.widget.update_data([self.usage])
        new_config = {
            "settings": {
                "widget_size": "Large",
                "widget_width": 350,
                "always_on_top": False,
                "usage_view": "bar",
                "expanded_font_size": 16,
                "expanded_font_bold": False,
                "compact_font_size": 14,
                "compact_font_bold": False,
            }
        }

        self.widget.rebuild_ui(
            new_config,
            [CodexProvider({"id": "codex", "name": "Codex"})],
        )

        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        value_label = next(
            label for label in row.findChildren(QLabel) if label.text().endswith("%")
        )
        self.assertEqual(value_label.font().pointSize(), 16)
        self.assertEqual(value_label.font().weight(), 400)

    def test_large_independent_fonts_resize_rows_bars_and_compact_width(self):
        config = {
            "settings": {
                "widget_size": "Medium",
                "always_on_top": False,
                "usage_view": "bar",
                "expanded_font_size": 18,
                "expanded_font_bold": True,
                "compact_font_size": 16,
                "compact_font_bold": False,
            }
        }
        self.widget.rebuild_ui(
            config,
            [CodexProvider({"id": "codex", "name": "Codex"})],
            preserve_usage=False,
        )
        self.widget.update_data([self.usage])
        self.app.processEvents()

        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        usage_bar = row.findChild(UsageBar)
        self.assertIsNotNone(usage_bar)
        assert usage_bar is not None
        self.assertGreaterEqual(usage_bar.height(), 18)
        value_label = next(
            label for label in row.findChildren(QLabel) if label.text().endswith("%")
        )
        self.assertEqual(value_label.font().pointSize(), 18)
        self.assertGreaterEqual(self.widget.width(), 300)

        self.widget.enter_compact_mode()
        self.app.processEvents()
        compact_value = self.widget.compact_ui_map["codex"]["value"]
        self.assertEqual(compact_value.font().pointSize(), 16)
        self.assertEqual(compact_value.font().weight(), 400)
        self.assertGreaterEqual(compact_value.width(), compact_value.sizeHint().width())
        self.assertGreaterEqual(self.widget.frame.height(), compact_value.sizeHint().height() + 16)

    def test_max_compact_font_fits_three_providers_without_clipping(self):
        providers: list[BaseAIProvider] = [
            CodexProvider({"id": "codex", "name": "Codex"}),
            AntigravityProvider(
                {
                    "id": "gemini",
                    "name": "Gemini",
                    "show_five_hour": True,
                    "show_weekly": True,
                }
            ),
            ClaudeProvider(
                {
                    "id": "claude",
                    "name": "Claude",
                    "show_five_hour": True,
                    "show_weekly": True,
                }
            ),
        ]
        config = {
            "settings": {
                "widget_size": "Medium",
                "always_on_top": False,
                "usage_view": "bar",
                "expanded_font_size": 13,
                "expanded_font_bold": True,
                "compact_font_size": 16,
                "compact_font_bold": True,
            }
        }
        self.widget.rebuild_ui(config, providers, preserve_usage=False)
        self.widget.update_data(
            [
                self.usage,
                ModelUsage(
                    "gemini",
                    "Gemini",
                    "Gemini",
                    49,
                    100,
                    "%",
                    windows=[
                        UsageWindow("5시간", 25, "", 75),
                        UsageWindow("주간", 49, "", 51),
                    ],
                ),
                ModelUsage(
                    "claude",
                    "Claude",
                    "Claude",
                    46,
                    100,
                    "%",
                    windows=[
                        UsageWindow("5시간", 46, "", 54),
                        UsageWindow("주간", 12, "", 88),
                    ],
                ),
            ]
        )
        self.widget.enter_compact_mode()
        self.app.processEvents()

        for compact_ui in self.widget.compact_ui_map.values():
            value = compact_ui["value"]
            self.assertGreaterEqual(value.width(), value.sizeHint().width())
        self.assertGreaterEqual(
            self.widget.width(),
            self.widget.compact_bar.sizeHint().width()
            + self.widget.frame_layout.contentsMargins().left()
            + self.widget.frame_layout.contentsMargins().right(),
        )

    def test_first_compact_load_reflows_from_spinners_to_values(self):
        providers: list[BaseAIProvider] = [
            CodexProvider({"id": "codex", "name": "Codex"}),
            AntigravityProvider(
                {
                    "id": "gemini",
                    "name": "Gemini",
                    "show_five_hour": True,
                    "show_weekly": True,
                }
            ),
            ClaudeProvider(
                {
                    "id": "claude",
                    "name": "Claude",
                    "show_five_hour": True,
                    "show_weekly": True,
                }
            ),
        ]
        self.widget.rebuild_ui(
            {
                "settings": {
                    "widget_size": "Medium",
                    "always_on_top": False,
                    "usage_view": "bar",
                    "expanded_font_size": 13,
                    "expanded_font_bold": True,
                    "compact_font_size": 12,
                    "compact_font_bold": True,
                }
            },
            providers,
            preserve_usage=False,
        )
        self.widget.enter_compact_mode()
        self.widget.set_loading()
        self.app.processEvents()
        loading_width = self.widget.width()

        self.widget.update_data(
            [
                self.usage,
                ModelUsage(
                    "gemini",
                    "Gemini",
                    "Gemini",
                    59,
                    100,
                    "%",
                    windows=[
                        UsageWindow("5시간", 59, "", 41),
                        UsageWindow("주간", 10, "", 90),
                    ],
                ),
                ModelUsage(
                    "claude",
                    "Claude",
                    "Claude",
                    51,
                    100,
                    "%",
                    windows=[
                        UsageWindow("5시간", 51, "", 49),
                        UsageWindow("주간", 13, "", 87),
                    ],
                ),
            ]
        )
        self.app.processEvents()

        self.assertGreater(self.widget.width(), loading_width)
        for compact_ui in self.widget.compact_ui_map.values():
            value = compact_ui["value"]
            self.assertTrue(value.isVisible())
            self.assertGreaterEqual(value.width(), value.sizeHint().width())
        self.assertGreaterEqual(
            self.widget.width(),
            self.widget.compact_bar.sizeHint().width()
            + self.widget.frame_layout.contentsMargins().left()
            + self.widget.frame_layout.contentsMargins().right(),
        )

    def test_rebuild_shrinks_after_provider_is_removed(self):
        providers: list[BaseAIProvider] = [
            CodexProvider({"id": provider_id, "name": provider_id.title()})
            for provider_id in ("first", "second", "third")
        ]
        self.widget.rebuild_ui(
            self.widget.config_data,
            providers,
            preserve_usage=False,
        )
        self.app.processEvents()
        expanded_height = self.widget.height()

        self.widget.rebuild_ui(
            self.widget.config_data,
            providers[:2],
            preserve_usage=False,
        )
        self.app.processEvents()

        self.assertLess(self.widget.height(), expanded_height)
        self.assertEqual(self.widget.cards_layout.count(), 3)


if __name__ == "__main__":
    unittest.main()
