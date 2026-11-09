import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from feedback import FEEDBACK_CHOOSER_URL
from providers import ModelUsage, UsageWindow
from subscription_usage import StatusKind
from ui.tray import SynapCapTray, create_usage_tray_icon


class TrayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_feedback_action_opens_issue_template_chooser(self):
        tray = SynapCapTray()
        requested_urls = []
        tray.feedback_requested.connect(requested_urls.append)

        tray.feedback_action.trigger()

        self.assertEqual(requested_urls, [FEEDBACK_CHOOSER_URL])
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_update_check_and_restart_actions_emit_requests(self):
        tray = SynapCapTray()
        update_checks = []
        restarts = []
        tray.update_check_requested.connect(lambda: update_checks.append(True))
        tray.restart_requested.connect(lambda: restarts.append(True))

        tray.check_update_action.trigger()
        tray.restart_action.trigger()

        self.assertEqual(update_checks, [True])
        self.assertEqual(restarts, [True])
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_update_check_action_shows_progress_state(self):
        tray = SynapCapTray()

        tray.set_update_checking(True)
        self.assertFalse(tray.check_update_action.isEnabled())
        self.assertEqual(tray.check_update_action.text(), "업데이트 확인 중...")

        tray.set_update_checking(False)
        self.assertTrue(tray.check_update_action.isEnabled())
        self.assertEqual(tray.check_update_action.text(), "업데이트 확인")
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_usage_threshold_notification_is_actionable(self):
        tray = SynapCapTray()
        with patch.object(tray.tray_icon, "showMessage") as show_message:
            tray.show_usage_alert("Claude", "5시간", 92, 90)

        title, message = show_message.call_args.args[:2]
        self.assertIn("Claude", title)
        self.assertIn("92%", message)
        self.assertIn("90%", message)
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_display_mode_actions_are_exclusive_and_emit_mode(self):
        tray = SynapCapTray(window_mode="bar")
        requested = []
        tray.window_mode_requested.connect(requested.append)

        self.assertTrue(tray.mode_actions["bar"].isChecked())
        tray.mode_actions["none"].trigger()

        self.assertEqual(requested, ["none"])
        self.assertTrue(tray.mode_actions["none"].isChecked())
        self.assertFalse(tray.mode_actions["bar"].isChecked())
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_left_click_requests_the_last_visible_window(self):
        tray = SynapCapTray(window_mode="none")
        restores = []
        activations = []
        tray.restore_window_requested.connect(lambda: restores.append(True))
        tray.activation_observed.connect(activations.append)

        tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)

        self.assertEqual(restores, [True])
        self.assertEqual(activations, ["Trigger"])
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_tray_icon_uses_the_highest_available_usage(self):
        tray = SynapCapTray()
        usages = [
            ModelUsage(
                "codex",
                "Codex",
                "Codex",
                32,
                100,
                "%",
                windows=[
                    UsageWindow("5h", 32, "1h"),
                    UsageWindow("7d", 67, "4d"),
                ],
            ),
            ModelUsage("claude", "Claude", "Claude", 91, 100, "%"),
        ]

        with patch("ui.tray.create_usage_tray_icon") as create_icon:
            create_icon.return_value = QIcon()
            tray.update_usage(usages)

        create_icon.assert_called_once_with(91)
        self.assertIn("Codex 주간 67%", tray.tray_icon.toolTip())
        self.assertIn("Claude 사용량 91%", tray.tray_icon.toolTip())
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_tray_metric_can_pin_a_single_provider(self):
        tray = SynapCapTray(tray_metric="codex")
        usages = [
            ModelUsage(
                "codex",
                "Codex",
                "Codex",
                40,
                100,
                "%",
                windows=[UsageWindow("5h", 40, "1h"), UsageWindow("7d", 55, "4d")],
            ),
            ModelUsage("claude", "Claude", "Claude", 92, 100, "%"),
        ]
        with patch("ui.tray.create_usage_tray_icon") as create_icon:
            create_icon.return_value = QIcon()
            tray.update_usage(usages)
        # Shows Codex's highest window (55), not Claude's 92.
        create_icon.assert_called_once_with(55)
        # Tooltip still lists every provider.
        self.assertIn("Codex 주간 55%", tray.tray_icon.toolTip())
        self.assertIn("Claude 사용량 92%", tray.tray_icon.toolTip())

        # Switching back to "highest" re-reads without new data.
        with patch("ui.tray.create_usage_tray_icon") as create_icon:
            create_icon.return_value = QIcon()
            tray.set_tray_metric("highest")
        create_icon.assert_called_once_with(92)
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_tray_metric_falls_back_when_pinned_provider_errors(self):
        tray = SynapCapTray(tray_metric="codex")
        usages = [
            ModelUsage("codex", "Codex", "Codex", 0, 100, "%", error="codex CLI를 찾을 수 없음"),
            ModelUsage("claude", "Claude", "Claude", 70, 100, "%"),
        ]
        with (
            patch("ui.tray.create_usage_tray_icon") as create_icon,
            patch("ui.tray.create_app_icon") as app_icon,
        ):
            create_icon.return_value = QIcon()
            app_icon.return_value = QIcon()
            tray.update_usage(usages)
        create_icon.assert_not_called()
        app_icon.assert_called()
        self.assertIn("Codex 조회 오류", tray.tray_icon.toolTip())
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_tray_metric_none_keeps_the_plain_app_icon(self):
        tray = SynapCapTray(tray_metric="none")
        usages = [ModelUsage("claude", "Claude", "Claude", 88, 100, "%")]
        with (
            patch("ui.tray.create_usage_tray_icon") as create_icon,
            patch("ui.tray.create_app_icon") as app_icon,
        ):
            create_icon.return_value = QIcon()
            app_icon.return_value = QIcon()
            tray.update_usage(usages)
        create_icon.assert_not_called()
        app_icon.assert_called()
        # Tooltip still carries the numbers.
        self.assertIn("Claude 사용량 88%", tray.tray_icon.toolTip())
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_tray_tooltip_identifies_session_and_weekly_windows(self):
        tray = SynapCapTray()
        usages = [
            ModelUsage(
                "codex",
                "Codex",
                "Codex",
                85,
                100,
                "%",
                windows=[
                    UsageWindow("5시간", 85, "1h"),
                    UsageWindow("주간", 44, "4d"),
                ],
            ),
            ModelUsage(
                "gemini",
                "Gemini",
                "Gemini",
                28,
                100,
                "%",
                windows=[
                    UsageWindow("5h", 12, "1h"),
                    UsageWindow("7d", 28, "4d"),
                ],
            ),
        ]

        with patch("ui.tray.create_usage_tray_icon") as create_icon:
            create_icon.return_value = QIcon()
            tray.update_usage(usages)

        self.assertIn("Codex 세션 85%", tray.tray_icon.toolTip())
        self.assertIn("Gemini 주간 28%", tray.tray_icon.toolTip())
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_three_digit_usage_tray_icon_is_rendered(self):
        self.assertFalse(create_usage_tray_icon(100).isNull())

    def test_tray_peak_identifies_quota_group_and_unavailable_argon(self):
        tray = SynapCapTray()
        usage = ModelUsage("gemini", "Gemini", "Gemini Models", 95, 100, "%", windows=[
            UsageWindow("주간", 35, "", quota_group="Gemini Models"),
            UsageWindow("주간", 95, "", quota_group="Gemini 4 Argon"),
        ])
        try:
            tray.update_usage([usage])
            self.assertIn("Gemini 4 Argon · 주간 95%", tray.tray_icon.toolTip())
            usage.windows.pop()
            usage.action_hint = "Argon 조회 미지원: CLI가 별도 한도를 제공하지 않습니다."
            tray.update_usage([usage])
            self.assertIn("Gemini Models · 주간 35%", tray.tray_icon.toolTip())
            self.assertIn("Argon 조회 미지원", tray.tray_icon.toolTip())
        finally:
            tray.tray_icon.hide()
            tray.tray_icon.deleteLater()

    def test_no_quota_and_unlimited_are_excluded_from_tray_number(self):
        no_quota = ModelUsage(
            "grok",
            "Grok",
            "Grok API",
            0,
            100,
            "%",
            status_kind=StatusKind.NO_QUOTA,
        )
        unlimited = ModelUsage(
            "copilot",
            "Copilot",
            "Copilot",
            0,
            100,
            "%",
            windows=[UsageWindow("채팅", 0, "", None, unlimited=True)],
        )
        tray = SynapCapTray(tray_metric="highest")
        with (
            patch("ui.tray.create_usage_tray_icon") as create_icon,
            patch("ui.tray.create_app_icon") as app_icon,
        ):
            app_icon.return_value = QIcon()
            tray.update_usage([no_quota, unlimited])

        create_icon.assert_not_called()
        app_icon.assert_called()
        self.assertIn("Grok 한도 없음", tray.tray_icon.toolTip())
        self.assertIn("Copilot 무제한", tray.tray_icon.toolTip())
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_stale_unlimited_usage_keeps_unlimited_tooltip(self):
        usage = ModelUsage(
            "copilot",
            "Copilot",
            "Copilot",
            0,
            100,
            "%",
            windows=[UsageWindow("채팅", 0, "", None, unlimited=True)],
            is_stale=True,
            error="temporary failure",
        )
        tray = SynapCapTray(tray_metric="highest")
        tray.update_usage([usage])
        self.assertIn("Copilot 무제한 (갱신 실패)", tray.tray_icon.toolTip())
        self.assertNotIn("0%", tray.tray_icon.toolTip())
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_zero_percent_remains_a_measurable_tray_value(self):
        tray = SynapCapTray(tray_metric="codex")
        usage = ModelUsage("codex", "Codex", "Codex", 0, 100, "%")
        with patch("ui.tray.create_usage_tray_icon") as create_icon:
            create_icon.return_value = QIcon()
            tray.update_usage([usage])
        create_icon.assert_called_once_with(0)
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()


if __name__ == "__main__":
    unittest.main()
