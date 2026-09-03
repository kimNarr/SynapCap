import os
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint, QRect, Qt
from PySide6.QtGui import QFont, QFontInfo, QFontMetrics, QPalette
from PySide6.QtWidgets import QApplication, QLabel, QToolTip, QWidget

from providers import (
    AntigravityProvider,
    BaseAIProvider,
    ClaudeProvider,
    CodexProvider,
    ModelUsage,
    UsageWindow,
)
from theme import apply_theme_setting, t
from ui.widget import (
    COMPACT_BOTTOM_SAFE_GAP,
    FIXED_WIDGET_WIDTH,
    TOOLTIP_CONTROL_GAP,
    FocusProviderButton,
    SynapCapWidget,
    UsageRing,
)
from version import APP_VERSION


class WidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        apply_theme_setting("dark")
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
        apply_theme_setting("dark")

    def test_reset_time_is_presented_relatively(self):
        relative, tooltip = self.widget._reset_presentation(
            "8/12 09:49",
            now=datetime(2026, 8, 10, 17, 0, tzinfo=UTC),
        )

        self.assertEqual(relative, "1일 16시간 후")
        self.assertEqual(tooltip, "8/12 09:49 초기화")

    def test_expanded_header_uses_horizontal_wordmark(self):
        self.assertTrue(hasattr(self.widget, "header_logo"))
        self.assertFalse(self.widget.header_logo.pixmap().isNull())
        self.assertEqual(self.widget.header_logo.size().width(), 20)
        self.assertEqual(self.widget.header_logo.size().height(), 20)
        self.assertTrue(hasattr(self.widget, "wordmark_label"))
        self.assertFalse(self.widget.wordmark_label.pixmap().isNull())
        self.assertEqual(self.widget.wordmark_label.size().width(), 92)
        self.assertEqual(self.widget.wordmark_label.size().height(), 28)
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

    def test_expanded_usage_uses_one_ring_shape(self):
        self.widget.update_data([self.usage])
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        ring = row.findChild(UsageRing)
        self.assertIsNotNone(ring)
        assert ring is not None
        self.assertEqual(ring.value_text, "49%")
        self.assertEqual(ring.center_caption, "")
        period_badge = row.findChild(QLabel, "windowBadge")
        self.assertIsNotNone(period_badge)
        assert period_badge is not None
        self.assertEqual(period_badge.text(), "WEEKLY")
        self.assertEqual(period_badge.alignment(), Qt.AlignmentFlag.AlignCenter)

        self.assertEqual(self.widget.usage_view, "ring")
        self.assertEqual(len(row.findChildren(UsageRing)), 1)
        self.assertTrue(self.widget._horizontal_ring_active)

    def test_legacy_bar_setting_is_normalized_to_ring(self):
        self.usage.windows = [UsageWindow("5시간", 1, "8/12 09:49", 99)]
        self.widget.update_data([self.usage], force=True)
        self.app.processEvents()

        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        self.assertIsNotNone(row.findChild(UsageRing))
        self.assertEqual(self.widget.usage_view, "ring")

    def test_legacy_segment_setting_is_normalized_to_ring(self):
        self.widget.config_data["settings"]["usage_view"] = "segment"
        self.widget.rebuild_ui(self.widget.config_data, self.widget.providers)
        self.widget.update_data([self.usage], force=True)
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        self.assertIsNotNone(row.findChild(UsageRing))

    def test_usage_scale_has_four_tiers_with_a_muted_low_end(self):
        self.assertEqual(self.widget._usage_color(10), "#8087A0")  # calm
        self.assertEqual(self.widget._usage_color(65), "#89B4FA")  # notice
        self.assertEqual(self.widget._usage_color(80), "#FAB387")  # warn
        self.assertEqual(self.widget._usage_color(92), "#F38BA8")  # crit

    def test_warning_and_critical_values_keep_ring_severity_colours(self):
        self.usage.windows = [UsageWindow("5시간", 65, "8/12 09:49", 35)]
        self.widget.update_data([self.usage], force=True)
        ring = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(UsageRing)
        assert ring is not None
        self.assertEqual(ring.color.name(), "#89b4fa")

        self.usage.windows = [UsageWindow("5시간", 78, "8/12 09:49", 22)]
        self.widget.update_data([self.usage], force=True)
        ring = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(UsageRing)
        assert ring is not None
        self.assertEqual(ring.color.name(), "#fab387")

        self.usage.windows = [UsageWindow("5시간", 92, "8/12 09:49", 8)]
        self.widget.update_data([self.usage], force=True)
        ring = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(UsageRing)
        assert ring is not None
        self.assertEqual(ring.color.name(), "#f38ba8")

    def test_focus_ring_reset_countdown_is_dim_secondary_metadata(self):
        self.widget.update_data([self.usage])
        reset_label = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(
            QLabel, "resetCountdown"
        )

        assert reset_label is not None
        # Dim + regular weight so the ring's % stays the headline.
        self.assertIn(f"color: {t('ink_dim')}", reset_label.styleSheet())
        self.assertEqual(reset_label.font().weight(), 400)
        preset = self.widget._expanded_preset(self.widget.config_data["settings"])
        self.assertEqual(
            reset_label.font().pointSize(),
            max(9, preset["val_size"] - 2),
        )

    def test_codex_defaults_to_five_hour_and_weekly_windows(self):
        self.usage.windows = [
            UsageWindow("5시간", 38, "8/26 14:07", 62),
            UsageWindow("주간", 6, "9/2 09:07", 94),
        ]

        self.widget.update_data([self.usage])

        rows = self.widget.provider_ui_map["codex"]["window_rows"]
        self.assertEqual(len(rows), 2)
        values = [row.findChild(UsageRing).value_text for row in rows]
        self.assertEqual(values, ["38%", "6%"])

    def test_fixed_expanded_rings_use_bold_values(self):
        self.widget.update_data([self.usage])

        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        ring = row.findChild(UsageRing)
        assert ring is not None
        self.assertTrue(ring.bold)

    def test_compact_uses_a_fixed_medium_baseline_weight(self):
        self.widget.update_data([self.usage])
        self.widget.enter_compact_mode()
        self.app.processEvents()

        compact_value = self.widget.compact_ui_map["codex"]["value"]
        self.assertEqual(compact_value.font().weight(), 500)

    def test_expanded_widget_uses_fixed_width(self):
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

        self.assertEqual(self.widget.width(), FIXED_WIDGET_WIDTH)
        self.assertEqual(self.widget._expanded_preset({"widget_scale": "medium"})["val_size"], 11)

    def test_missing_cli_reads_as_dormant_not_an_alarm(self):
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

        ui = self.widget.provider_ui_map["codex"]
        status = ui["status"]
        self.assertEqual(status.text(), "미설치")
        self.assertIn(usage.error, status.toolTip())
        self.assertIn("진단 정보 보기", status.toolTip())
        self.assertIn("설정에서 숨길 수 있습니다", status.toolTip())
        # Dormant styling: grey badge, dimmed provider name — not the red alarm.
        self.assertIn(t("ink_dim"), status.styleSheet())
        self.assertNotIn(t("danger"), status.styleSheet())
        self.assertIn(t("ink_dim"), ui["name"].styleSheet())

    def test_login_required_stays_an_actionable_error(self):
        self.widget.update_data(
            [
                ModelUsage(
                    "codex", "Codex", "Codex", 0, 100, "%",
                    error="codex 로그인이 필요합니다",
                )
            ]
        )
        ui = self.widget.provider_ui_map["codex"]
        self.assertEqual(ui["status"].text(), "로그인 필요")
        self.assertIn(t("danger"), ui["status"].styleSheet())
        self.assertIn(t("ink"), ui["name"].styleSheet())

    def test_ring_tooltip_is_shown_on_enter(self):
        self.widget.update_data([self.usage])
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        usage_ring = row.findChild(UsageRing)
        self.assertIsNotNone(usage_ring)
        assert usage_ring is not None

        self.assertEqual(usage_ring.toolTip(), "49% 사용 · 51% 남음")
        with patch("ui.widget.QToolTip.showText") as show_text:
            self.widget.eventFilter(usage_ring, QEvent(QEvent.Type.Enter))

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
        usage_ring = ui["window_rows"][0].findChild(UsageRing)
        self.assertIsNotNone(usage_ring)
        assert usage_ring is not None
        self.assertIn("Claude CLI 기준 사용량", usage_ring.toolTip())

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

    def test_freshness_caption_reads_fresh_then_stale(self):
        base = datetime(2026, 8, 27, 8, 0, tzinfo=UTC)
        self.assertEqual(
            self.widget._freshness_caption(base, 30, now=base + timedelta(seconds=10)),
            "방금 갱신됨",
        )
        self.assertEqual(
            self.widget._freshness_caption(base, 30, now=base + timedelta(minutes=2)),
            "2분 전 갱신",
        )
        self.assertIn(
            "새로고침 권장",
            self.widget._freshness_caption(base, 30, now=base + timedelta(minutes=15)),
        )

    def test_focus_ring_moves_freshness_caption_to_refresh_tooltip(self):
        self.usage.fetched_at = datetime.now().astimezone() - timedelta(minutes=3)
        self.widget.update_data([self.usage], force=True)
        self.app.processEvents()

        self.assertTrue(self.widget._horizontal_ring_active)
        self.assertFalse(self.widget.freshness_label.isVisible())
        self.assertIn("분 전 갱신", self.widget.refresh_btn.toolTip())

        self.widget.enter_compact_mode()
        self.app.processEvents()
        self.assertFalse(self.widget.freshness_label.isVisible())

    def test_focus_ring_has_no_legacy_column_header(self):
        providers = [
            CodexProvider({"id": "codex", "name": "Codex"}),
            AntigravityProvider({"id": "gemini", "name": "Gemini"}),
        ]
        self.widget.rebuild_ui(
            self.widget.config_data, providers, preserve_usage=False
        )
        self.widget.update_data(
            [
                ModelUsage(
                    "codex", "Codex", "Codex", 49, 100, "%",
                    windows=[UsageWindow("주간", 49, "8/12 09:49", 51)],
                ),
                ModelUsage(
                    "gemini", "Gemini", "Gemini", 20, 100, "%",
                    windows=[UsageWindow("주간", 20, "", 80)],
                ),
            ],
            force=True,
        )
        self.app.processEvents()

        self.assertTrue(self.widget._horizontal_ring_active)
        self.assertEqual(self.widget.focus_provider_buttons.keys(), {"codex", "gemini"})
        self.assertEqual(
            self.widget.provider_ui_map["codex"]["card"].findChildren(
                QLabel, "usageColumnHeader"
            ),
            [],
        )

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

    def test_instant_tooltip_is_anchored_near_hovered_widget(self):
        expected_position = self.widget.version_btn.mapToGlobal(
            QPoint(0, max(0, self.widget.version_btn.height() - 10))
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
        tooltip_lines = 3
        tooltip_height = (
            QFontMetrics(QToolTip.font()).lineSpacing() * tooltip_lines
        ) + 16
        self.assertGreaterEqual(
            watched.mapToGlobal(QPoint(0, 0)).y()
            - (position.y() + tooltip_height),
            TOOLTIP_CONTROL_GAP,
        )

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
        self.assertIn("background: transparent", self.widget.version_btn.styleSheet())
        self.assertIn("border: none", self.widget.version_btn.styleSheet())
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
        self.assertEqual(self.widget.version_btn.height(), 18)
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

    def test_window_controls_are_split_off_from_app_actions(self):
        header_children = self.widget.header_widget.children()
        self.assertIn(self.widget.header_control_divider, header_children)
        self.assertEqual(self.widget.header_control_divider.width(), 1)
        self.assertFalse(hasattr(self.widget, "compact_control_divider"))
        self.assertFalse(hasattr(self.widget, "compact_logo_divider"))

    def test_header_has_no_graph_view_toggle(self):
        # The graph shape is chosen in Settings; the cryptic header cycle button
        # is gone.
        self.assertFalse(hasattr(self.widget, "view_btn"))
        self.assertFalse(hasattr(self.widget, "_toggle_usage_view"))

    def test_fixed_widget_always_uses_the_ring_view(self):
        self.widget.update_data([self.usage])
        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        self.assertEqual(len(row.findChildren(UsageRing)), 1)

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

    def test_window_modes_switch_between_expanded_bar_and_tray_only(self):
        self.widget.set_window_mode("bar")
        self.app.processEvents()
        self.assertEqual(self.widget.window_mode(), "bar")
        self.assertTrue(self.widget.is_compact)
        self.assertTrue(self.widget.isVisible())

        self.widget.set_window_mode("none")
        self.app.processEvents()
        self.assertEqual(self.widget.window_mode(), "none")
        self.assertFalse(self.widget.isVisible())

        self.widget.set_window_mode("expanded")
        self.app.processEvents()
        self.assertEqual(self.widget.window_mode(), "expanded")
        self.assertFalse(self.widget.is_compact)
        self.assertTrue(self.widget.isVisible())

    def test_header_controls_request_the_visible_window_modes(self):
        requested = []
        self.widget.window_mode_requested.connect(
            lambda mode, restore_position: requested.append(
                (mode, restore_position)
            )
        )

        self.widget.minimize_btn.click()
        self.widget.expand_btn.click()

        self.assertEqual(
            requested,
            [("bar", False), ("expanded", False)],
        )

    def test_compact_bar_shows_latest_provider_usage(self):
        self.widget.update_data([self.usage])
        self.widget.enter_compact_mode()
        self.app.processEvents()

        compact_value = self.widget.compact_ui_map["codex"]["value"]
        compact_item = self.widget.compact_ui_map["codex"]["item"]
        self.assertEqual(compact_value.text(), "49%")
        self.assertIn("Codex", compact_item.toolTip())
        self.assertEqual(compact_value.font().pointSize(), 10)
        self.assertIn("color: #F8FAFC", compact_value.styleSheet())
        self.assertEqual(self.widget.compact_logo.size().width(), 17)
        self.assertEqual(self.widget.expand_btn.height(), 20)
        self.assertLess(self.widget.frame.height(), 50)
        self.assertTrue(self.widget.frame.property("compactMode"))
        self.assertIn("border: 2px solid #4A5266", self.widget.frame.styleSheet())
        self.assertIn("QFrame#rootFrame", self.widget.frame.styleSheet())
        self.assertIn("border-radius: 6px", self.widget.frame.styleSheet())

    def test_compact_bar_uses_flat_provider_groups(self):
        providers = [
            CodexProvider({"id": "codex", "name": "Codex"}),
            AntigravityProvider({"id": "gemini", "name": "Gemini"}),
            ClaudeProvider({"id": "claude", "name": "Claude"}),
        ]
        self.widget.rebuild_ui(
            self.widget.config_data, providers, preserve_usage=False
        )
        self.widget.enter_compact_mode()
        self.app.processEvents()

        layout = self.widget.compact_items_layout
        items = [
            layout.itemAt(index).widget()
            for index in range(layout.count())
            if layout.itemAt(index).widget() is not None
        ]
        self.assertEqual(len(items), 3)
        self.assertTrue(
            all(item.objectName() == "compactProviderGroup" for item in items)
        )
        self.assertIn("QWidget#compactProviderGroup", self.widget.frame.styleSheet())
        self.assertTrue(
            all(item.layout().contentsMargins().left() >= 4 for item in items)
        )
        self.assertTrue(
            all(item.layout().contentsMargins().top() >= 3 for item in items)
        )

    def test_light_theme_tooltip_palette_has_readable_text_and_background(self):
        apply_theme_setting("light")
        self.widget.apply_theme()

        tooltip_palette = QToolTip.palette()
        self.assertEqual(
            tooltip_palette.color(QPalette.ColorRole.ToolTipBase).name(),
            "#171a21",
        )
        self.assertEqual(
            tooltip_palette.color(QPalette.ColorRole.ToolTipText).name(),
            "#f8fafc",
        )

    def test_compact_bar_uses_one_percent_suffix_for_two_windows(self):
        provider = AntigravityProvider(
            {
                "id": "gemini",
                "name": "Gemini",
                "show_five_hour": True,
                "show_weekly": True,
            }
        )
        self.widget.rebuild_ui(
            self.widget.config_data, [provider], preserve_usage=False
        )
        self.widget.update_data(
            [
                ModelUsage(
                    "gemini",
                    "Gemini",
                    "Gemini",
                    72,
                    100,
                    "%",
                    windows=[
                        UsageWindow("5시간", 8, "", 92),
                        UsageWindow("주간", 72, "", 28),
                    ],
                )
            ]
        )
        self.widget.enter_compact_mode()
        self.app.processEvents()

        compact_value = self.widget.compact_ui_map["gemini"]["value"]
        self.assertEqual(compact_value.property("compactPlainText"), "8 / 72%")
        self.assertEqual(compact_value.text().count("%"), 1)

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
        self.assertEqual(compact_value.text(), "15 / 49%")
        self.assertGreaterEqual(compact_value.width(), compact_value.font().pointSize() * 3)
        self.assertIn("5시간 15% 사용", compact_item.toolTip())
        self.assertIn("주간 49% 사용", compact_item.toolTip())

        self.widget.provider_ui_map["gemini"]["show_five_hour"] = False
        self.widget._refresh_compact_values()
        self.assertEqual(compact_value.text(), "49%")

    def test_fixed_focus_ring_places_window_tiles_side_by_side(self):
        self.usage.windows = [
            UsageWindow("5시간", 41, "8/12 09:49", 59),
            UsageWindow("주간", 12, "8/18 09:49", 88),
        ]
        self.widget.rebuild_ui(self.widget.config_data, self.widget.providers)
        self.widget.update_data([self.usage], force=True)
        self.app.processEvents()

        first, second = self.widget.provider_ui_map["codex"]["window_rows"]
        self.assertEqual(first.geometry().top(), second.geometry().top())
        self.assertLess(first.geometry().left(), second.geometry().left())
        resets = [tile.findChild(QLabel, "resetCountdown") for tile in (first, second)]
        self.assertEqual(
            resets[0].mapTo(first, resets[0].rect().topLeft()).x(),
            resets[1].mapTo(second, resets[1].rect().topLeft()).x(),
        )
        self.assertEqual(resets[0].width(), resets[1].width())
        self.assertTrue(all(tile.findChild(UsageRing) for tile in (first, second)))

    def test_horizontal_ring_layout_focuses_one_provider_with_two_large_rings(self):
        providers: list[BaseAIProvider] = [
            CodexProvider({"id": "codex", "name": "Codex"}),
            AntigravityProvider({"id": "gemini", "name": "Gemini"}),
            ClaudeProvider({"id": "claude", "name": "Claude"}),
        ]
        config = {
            "settings": {
                "widget_scale": "medium",
                "always_on_top": False,
                "usage_view": "ring",
                "ring_layout": "horizontal",
            }
        }

        with patch.object(
            self.widget,
            "_available_geometry",
            return_value=QRect(0, 0, 1400, 900),
        ):
            self.widget.rebuild_ui(config, providers, preserve_usage=False)
            self.widget.update_data(
                [
                    ModelUsage(
                        "codex",
                        "Codex",
                        "Codex",
                        34,
                        100,
                        "%",
                        windows=[
                            UsageWindow("5시간", 34, "2h 28m", 66),
                            UsageWindow("주간", 26, "5d 22h", 74),
                        ],
                    ),
                    ModelUsage(
                        "gemini",
                        "Gemini",
                        "Gemini",
                        68,
                        100,
                        "%",
                        windows=[
                            UsageWindow("5시간", 68, "2h 35m", 32),
                            UsageWindow("주간", 69, "21h 13m", 31),
                        ],
                    ),
                    ModelUsage(
                        "claude",
                        "Claude",
                        "Claude",
                        94,
                        100,
                        "%",
                        windows=[
                            UsageWindow("5시간", 94, "2h 24m", 6),
                            UsageWindow("주간", 65, "15h 24m", 35),
                        ],
                    ),
                ],
                force=True,
            )
            self.app.processEvents()

        self.assertTrue(self.widget._horizontal_ring_active)
        self.assertEqual(set(self.widget.focus_provider_buttons), {
            "codex", "gemini", "claude"
        })
        self.assertTrue(
            all(
                isinstance(button, FocusProviderButton)
                for button in self.widget.focus_provider_buttons.values()
            )
        )
        codex_tab = self.widget.focus_provider_buttons["codex"]
        self.assertLess(codex_tab.title_size, codex_tab.summary_size)
        for button in self.widget.focus_provider_buttons.values():
            summary_font = QFont("Segoe UI")
            summary_font.setPixelSize(button.summary_size)
            summary_font.setWeight(QFont.Weight.DemiBold)
            available_summary_width = button.width() - (9 + 22 + 8) - 7
            # The offscreen Qt backend used by tests cannot resolve Windows
            # fonts. Segoe UI 11 px DemiBold measures 55 px on Windows.
            required_summary_width = (
                QFontMetrics(summary_font).horizontalAdvance("100 / 100%")
                if QFontInfo(summary_font).family()
                else 55
            )
            self.assertGreaterEqual(
                available_summary_width,
                required_summary_width,
            )
        self.assertIn(
            "34 / 26%", self.widget.focus_provider_buttons["codex"].text()
        )
        self.assertTrue(self.widget.provider_ui_map["codex"]["name"].isHidden())
        title_container = self.widget.provider_ui_map["codex"]["title_container"]
        self.assertTrue(title_container.isHidden())
        self.assertIs(
            self.widget.provider_ui_map["codex"]["status"].parentWidget(),
            title_container,
        )
        self.assertFalse(self.widget.provider_ui_map["codex"]["card"].isHidden())
        self.assertTrue(self.widget.provider_ui_map["gemini"]["card"].isHidden())
        self.assertTrue(self.widget.provider_ui_map["claude"]["card"].isHidden())
        rings = self.widget.provider_ui_map["codex"]["card"].findChildren(
            UsageRing
        )
        self.assertEqual(len(rings), 2)
        self.assertTrue(all(ring.emphasized for ring in rings))
        self.assertTrue(all(ring.ring_size >= 96 for ring in rings))
        self.assertEqual({ring.center_caption for ring in rings}, {""})
        labels = [
            tile.findChild(QLabel, "windowBadge").text()
            for tile in self.widget.provider_ui_map["codex"]["window_rows"]
        ]
        self.assertEqual(labels, ["SESSION", "WEEKLY"])
        first, second = self.widget.provider_ui_map["codex"]["window_rows"]
        self.assertEqual(first.geometry().top(), second.geometry().top())
        self.assertLess(self.widget.width(), 600)

        self.widget.focus_provider_buttons["gemini"].click()
        self.app.processEvents()
        self.assertEqual(self.widget._focused_provider_id, "gemini")
        self.assertTrue(self.widget.provider_ui_map["codex"]["card"].isHidden())
        self.assertFalse(self.widget.provider_ui_map["gemini"]["card"].isHidden())

        with patch.object(
            self.widget,
            "_available_geometry",
            return_value=QRect(0, 0, 1400, 900),
        ):
            self.widget.rebuild_ui(config, providers)
            self.app.processEvents()
        self.assertEqual(self.widget._focused_provider_id, "gemini")
        self.assertTrue(self.widget.focus_provider_buttons["gemini"].isChecked())
        self.assertFalse(self.widget.provider_ui_map["gemini"]["card"].isHidden())

    def test_fixed_focus_ring_does_not_fall_back_on_a_narrow_screen(self):
        providers: list[BaseAIProvider] = [
            CodexProvider({"id": "codex", "name": "Codex"}),
            AntigravityProvider({"id": "gemini", "name": "Gemini"}),
            ClaudeProvider({"id": "claude", "name": "Claude"}),
        ]
        config = {
            "settings": {
                "widget_scale": "medium",
                "always_on_top": False,
                "usage_view": "ring",
                "ring_layout": "horizontal",
            }
        }

        with patch.object(
            self.widget,
            "_available_geometry",
            return_value=QRect(0, 0, 380, 900),
        ):
            self.widget.rebuild_ui(config, providers, preserve_usage=False)
            self.app.processEvents()

        cards = [
            self.widget.provider_ui_map[provider.provider_id]["card"]
            for provider in providers
        ]
        self.assertTrue(self.widget._horizontal_ring_active)
        self.assertEqual(set(self.widget.focus_provider_buttons), {"codex", "gemini", "claude"})
        self.assertEqual(self.widget.width(), FIXED_WIDGET_WIDTH)
        self.assertTrue(cards[0].isVisible())
        self.assertTrue(all(card.isHidden() for card in cards[1:]))

    def test_compact_scale_uses_tighter_spacing_and_readable_default_weight(self):
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
        self.widget.update_data([self.usage])
        self.widget.enter_compact_mode()
        self.app.processEvents()

        metrics = self.widget._compact_metrics()
        compact_value = self.widget.compact_ui_map["codex"]["value"]
        self.assertEqual(compact_value.font().pointSize(), 10)
        self.assertEqual(compact_value.font().weight(), 500)
        self.assertEqual(metrics["provider_spacing"], 10)
        self.assertGreaterEqual(metrics["vertical_margin"], 2)
        self.assertEqual(self.widget.compact_layout.spacing(), metrics["logo_spacing"])
        self.assertEqual(
            self.widget.compact_items_layout.spacing(), metrics["provider_spacing"]
        )

    def test_apply_theme_preserves_ring_and_compact_state(self):
        self.widget.config_data["settings"]["usage_view"] = "segment"
        self.widget.rebuild_ui(self.widget.config_data, self.widget.providers)
        self.widget.enter_compact_mode()
        self.app.processEvents()

        apply_theme_setting("light")
        self.widget.apply_theme()
        self.app.processEvents()

        self.assertTrue(self.widget.is_compact)
        self.assertEqual(self.widget.usage_view, "ring")
        self.assertIn("#F7F8FB", self.widget.frame.styleSheet())

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
        self.assertEqual(compact_value.font().weight(), 700)
        self.assertEqual(compact_value.font().pointSize(), 10)

        warning_usage = ModelUsage("codex", "Codex", "Codex", 80, 100, "%")
        self.widget.update_data([warning_usage])
        self.assertEqual(compact_value.font().weight(), 600)

    def test_screen_bounds_exclude_the_taskbar_area(self):
        screen = self.widget.screen()
        assert screen is not None
        self.assertEqual(
            self.widget._available_geometry(),
            screen.availableGeometry(),
        )

    def test_compact_bottom_snap_keeps_a_small_screen_edge_gap(self):
        screen = self.widget.screen()
        assert screen is not None
        geometry = screen.availableGeometry()
        self.widget.enter_compact_mode()
        self.widget.move(
            geometry.left() + 40,
            geometry.bottom() - self.widget.height() + 1,
        )

        self.widget._snap_to_screen_edges()

        self.assertEqual(
            self.widget.frameGeometry().bottom(),
            geometry.bottom() - COMPACT_BOTTOM_SAFE_GAP,
        )

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
        self.assertEqual(widget.width(), FIXED_WIDGET_WIDTH)

        widget.enter_compact_mode()
        self.app.processEvents()

        self.assertLessEqual(widget.width(), FIXED_WIDGET_WIDTH)
        self.assertGreaterEqual(
            widget.width(),
            widget.compact_bar.sizeHint().width()
            + widget.frame_layout.contentsMargins().left()
            + widget.frame_layout.contentsMargins().right(),
        )
        widget.exit_compact_mode()
        self.app.processEvents()
        self.assertEqual(widget.width(), FIXED_WIDGET_WIDTH)
        widget.close()
        widget.deleteLater()

    def test_fixed_width_survives_compact_round_trip(self):
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
        self.assertEqual(expected_width, FIXED_WIDGET_WIDTH)
        self.assertEqual(self.widget.width(), expected_width)

        self.widget.enter_compact_mode()
        self.app.processEvents()
        self.assertLess(self.widget.width(), expected_width)

        self.widget.exit_compact_mode()
        self.app.processEvents()

        self.assertEqual(self.widget.width(), expected_width)

        # A deferred Qt content-fit pass must not replace the fixed width
        # with a transient compact/content size hint.
        self.widget.setFixedWidth(280)
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
        self.assertEqual(self.widget.width(), FIXED_WIDGET_WIDTH)

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
        self.widget.move(
            available.right() - self.widget.width() - 40,
            available.bottom() - self.widget.height() + 1,
        )
        self.widget.enter_compact_mode()
        self.app.processEvents()

        self.widget.exit_compact_mode()

        self.assertFalse(self.widget._fit_timer.isActive())
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

    def test_missing_reset_is_shown_without_tooltip(self):
        self.widget.provider_ui_map["codex"]["show_five_hour"] = True
        self.usage.windows = [UsageWindow("5시간", 0, "", 100)]
        self.widget.update_data([self.usage])

        row = self.widget.provider_ui_map["codex"]["window_rows"][0]
        labels = [label.text() for label in row.findChildren(QLabel)]
        self.assertIn("SESSION", labels)
        reset_label = row.findChild(QLabel, "resetCountdown")
        self.assertIsNotNone(reset_label)
        assert reset_label is not None
        # The short status is self-contained; time labels intentionally do not
        # open a tooltip when the pointer crosses the compact usage row.
        self.assertEqual(reset_label.text(), "미상")
        self.assertEqual(reset_label.toolTip(), "")
        self.assertGreaterEqual(reset_label.width(), reset_label.sizeHint().width())

    def test_stale_reset_shows_short_label_without_tooltip(self):
        self.widget.provider_ui_map["codex"]["show_five_hour"] = True
        self.usage.windows = [UsageWindow("5시간", 40, "8/12 13:00", 60)]
        self.widget.update_data([self.usage])

        reset_label = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(
            QLabel, "resetCountdown"
        )
        self.assertIsNotNone(reset_label)
        assert reset_label is not None
        self.assertEqual(reset_label.text(), "확인 중")
        self.assertEqual(reset_label.toolTip(), "")
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

        ring = self.widget.provider_ui_map["codex"]["window_rows"][0].findChild(UsageRing)
        assert ring is not None
        self.assertEqual(ring.font_size, 11)
        self.assertTrue(ring.bold)
        self.assertEqual(self.widget.width(), FIXED_WIDGET_WIDTH)

    def test_fixed_metrics_ignore_legacy_font_preferences(self):
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
        usage_ring = row.findChild(UsageRing)
        self.assertIsNotNone(usage_ring)
        assert usage_ring is not None
        self.assertGreaterEqual(usage_ring.height(), 22)
        self.assertEqual(usage_ring.font_size, 11)
        self.assertEqual(self.widget.width(), FIXED_WIDGET_WIDTH)

        self.widget.enter_compact_mode()
        self.app.processEvents()
        compact_value = self.widget.compact_ui_map["codex"]["value"]
        self.assertEqual(compact_value.font().pointSize(), 10)
        self.assertEqual(compact_value.font().weight(), 500)
        self.assertGreaterEqual(compact_value.width(), compact_value.font().pointSize() * 3)
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
            self.assertGreaterEqual(value.width(), value.font().pointSize() * 3)
            self.assertLessEqual(value.width(), 110)
        self.assertGreaterEqual(
            self.widget.width(),
            self.widget.compact_bar.sizeHint().width()
            + self.widget.frame_layout.contentsMargins().left()
            + self.widget.frame_layout.contentsMargins().right()
            + 8,
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
            self.assertGreaterEqual(value.width(), value.font().pointSize() * 3)
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

        self.assertEqual(self.widget.height(), expanded_height)
        self.assertEqual(self.widget.cards_layout.count(), 3)


if __name__ == "__main__":
    unittest.main()
