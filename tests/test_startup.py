import os
import unittest
from unittest.mock import MagicMock, patch

from startup import _launch_command, is_startup_enabled, set_startup_enabled


class StartupTests(unittest.TestCase):
    def test_launch_command_contains_executable(self):
        cmd = _launch_command()
        self.assertTrue(len(cmd) > 0)
        self.assertTrue(cmd.startswith('"'))

    @patch("os.name", "posix")
    def test_non_windows_safely_returns_false(self):
        self.assertFalse(is_startup_enabled())
        self.assertFalse(set_startup_enabled(True))

    @patch("startup._launch_command", return_value='"C:\\app.exe"')
    @patch("os.name", "nt")
    def test_windows_registry_toggle_mock(self, launch_command):
        import sys
        mock_winreg = MagicMock()
        with patch.dict(sys.modules, {"winreg": mock_winreg}):
            mock_winreg.HKEY_CURRENT_USER = 1
            mock_winreg.KEY_READ = 2
            mock_winreg.KEY_SET_VALUE = 4
            mock_winreg.REG_SZ = 1
            mock_key = MagicMock()
            mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
            mock_winreg.QueryValueEx.return_value = ("C:\\app.exe", 1)

            # Check enabled
            self.assertTrue(is_startup_enabled())

            # Set enabled
            self.assertTrue(set_startup_enabled(True))
            mock_winreg.SetValueEx.assert_called_once_with(
                mock_key, "SynapCap", 0, mock_winreg.REG_SZ, '"C:\\app.exe"',
            )
            launch_command.assert_called_once_with()

            # Set disabled
            self.assertTrue(set_startup_enabled(False))
            mock_winreg.DeleteValue.assert_called_once()


if __name__ == "__main__":
    unittest.main()
