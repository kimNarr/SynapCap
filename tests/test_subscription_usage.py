import io
import json
import os
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from subscription_usage import (
    StatusKind,
    SubscriptionSnapshot,
    SubscriptionUsageError,
    SubscriptionWindow,
    _cli_environment,
    _command_path,
    _hidden_process_kwargs,
    _query_claude_oauth_usage,
    _run_copilot_probe_script,
    query_antigravity_subscription,
    query_claude_subscription,
    query_codex_subscription,
    query_copilot_subscription,
    query_grok_subscription,
)


class SubscriptionUsageTests(unittest.TestCase):
    @patch("subscription_usage.subprocess.Popen")
    def test_frozen_copilot_probe_uses_bundled_helper_not_app_executable(self, popen):
        popen.return_value.communicate.return_value = (
            json.dumps({"status": "ok", "quotas": {}}),
            "",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            helper_name = "SynapCapCopilotProbe.exe" if os.name == "nt" else "SynapCapCopilotProbe"
            helper = Path(temp_dir) / helper_name
            helper.write_bytes(b"probe")
            helper = helper.resolve()
            app = Path(temp_dir) / "SynapCap.exe"
            with (
                patch("subscription_usage.sys.frozen", True, create=True),
                patch("subscription_usage.sys.executable", str(app)),
                patch("subscription_usage.sys._MEIPASS", temp_dir, create=True),
            ):
                result = _run_copilot_probe_script(None, 10)

        command = popen.call_args.args[0]
        self.assertEqual(command, [str(helper)])
        self.assertNotIn(str(app), command)
        self.assertEqual(result["status"], "ok")

    @patch("subscription_usage.urllib.request.build_opener")
    @patch("subscription_usage._read_claude_oauth_token", return_value="test-token")
    def test_claude_api_reports_rate_limit_without_login_error(self, token, opener):
        opener.return_value.open.side_effect = urllib.error.HTTPError(
            "https://api.anthropic.com/api/oauth/usage",
            429,
            "limited",
            {},
            None,
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
    @patch("subscription_usage._command_path", return_value="agy.exe")
    def test_antigravity_preserves_gemini_and_argon_groups(self, command_path, run_command):
        # Synthetic CLI rows, not a captured Argon response. The percentage
        # meaning is explicit; a screenshot's bare Weekly Limit is not enough.
        run_command.return_value = (
            "Gemini 4 Argon\tWeekly Limit Remaining\t98%\t2026-10-25T09:00:00Z\n"
            "Gemini Models\tWeekly Limit Remaining\t65%\t2026-10-24T00:00:00Z\n"
            "Gemini Models\tFive Hour Limit Remaining\t72%\t2026-10-19T11:00:00Z\n"
            "Claude and GPT models\tWeekly Limit Remaining\t0%\t2026-10-24T00:00:00Z"
        )
        result = query_antigravity_subscription({"quota_group": "Gemini Models"})
        self.assertEqual(
            [(w.quota_group, w.label, w.used_percent) for w in result.windows],
            [("Gemini Models", "5시간", 28), ("Gemini Models", "주간", 35),
             ("Gemini 4 Argon", "주간", 2)],
        )
        self.assertEqual(result.used_percent, 35)
        self.assertIsNone(result.action_hint)
        self.assertNotEqual(result.windows[1].reset_text, result.windows[2].reset_text)

        from providers import AntigravityProvider
        usage = AntigravityProvider({"id": "antigravity", "name": "Gemini"}).fetch_usage()
        self.assertEqual(usage.windows[2].display_label, "Gemini 4 Argon · 주간")

    @patch("subscription_usage._run_text_command")
    @patch("subscription_usage._command_path", return_value="agy.exe")
    def test_antigravity_missing_or_ambiguous_argon_does_not_invent_values(self, command_path, run_command):
        base = "Gemini Models\tWeekly Limit Remaining\t65%\t2026-10-24T00:00:00Z"
        for extra in ("", "\nGemini 4 Argon\tGemini 4 Argon Weekly Limit\t98%\t2026-10-25T09:00:00Z"):
            with self.subTest(extra=extra):
                run_command.return_value = base + extra
                result = query_antigravity_subscription({})
                self.assertEqual(len(result.windows), 1)
                self.assertEqual(result.windows[0].used_percent, 35)
                self.assertIn("Argon 조회 미지원", result.action_hint)

    @patch("subscription_usage._run_text_command")
    @patch("subscription_usage._command_path", return_value="agy.exe")
    def test_antigravity_exact_custom_group_and_no_arbitrary_fallback(self, command_path, run_command):
        run_command.return_value = (
            "Gemini Models\tWeekly Limit Remaining\t65%\t2026-10-24T00:00:00Z\n"
            "Gemini 4 Argon\tWeekly Limit Used\t42%\t2026-10-25T09:00:00Z\n"
            "Gemini 4 Argon Plus\tWeekly Limit Remaining\t0%\t2026-10-25T09:00:00Z"
        )
        result = query_antigravity_subscription({"quota_group": "gemini 4 argon"})
        self.assertEqual([(w.quota_group, w.used_percent) for w in result.windows], [("Gemini 4 Argon", 42)])
        with self.assertRaises(SubscriptionUsageError) as raised:
            query_antigravity_subscription({"quota_group": "missing group"})
        self.assertEqual(raised.exception.status_kind, StatusKind.FORMAT_ERROR)

    @patch("subscription_usage._run_text_command")
    @patch("subscription_usage._command_path", return_value="agy.exe")
    def test_antigravity_group_changes_keep_period_identity(self, command_path, run_command):
        for groups in (("Gemini Flash", "Gemini Argon"), ("Gemini Argon",)):
            with self.subTest(groups=groups):
                run_command.return_value = "\n".join(
                    f"{group}\tFive Hour Limit Remaining\t80%\t2026-10-19T11:00:00Z"
                    for group in groups
                )
                result = query_antigravity_subscription({})
                self.assertEqual({w.quota_group for w in result.windows}, set(groups))
                self.assertTrue(all(w.label == "5시간" for w in result.windows))

    @patch("subscription_usage._run_text_command")
    @patch("subscription_usage._command_path", return_value="agy.exe")
    def test_antigravity_ignores_invalid_percentages_and_unknown_periods(self, command_path, run_command):
        for period, percent in (("Weekly Limit Remaining", "nan"), ("Weekly Limit Remaining", "inf"),
                                ("Weekly Limit Remaining", "101"), ("Weekly Limit Remaining", "-1"),
                                ("Monthly Limit Remaining", "20")):
            with self.subTest(period=period, percent=percent):
                run_command.return_value = (
                    "Gemini Models\tWeekly Limit Remaining\t65%\t2026-10-24T00:00:00Z\n"
                    f"Gemini 4 Argon\t{period}\t{percent}%\t2026-10-25T09:00:00Z"
                )
                result = query_antigravity_subscription({})
                self.assertEqual(len(result.windows), 1)
                self.assertIn("조회 미지원", result.action_hint)

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

    @patch("subscription_usage.urllib.request.build_opener")
    def test_grok_no_quota_headers_returns_no_quota(self, build_opener):
        mock_response = io.StringIO('{"name": "test-key"}')
        mock_response.headers = {}
        build_opener.return_value.open.return_value.__enter__.return_value = mock_response

        result = query_grok_subscription({"api_key": "xai-mock-key"})

        self.assertEqual(result.status_kind, StatusKind.NO_QUOTA)
        self.assertEqual(result.status_text, "연결됨 · 구독 사용량 미지원")
        self.assertEqual(result.windows, ())
        self.assertEqual(result.used_percent, 0.0)

    @patch("subscription_usage.urllib.request.build_opener")
    def test_grok_with_quota_headers_returns_ok_snapshot(self, build_opener):
        mock_response = io.StringIO('{"name": "test-key"}')
        mock_response.headers = {
            "x-ratelimit-remaining-requests": "20",
            "x-ratelimit-limit-requests": "100",
            "x-ratelimit-reset-requests": "1800",
        }
        build_opener.return_value.open.return_value.__enter__.return_value = mock_response

        result = query_grok_subscription({"api_key": "xai-mock-key"})

        self.assertEqual(result.status_kind, StatusKind.OK)
        self.assertEqual(result.used_percent, 80.0)
        self.assertEqual(len(result.windows), 1)
        self.assertEqual(result.windows[0].label, "요청")
        self.assertEqual(result.windows[0].used_percent, 80.0)

    @patch("subscription_usage._run_copilot_probe_script")
    def test_copilot_empty_quotas_returns_no_quota(self, run_probe):
        run_probe.return_value = {"quotas": {}}

        result = query_copilot_subscription({})

        self.assertEqual(result.status_kind, StatusKind.NO_QUOTA)
        self.assertEqual(result.status_text, "조회 가능한 한도 없음")
        self.assertEqual(result.windows, ())
        self.assertEqual(result.used_percent, 0.0)

    def test_subscription_usage_error_status_kind_inference(self):
        err_login = SubscriptionUsageError("로그인이 필요합니다")
        self.assertEqual(err_login.status_kind, StatusKind.LOGIN_REQUIRED)

        err_rate = SubscriptionUsageError("사용량 조회 제한 (429)")
        self.assertEqual(err_rate.status_kind, StatusKind.RATE_LIMITED)

        err_timeout = SubscriptionUsageError("연결 시간 초과")
        self.assertEqual(err_timeout.status_kind, StatusKind.TIMEOUT)

        err_missing = SubscriptionUsageError("CLI 명령을 찾을 수 없습니다")
        self.assertEqual(err_missing.status_kind, StatusKind.NOT_INSTALLED)

        err_server = SubscriptionUsageError("서버 응답 오류 (500)")
        self.assertEqual(err_server.status_kind, StatusKind.SERVER_ERROR)

        err_format = SubscriptionUsageError("응답 형식 오류")
        self.assertEqual(err_format.status_kind, StatusKind.FORMAT_ERROR)

        err_no_quota = SubscriptionUsageError("구독 한도 없음")
        self.assertEqual(err_no_quota.status_kind, StatusKind.NO_QUOTA)


class ProviderCacheTests(unittest.TestCase):
    @patch("providers.query_claude_subscription")
    def test_claude_rate_limit_cooldown_survives_manual_refresh(self, query):
        from providers import ClaudeProvider

        query.side_effect = SubscriptionUsageError(
            "Claude 사용량 조회 제한 · 잠시 후 다시 시도하세요"
        )
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
