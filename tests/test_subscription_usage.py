import os
import io
import json
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from subscription_usage import (
    SubscriptionSnapshot,
    SubscriptionWindow,
    _cli_environment,
    _command_path,
    _hidden_process_kwargs,
    query_antigravity_subscription,
    query_claude_subscription,
    query_codex_subscription,
    SubscriptionUsageError,
    _query_claude_oauth_usage,
)


class SubscriptionUsageTests(unittest.TestCase):
    @patch("subscription_usage.urllib.request.build_opener")
    @patch("subscription_usage._read_claude_oauth_token", return_value="test-token")
    def test_claude_api_reports_rate_limit_without_login_error(self, token, opener):
        opener.return_value.open.side_effect = urllib.error.HTTPError(
            "https://api.anthropic.com/api/oauth/usage", 429, "limited", {}, None,
        )
        with self.assertRaisesRegex(SubscriptionUsageError, "조회 제한"):
            _query_claude_oauth_usage(5)

    @patch("subscription_usage._query_claude_oauth_usage")
    @patch("subscription_usage._run_text_command")
    @patch("subscription_usage._command_path")
    def test_claude_cost_only_output_uses_subscription_endpoint(self, command, run, query):
        command.return_value = "claude.exe"
        run.return_value = "Total cost: $0.0000\nTotal duration (API): 0s\nUsage: 0 input"
        expected = SubscriptionSnapshot(55, "Claude Code", "weekly")
        query.return_value = expected
        self.assertEqual(query_claude_subscription({}), expected)
        query.assert_called_once_with(25.0)

    @patch("subscription_usage.urllib.request.build_opener")
    @patch("subscription_usage._read_claude_oauth_token", return_value="test-token")
    def test_claude_api_preserves_zero_usage_and_window_order(self, token, opener):
        payload = {
            "five_hour": {"utilization": 0, "resets_at": None},
            "seven_day": {"utilization": 55, "resets_at": "2026-10-08T00:00:00Z"},
            "seven_day_sonnet": {"utilization": 99, "resets_at": None},
        }
        opener.return_value.open.return_value = io.StringIO(json.dumps(payload))
        result = _query_claude_oauth_usage(5)
        self.assertEqual(result.used_percent, 55)
        self.assertEqual([w.label for w in result.windows], ["5시간", "주간"])
        self.assertEqual(result.windows[0].used_percent, 0)
        self.assertEqual(result.windows[0].reset_text, "")

    @patch("subscription_usage.urllib.request.build_opener")
    @patch("subscription_usage._read_claude_oauth_token", return_value="test-token")
    def test_claude_api_does_not_treat_missing_limits_as_zero(self, token, opener):
        opener.return_value.open.return_value = io.StringIO('{"five_hour":null,"seven_day":null}')
        with self.assertRaisesRegex(SubscriptionUsageError, "한도 없음"):
            _query_claude_oauth_usage(5)

    def test_macos_gui_finds_cli_in_user_local_bin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            executable = home / ".local" / "bin" / "claude"
            executable.parent.mkdir(parents=True)
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(0o700)

            with (
                patch("subscription_usage.Path.home", return_value=home),
                patch("subscription_usage.sys.platform", "darwin"),
                patch.dict(os.environ, {"PATH": ""}),
            ):
                result = _command_path(None, "claude")
                environment = _cli_environment()

            self.assertEqual(result, executable.resolve())
            self.assertIn(
                str(executable.parent),
                environment["PATH"].split(os.pathsep),
            )

    def test_macos_cli_search_skips_protected_and_mounted_paths(self):
        home = Path("/Users/tester")
        path_value = os.pathsep.join(
            (
                "/Volumes/team-tools/bin",
                "/Users/tester/Music/tools/bin",
                "/Users/tester/.local/bin",
                "/opt/homebrew/bin",
            )
        )

        with (
            patch("subscription_usage.Path.home", return_value=home),
            patch("subscription_usage.sys.platform", "darwin"),
            patch.dict(os.environ, {"PATH": path_value}),
        ):
            directories = [
                value.replace("\\", "/") for value in _cli_environment()["PATH"].split(os.pathsep)
            ]

        self.assertNotIn("/Volumes/team-tools/bin", directories)
        self.assertNotIn("/Users/tester/Music/tools/bin", directories)
        self.assertIn("/Users/tester/.local/bin", directories)
        self.assertIn("/opt/homebrew/bin", directories)

    @unittest.skipUnless(os.name == "nt", "Windows-specific process flags")
    def test_cli_processes_are_forced_hidden_on_windows(self):
        kwargs = _hidden_process_kwargs()

        self.assertTrue(kwargs["creationflags"] & subprocess.CREATE_NO_WINDOW)
        self.assertTrue(kwargs["startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW)
        self.assertEqual(kwargs["startupinfo"].wShowWindow, subprocess.SW_HIDE)

    @patch("subscription_usage._read_codex_app_server")
    @patch("subscription_usage._codex_cache_copy")
    @patch("subscription_usage._find_codex_command")
    def test_codex_uses_most_constrained_window(self, find_command, cache_copy, read_server):
        find_command.return_value = cache_copy.return_value = "codex.exe"
        read_server.return_value = {
            "rateLimits": {
                "planType": "plus",
                "primary": {
                    "usedPercent": 12,
                    "windowDurationMins": 300,
                    "resetsAt": 1786347000,
                },
                "secondary": {
                    "usedPercent": 44,
                    "windowDurationMins": 10080,
                    "resetsAt": 1786926634,
                },
            }
        }

        result = query_codex_subscription({})

        self.assertEqual(result.used_percent, 44.0)
        self.assertEqual(result.model_name, "Codex (Plus)")
        self.assertIn("주간", result.status_text)
        self.assertEqual([window.label for window in result.windows], ["5시간", "주간"])
        self.assertEqual([window.used_percent for window in result.windows], [12.0, 44.0])

    @patch("subscription_usage._run_text_command")
    @patch("subscription_usage._command_path")
    def test_antigravity_converts_remaining_to_used(self, command_path, run_command):
        command_path.return_value = "agy.exe"
        run_command.return_value = "\n".join(
            [
                "Gemini Models\tWeekly Limit Remaining\t52%\t2026-08-12T00:49:11Z",
                "Gemini Models\tFive Hour Limit Remaining\t92%\t2026-08-10T11:00:31Z",
                "Claude and GPT models\tWeekly Limit Remaining\t100%\t2026-08-17T07:10:35Z",
            ]
        )

        result = query_antigravity_subscription({"quota_group": "Gemini Models"})

        self.assertEqual(result.used_percent, 48.0)
        self.assertEqual(result.model_name, "Gemini Models")
        self.assertIn("주간 52% 남음", result.status_text)
        self.assertEqual([window.label for window in result.windows], ["5시간", "주간"])
        self.assertEqual([window.used_percent for window in result.windows], [8.0, 48.0])
        environment = run_command.call_args.kwargs["env_overrides"]
        self.assertIn("PATH", environment)
        self.assertEqual(environment["AGY_CLI_DISABLE_AUTO_UPDATE"], "true")
        self.assertNotIn("HOME", environment)
        self.assertNotIn("USERPROFILE", environment)
        self.assertNotIn(".local", environment["PATH"])
        self.assertNotIn("agy", environment["PATH"].lower())
        command = run_command.call_args.args[0]
        self.assertIn("--sandbox", command)
        self.assertIn("--log-file", command)

    @patch("subscription_usage._run_text_command")
    @patch("subscription_usage._command_path")
    def test_antigravity_keeps_real_user_home_for_keyring(self, command_path, run_command):
        command_path.return_value = "agy.exe"
        run_command.return_value = (
            "Gemini Models\tWeekly Limit Remaining\t52%\t2026-08-12T00:49:11Z"
        )

        query_antigravity_subscription({"quota_group": "Gemini Models"})

        environment = run_command.call_args.kwargs["env_overrides"]
        for variable in (
            "HOME",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "XDG_CONFIG_HOME",
        ):
            self.assertNotIn(variable, environment)

    @patch("subscription_usage._run_text_command")
    @patch("subscription_usage._command_path")
    def test_claude_parses_subscription_windows(self, command_path, run_command):
        command_path.return_value = "claude.exe"
        run_command.return_value = """
You are currently using your subscription to power your Claude Code usage

Current session: 6% used · resets Aug 10, 7:30pm (Asia/Seoul)
Current week (all models): 50% used · resets Aug 12, 4am (Asia/Seoul)
""".strip()

        result = query_claude_subscription({})

        command = run_command.call_args.args[0]
        self.assertIn("--safe-mode", command)
        self.assertIn("--no-chrome", command)
        self.assertIn("--strict-mcp-config", command)
        self.assertIn("--mcp-config", command)
        mcp_config = Path(command[command.index("--mcp-config") + 1])
        self.assertEqual(
            mcp_config.read_text(encoding="utf-8"),
            '{"mcpServers":{}}\n',
        )
        self.assertEqual(
            run_command.call_args.kwargs["env_overrides"]["MCP_CONNECTION_NONBLOCKING"],
            "true",
        )
        self.assertEqual(result.used_percent, 50.0)
        self.assertEqual(result.model_name, "Claude Code")
        self.assertIn("주간", result.status_text)
        self.assertIn("8/12 04:00", result.status_text)
        self.assertEqual([window.label for window in result.windows], ["5시간", "주간"])
        self.assertEqual([window.used_percent for window in result.windows], [6.0, 50.0])

    @patch("subscription_usage._run_text_command")
    @patch("subscription_usage._command_path")
    def test_claude_keeps_zero_session_without_reset(self, command_path, run_command):
        command_path.return_value = "claude.exe"
        run_command.return_value = """
You are currently using your subscription to power your Claude Code usage

Current session: 0% used
Current week (all models): 55% used · resets Aug 12, 4am (Asia/Seoul)
""".strip()

        result = query_claude_subscription({})

        self.assertEqual([window.label for window in result.windows], ["5시간", "주간"])
        self.assertEqual([window.used_percent for window in result.windows], [0.0, 55.0])
        self.assertEqual(result.windows[0].reset_text, "")


class ProviderCacheTests(unittest.TestCase):
    @patch("providers.query_claude_subscription")
    def test_claude_rate_limit_cooldown_survives_manual_refresh(self, query):
        from providers import ClaudeProvider

        query.side_effect = SubscriptionUsageError("Claude 사용량 조회 제한 · 잠시 후 다시 시도하세요")
        provider = ClaudeProvider({"id": "claude"})
        with patch("providers.time.monotonic", return_value=100):
            first = provider.fetch_usage()
            provider.invalidate_cache()
            self.assertIs(provider.fetch_usage(), first)
        query.assert_called_once()
        with patch("providers.time.monotonic", return_value=401):
            provider.fetch_usage()
        self.assertEqual(query.call_count, 2)

    @patch("providers.query_codex_subscription")
    def test_manual_invalidation_allows_a_fresh_read(self, query):
        from providers import CodexProvider

        query.side_effect = [
            SubscriptionSnapshot(
                10,
                "Codex",
                "주간",
                (SubscriptionWindow("주간", 10, "8/17 09:30", 90),),
            ),
            SubscriptionSnapshot(20, "Codex", "주간"),
        ]
        provider = CodexProvider({"id": "codex", "name": "Codex", "cache_ttl_sec": 3600})

        first = provider.fetch_usage()
        self.assertEqual(first.used, 10)
        self.assertIsNotNone(first.windows)
        assert first.windows is not None
        self.assertEqual(first.windows[0].remaining, 90)
        self.assertIsNotNone(first.fetched_at)
        self.assertEqual(provider.fetch_usage().used, 10)
        provider.invalidate_cache()
        self.assertEqual(provider.fetch_usage().used, 20)
        self.assertEqual(query.call_count, 2)


if __name__ == "__main__":
    unittest.main()
