import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from feedback import FEEDBACK_CHOOSER_URL
from ui.tray import SynapCapTray


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


if __name__ == "__main__":
    unittest.main()
