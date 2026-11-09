import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QMessageBox

from main import (
    _changed_provider_query_ids,
    _launch_restart_process,
    _launch_windows_installer,
    _provider_query_settings_changed,
    _provider_settings_changed,
    _setting_changed,
    _should_start_centered,
    confirm_quit,
    show_provider_diagnostics,
)
from providers import CodexProvider, ModelUsage
from ui.widget import SynapCapWidget


class UpdateInstallerTests(unittest.TestCase):
    @patch("main.ctypes.windll", create=True)
    def test_windows_installer_uses_elevation_and_silent_flags(self, windll):
        windll.shell32.ShellExecuteW.return_value = 42

        _launch_windows_installer(r"C:\Temp\SynapCap-Setup.exe")

        call = windll.shell32.ShellExecuteW.call_args.args
        self.assertEqual(call[1], "open")
        self.assertEqual(call[2], r"C:\Temp\SynapCap-Setup.exe")
        self.assertIn("/VERYSILENT", call[3])
        self.assertIn("/CLOSEAPPLICATIONS", call[3])

    @patch("main.ctypes.windll", create=True)
    def test_windows_installer_rejection_does_not_quit_app(self, windll):
        windll.shell32.ShellExecuteW.return_value = 5

        with self.assertRaises(OSError):
            _launch_windows_installer(r"C:\Temp\SynapCap-Setup.exe")

    @patch("main.subprocess.Popen")
    @patch("main.sys.argv", ["main.py", "--sample"])
    @patch("main.sys.executable", "python-test")
    def test_restart_launches_replacement_process(self, popen):
        with patch("main.sys.frozen", False, create=True):
            _launch_restart_process()

        command = popen.call_args.args[0]
        self.assertEqual(command, ["python-test", "main.py", "--sample"])
        self.assertTrue(popen.call_args.kwargs["close_fds"])


class SettingsChangeTests(unittest.TestCase):
    def test_theme_setting_change_is_detected(self):
        previous = {"settings": {"theme": "dark"}}
        current = {"settings": {"theme": "light"}}

        self.assertTrue(_setting_changed(previous, current, "theme"))

    def test_window_mode_change_is_detected(self):
        previous = {"settings": {"window_mode": "expanded"}}
        current = {"settings": {"window_mode": "none"}}

        self.assertTrue(_setting_changed(previous, current, "window_mode"))

    def test_start_centered_on_first_run_and_after_update_only(self):
        # First run: no saved position anywhere.
        self.assertTrue(_should_start_centered({}, updated=False))
        # Fresh update, even with a saved position.
        self.assertTrue(
            _should_start_centered({"window_pos_bar": [10, 20]}, updated=True)
        )
        # Normal launch: reuse the saved position.
        self.assertFalse(
            _should_start_centered({"window_pos_expanded": [10, 20]}, updated=False)
        )

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
        self.assertTrue(_setting_changed(previous, current, "usage_value_bold"))

    def test_provider_edit_requires_provider_reload(self):
        previous = {"providers": [{"id": "codex", "type": "codex"}]}
        current = {"providers": [{"id": "codex", "type": "claude"}]}

        self.assertTrue(_provider_settings_changed(previous, current))
        self.assertTrue(_provider_query_settings_changed(previous, current))
        self.assertEqual(_changed_provider_query_ids(previous, current), {"codex"})

    def test_query_change_identifies_only_the_affected_provider(self):
        previous = {
            "providers": [
                {"id": "codex", "type": "codex"},
                {"id": "copilot", "type": "copilot", "account": "first"},
            ]
        }
        current = {
            "providers": [
                {"id": "codex", "type": "codex"},
                {"id": "copilot", "type": "copilot", "account": "second"},
            ]
        }

        self.assertEqual(
            _changed_provider_query_ids(previous, current),
            {"copilot"},
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
        self.assertFalse(_provider_query_settings_changed(previous, current))

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

        self.assertFalse(_provider_query_settings_changed(previous, current))


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
        dialog.setDefaultButton.assert_called_once_with(QMessageBox.StandardButton.No)

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
        assert icon_label is not None
        self.assertLess(icon_label.minimumWidth(), 100)
        self.assertLess(dialog.sizeHint().width(), 420)
        self.assertLess(
            dialog.button(QMessageBox.StandardButton.Yes).sizeHint().width(),
            90,
        )


class ProviderDiagnosticsIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    @patch("main.build_diagnostic_report", return_value="safe diagnostic report")
    def test_visible_provider_status_opens_matching_diagnostic_dialog(self, build_report):
        config = {
            "settings": {"always_on_top": False},
            "providers": [{"id": "codex", "name": "Codex", "type": "codex"}],
        }
        provider = CodexProvider(config["providers"][0])
        usage = ModelUsage(
            "codex",
            "Codex",
            "Codex",
            0,
            100,
            "%",
            error="Codex 로그인이 필요합니다",
        )
        widget = SynapCapWidget(config, [provider])
        widget.show()
        widget.update_data([usage])
        self.app.processEvents()

        dialog = MagicMock()
        copy_button = object()
        close_button = object()
        dialog.addButton.side_effect = [copy_button, close_button]
        dialog.clickedButton.return_value = close_button
        dialog_factory = MagicMock(return_value=dialog)
        widget.diagnostics_requested.connect(
            lambda provider_id: show_provider_diagnostics(
                widget,
                config,
                widget.latest_usage,
                provider_id,
                dialog_factory,
            )
        )

        try:
            status = widget.provider_ui_map["codex"]["status"]
            self.assertTrue(status.isVisibleTo(widget))
            status.click()

            dialog_factory.assert_called_once_with(widget)
            build_report.assert_called_once_with(config["providers"][0], usage)
            dialog.setWindowTitle.assert_called_once_with("Codex 진단")
            dialog.setDetailedText.assert_called_once_with("safe diagnostic report")
            dialog.exec.assert_called_once_with()
        finally:
            widget.close()
            widget.deleteLater()
            self.app.processEvents()


if __name__ == "__main__":
    unittest.main()
