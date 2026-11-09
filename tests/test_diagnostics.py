import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from diagnostics import build_diagnostic_report, sanitize_diagnostic_text
from providers import ModelUsage
from version import APP_VERSION


class DiagnosticsTests(unittest.TestCase):
    @patch("diagnostics.detect_cli_path", return_value="/usr/local/bin/claude")
    def test_report_contains_safe_actionable_cli_details(self, _detect):
        usage = ModelUsage(
            "claude",
            "Claude",
            "Claude Code",
            0,
            100,
            "%",
            error="로컬 CLI 로그인 필요",
            fetched_at=datetime(2026, 8, 27, 9, 30, tzinfo=UTC),
        )

        report = build_diagnostic_report(
            {"id": "claude", "name": "Claude", "type": "claude"},
            usage,
        )

        self.assertIn(f"SynapCap v{APP_VERSION}", report)
        self.assertIn("로컬 CLI 로그인 필요", report)
        self.assertIn("/usr/local/bin/claude", report)
        self.assertIn("claude --version", report)
        self.assertIn("실행 형태:", report)
        self.assertIn("실행 파일:", report)
        self.assertIn("Python 런타임:", report)
        self.assertIn("로컬 진단 로그:", report)
        self.assertIn("토큰이나 API 키가 포함되지 않습니다", report)

    @patch("diagnostics.Path.home", return_value=Path("C:/Users/alice"))
    @patch.dict(
        "diagnostics.os.environ",
        {
            "USERPROFILE": "C:\\Users\\alice",
            "LOCALAPPDATA": "C:\\Users\\alice\\AppData\\Local",
            "APPDATA": "C:\\Users\\alice\\AppData\\Roaming",
        },
        clear=False,
    )
    def test_sanitizer_redacts_user_paths_and_credentials(self, _home):
        text = sanitize_diagnostic_text(
            "C:\\Users\\alice\\AppData\\Local\\SynapCap\\app.exe "
            "github_pat_abcdefghijklmnop xai-abcdefghijklmnop"
        )

        self.assertEqual(
            text,
            "<LOCALAPPDATA>\\SynapCap\\app.exe <REDACTED> <REDACTED>",
        )
        self.assertNotIn("alice", text)

    @patch("diagnostics.sys.executable", "C:\\Users\\alice\\AppData\\Local\\SynapCap\\SynapCap.exe")
    @patch("diagnostics.sys.frozen", True, create=True)
    @patch("diagnostics.detect_cli_path", return_value=None)
    @patch("diagnostics.Path.home", return_value=Path("C:/Users/alice"))
    @patch.dict("diagnostics.os.environ", {"USERPROFILE": "C:\\Users\\alice"}, clear=False)
    def test_bundled_report_identifies_runtime_without_exposing_home(
        self,
        _home,
        _detect,
    ):
        report = build_diagnostic_report(
            {"id": "codex", "name": "Codex", "type": "codex"},
            None,
        )

        self.assertIn("실행 형태: 배포 번들", report)
        self.assertIn("실행 파일: <HOME>", report)
        self.assertNotIn("alice", report)
