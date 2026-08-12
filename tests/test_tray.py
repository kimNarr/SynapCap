import os
import unittest

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


if __name__ == "__main__":
    unittest.main()
