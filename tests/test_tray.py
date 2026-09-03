import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from feedback import FEEDBACK_CHOOSER_URL
from providers import ModelUsage, UsageWindow
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
        tray.restore_window_requested.connect(lambda: restores.append(True))

        tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)

        self.assertEqual(restores, [True])
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
        self.assertIn("Codex 67%", tray.tray_icon.toolTip())
        self.assertIn("Claude 91%", tray.tray_icon.toolTip())
        tray.tray_icon.hide()
        tray.tray_icon.deleteLater()

    def test_three_digit_usage_tray_icon_is_rendered(self):
        self.assertFalse(create_usage_tray_icon(100).isNull())


if __name__ == "__main__":
    unittest.main()
