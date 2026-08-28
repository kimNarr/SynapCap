import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from diagnostics import build_diagnostic_report
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
        self.assertIn("토큰이나 API 키가 포함되지 않습니다", report)
