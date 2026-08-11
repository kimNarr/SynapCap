import os
import unittest
from unittest.mock import MagicMock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from main import (
    confirm_quit,
    _provider_query_settings_changed,
    _provider_settings_changed,
    _setting_changed,
)


class SettingsChangeTests(unittest.TestCase):
    def test_visual_setting_does_not_change_providers(self):
        previous = {
            "settings": {"usage_value_bold": True},
            "providers": [{"id": "codex", "type": "codex"}],
        }
        current = {
            "settings": {"usage_value_bold": False},
            "providers": [{"id": "codex", "type": "codex"}],
        }

        self.assertFalse(_provider_settings_changed(previous, current))
        self.assertTrue(
            _setting_changed(previous, current, "usage_value_bold")
        )

    def test_provider_edit_requires_provider_reload(self):
        previous = {"providers": [{"id": "codex", "type": "codex"}]}
        current = {"providers": [{"id": "codex", "type": "claude"}]}

        self.assertTrue(_provider_settings_changed(previous, current))
        self.assertTrue(
            _provider_query_settings_changed(previous, current)
        )

    def test_provider_name_and_order_do_not_require_query(self):
        previous = {
            "providers": [
                {"id": "codex", "name": "Codex", "type": "codex"},
                {"id": "claude", "name": "Claude", "type": "claude"},
            ]
        }
        current = {
            "providers": [
                {"id": "claude", "name": "Claude Code", "type": "claude"},
                {"id": "codex", "name": "OpenAI Codex", "type": "codex"},
            ]
        }

        self.assertTrue(_provider_settings_changed(previous, current))
        self.assertFalse(
            _provider_query_settings_changed(previous, current)
        )

    def test_window_visibility_does_not_require_query(self):
        previous = {
            "providers": [
                {
                    "id": "claude",
                    "type": "claude",
                    "show_five_hour": True,
                    "show_weekly": True,
                }
            ]
        }
        current = {
            "providers": [
                {
                    "id": "claude",
                    "type": "claude",
                    "show_five_hour": False,
                    "show_weekly": True,
                }
            ]
        }

        self.assertFalse(
            _provider_query_settings_changed(previous, current)
        )


class QuitConfirmationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def _dialog(self, result):
        dialog = MagicMock()
        dialog.exec.return_value = result
        dialog.button.return_value = MagicMock()
        return dialog

    def test_exit_requires_explicit_confirmation(self):
        dialog = self._dialog(QMessageBox.StandardButton.Yes)

        confirmed = confirm_quit(None, lambda _parent: dialog)

        self.assertTrue(confirmed)
        dialog.setDefaultButton.assert_called_once_with(
            QMessageBox.StandardButton.No
        )

    def test_cancel_keeps_application_running(self):
        dialog = self._dialog(QMessageBox.StandardButton.No)

        self.assertFalse(confirm_quit(None, lambda _parent: dialog))

    def test_confirmation_does_not_stretch_the_icon_column(self):
        class NonBlockingMessageBox(QMessageBox):
            def exec(self):
                return QMessageBox.StandardButton.No

        dialog = NonBlockingMessageBox()
        self.assertFalse(confirm_quit(None, lambda _parent: dialog))
        dialog.ensurePolished()
        dialog.adjustSize()

        icon_label = dialog.findChild(QLabel, "qt_msgboxex_icon_label")
        self.assertIsNotNone(icon_label)
        self.assertLess(icon_label.minimumWidth(), 100)
        self.assertLess(dialog.sizeHint().width(), 500)

if __name__ == "__main__":
    unittest.main()
