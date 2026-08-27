import os
import unittest
from datetime import UTC, datetime
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtWidgets import QApplication, QLabel, QProgressBar

from providers import (
    AntigravityProvider,
    BaseAIProvider,
    ClaudeProvider,
    CodexProvider,
    ModelUsage,
    UsageWindow,
)
from ui.widget import SIZE_PRESETS, SynapCapWidget, UsageRing
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

    def test_bar_and_ring_views_can_be_toggled(self):
        self.widget.update_data([self.usage])
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        labels = [label.text() for label in row.findChildren(QLabel)]

        self.assertIn("49%", labels)
        self.assertNotIn("사용 49%", labels)
        self.assertEqual(len(row.findChildren(QProgressBar)), 1)
        usage_label = next(label for label in row.findChildren(QLabel) if label.text() == "49%")
        self.assertIn("font-weight: 700", usage_label.styleSheet())

        self.widget._toggle_usage_view()
        self.app.processEvents()
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]

        self.assertEqual(self.widget.usage_view, "ring")
        rings = row.findChildren(UsageRing)
        self.assertEqual(len(rings), 1)
        self.assertEqual(rings[0].value_text, "49%")
        self.assertEqual(len(self.widget.findChildren(QProgressBar)), 0)
        self.assertEqual(self.widget.config_data["settings"]["usage_view"], "ring")

        self.widget._toggle_usage_view()
        self.app.processEvents()
        self.assertEqual(self.widget.usage_view, "bar")
        self.assertEqual(len(self.widget.findChildren(UsageRing)), 0)

    def test_codex_defaults_to_five_hour_and_weekly_windows(self):
        self.usage.windows = [
            UsageWindow("5시간", 38, "8/26 14:07", 62),
            UsageWindow("주간", 6, "9/2 09:07", 94),
        ]

        self.widget.update_data([self.usage])

        rows = self.widget.provider_ui_map["codex"]["window_rows"]
        self.assertEqual(len(rows), 2)
        labels = [
            label.text()
            for row in rows
            for label in row.findChildren(QLabel)
        ]
        self.assertIn("38%", labels)
        self.assertIn("6%", labels)

    def test_usage_value_bold_can_be_disabled(self):
        self.widget.config_data["settings"]["expanded_font_bold"] = False
        self.widget.update_data([self.usage])

        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        usage_label = next(label for label in row.findChildren(QLabel) if label.text() == "49%")
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
            self.widget.eventFilter(progress, QEvent(QEvent.Type.Enter))

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
        progress = ui["window_rows"][0].findChild(QProgressBar)
        self.assertIn("Claude CLI 기준 사용량", progress.toolTip())

        self.widget.enter_compact_mode()
        compact_tooltip = self.widget.compact_ui_map["claude"]["value"].toolTip()
        self.assertIn("마지막 조회: 8/14 13:20:30", compact_tooltip)
        self.assertTrue(
            self.widget.compact_ui_map["claude"]["value"].property("instantTooltip")
        )

    def test_instant_tooltip_is_anchored_below_hovered_widget(self):
        expected_position = self.widget.version_btn.mapToGlobal(
            QPoint(0, self.widget.version_btn.height() + 4)
        )

        with patch("ui.widget.QToolTip.showText") as show_text:
            self.widget.eventFilter(self.widget.version_btn, QEvent(QEvent.Type.Enter))

        self.assertEqual(show_text.call_args.args[0], expected_position)
        self.assertEqual(show_text.call_args.args[1], f"현재 버전 v{APP_VERSION}")

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
        self.assertEqual(compact_value.text(), "49%")
        self.assertIn("Codex", compact_value.toolTip())
        self.assertIn("font-size: 12px", compact_value.styleSheet())
        self.assertEqual(self.widget.compact_logo.size().width(), 20)
        self.assertEqual(self.widget.expand_btn.height(), 26)
        self.assertGreaterEqual(self.widget.frame.height(), 40)
        self.assertIn("border: 1px solid #585B70", self.widget.frame.styleSheet())

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
        self.assertEqual(compact_value.text(), "15%/49%")
        self.assertGreaterEqual(compact_value.width(), compact_value.sizeHint().width())
        self.assertIn("5시간 15% 사용", compact_value.toolTip())
        self.assertIn("주간 49% 사용", compact_value.toolTip())

        self.widget.provider_ui_map["gemini"]["show_five_hour"] = False
        self.widget._refresh_compact_values()
        self.assertEqual(compact_value.text(), "49%")

    def test_small_preset_uses_300px_minimum_and_compact_fits_content(self):
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

    def test_large_preset_width_survives_compact_round_trip(self):
        self.widget.rebuild_ui(
            {
                "settings": {
                    "widget_size": "Large",
                    "always_on_top": False,
                    "usage_view": "bar",
                }
            },
            [CodexProvider({"id": "codex", "name": "Codex"})],
            preserve_usage=False,
        )
        self.widget.update_data([self.usage])
        self.app.processEvents()
        expected_width = SIZE_PRESETS["Large"]["width"]
        self.assertEqual(self.widget.width(), expected_width)

        self.widget.enter_compact_mode()
        self.app.processEvents()
        self.assertLess(self.widget.width(), expected_width)

        self.widget.exit_compact_mode()
        self.app.processEvents()

        self.assertEqual(self.widget.width(), expected_width)

        # A deferred Qt content-fit pass must not replace the selected Large
        # width with a transient compact/content size hint.
        self.widget.setFixedWidth(SIZE_PRESETS["Medium"]["width"])
        self.widget._fit_to_content()
        self.assertEqual(self.widget.width(), expected_width)

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
        self.assertIn("5시간 · 리셋 시각 미상", labels)

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
        usage_label = next(label for label in row.findChildren(QLabel) if label.text() == "49%")
        self.assertIn("font-size: 16px", usage_label.styleSheet())
        self.assertIn("font-weight: 400", usage_label.styleSheet())

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
        usage_label = next(label for label in row.findChildren(QLabel) if label.text() == "49%")
        progress = row.findChild(QProgressBar)
        self.assertIn("font-size: 18px", usage_label.styleSheet())
        self.assertGreaterEqual(progress.height(), 13)
        self.assertGreaterEqual(self.widget.width(), 360)

        self.widget.enter_compact_mode()
        self.app.processEvents()
        compact_value = self.widget.compact_ui_map["codex"]["value"]
        self.assertIn("font-size: 16px", compact_value.styleSheet())
        self.assertIn("font-weight: 400", compact_value.styleSheet())
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
