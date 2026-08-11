import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from config import get_default_config
from ui.settings_dialog import SettingsDialog


class SettingsDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.dialog = SettingsDialog(get_default_config())

    def tearDown(self):
        self.dialog.close()
        self.dialog.deleteLater()
        self.app.processEvents()

    def _provider_item(self, provider_id: str) -> dict:
        return next(
            item
            for item in self.dialog.provider_widgets
            if item["id"] == provider_id
        )

    def test_codex_only_allows_weekly_window(self):
        item = self._provider_item("codex")

        self.assertFalse(item["five_hour_check"].isChecked())
        self.assertFalse(item["five_hour_check"].isEnabled())
        self.assertTrue(item["weekly_check"].isChecked())
        self.assertFalse(item["weekly_check"].isEnabled())

    def test_gemini_cannot_hide_both_windows(self):
        item = self._provider_item("antigravity")
        item["five_hour_check"].setChecked(False)
        item["weekly_check"].setChecked(False)

        self.assertFalse(item["five_hour_check"].isChecked())
        self.assertTrue(item["weekly_check"].isChecked())


if __name__ == "__main__":
    unittest.main()
