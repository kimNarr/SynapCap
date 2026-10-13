from __future__ import annotations

import json
import math
import os
import posixpath
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Sequence

CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


class SubscriptionUsageError(RuntimeError):
    """A safe, user-facing error raised by a local subscription adapter."""


def _hidden_process_kwargs() -> dict[str, Any]:
    """Prevent short-lived CLI and PowerShell windows from flashing on Windows."""
    if os.name != "nt":
        return {}

    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup_info.wShowWindow = subprocess.SW_HIDE
    return {
        "creationflags": CREATE_NO_WINDOW,
        "startupinfo": startup_info,
    }


@dataclass(frozen=True)
class SubscriptionWindow:
    label: str
    used_percent: float
    reset_text: str
    remaining_percent: Optional[float] = None


@dataclass(frozen=True)
class SubscriptionSnapshot:
    used_percent: float
    model_name: str
    status_text: str
    windows: tuple[SubscriptionWindow, ...] = ()


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, round(float(value), 1)))


def _cli_search_directories() -> tuple[Path, ...]:
    """Return CLI locations that GUI apps do not inherit from the login shell."""
    home = Path.home()
    directories: list[Path] = []

    for value in os.environ.get("PATH", "").split(os.pathsep):
        if value:
            directory = Path(value).expanduser()
            if sys.platform != "darwin" or _safe_macos_cli_directory(directory, home):
                directories.append(directory)

    directories.extend(
        (
            home / ".local" / "bin",
            home / ".npm-global" / "bin",
            home / ".local" / "share" / "pnpm",
            home / ".bun" / "bin",
            home / ".volta" / "bin",
            home / ".asdf" / "shims",
        )
    )
    if sys.platform == "darwin":
        directories.extend((Path("/opt/homebrew/bin"), Path("/usr/local/bin")))
        directories.extend((home / ".nvm" / "versions" / "node").glob("*/bin"))

    unique: list[Path] = []
    seen: set[str] = set()
    for directory in directories:
        key = os.path.normcase(str(directory))
        if key not in seen:
            seen.add(key)
            unique.append(directory)
    return tuple(unique)


def _safe_macos_cli_directory(directory: Path, home: Path) -> bool:
    """Avoid probing protected folders and mounted volumes while locating CLIs."""
    path = posixpath.abspath(str(directory).replace("\\", "/"))
    home_path = posixpath.abspath(str(home).replace("\\", "/"))
    protected_roots = (
        posixpath.join(home_path, "Desktop"),
        posixpath.join(home_path, "Documents"),
        posixpath.join(home_path, "Downloads"),
        posixpath.join(home_path, "Movies"),
        posixpath.join(home_path, "Music"),
        posixpath.join(home_path, "Pictures"),
        "/Network",
        "/Volumes",
        "/net",
    )
    return not any(path == root or path.startswith(root + "/") for root in protected_roots)


def _cli_search_path() -> str:
    return os.pathsep.join(str(path) for path in _cli_search_directories())


def _cli_environment() -> dict[str, str]:
    env = os.environ.copy()
    env["PATH"] = _cli_search_path()
    env.update({"NO_COLOR": "1", "TERM": "dumb", "LANG": "en_US.UTF-8"})
    return env


def _usage_probe_path() -> str:
    """Keep only OS tools available to the isolated usage subprocess."""
    directories: list[Path] = []
    if os.name == "nt":
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        directories.extend((system_root / "System32", system_root))
    else:
        directories.extend((Path("/usr/bin"), Path("/bin"), Path("/usr/sbin"), Path("/sbin")))

    unique: list[str] = []
    seen: set[str] = set()
    for directory in directories:
        value = str(directory)
        key = os.path.normcase(value)
        if key not in seen:
            seen.add(key)
            unique.append(value)
    return os.pathsep.join(unique)


def _command_path(
    configured: Optional[str],
    executable_name: str,
    known_paths: Sequence[Path] = (),
) -> Path:
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(os.path.expandvars(configured)).expanduser())

    discovered = shutil.which(executable_name, path=_cli_search_path())
    if discovered:
        candidates.append(Path(discovered))

    candidates.extend(known_paths)
    for candidate in candidates:
        try:
            if candidate.is_file():
                return candidate.resolve()
        except OSError:
            continue

    raise SubscriptionUsageError(f"{executable_name} CLI를 찾을 수 없음")


def _run_text_command(
    command: Sequence[str],
    timeout_sec: float,
    cwd: Optional[Path] = None,
    env_overrides: Optional[dict[str, str]] = None,
) -> str:
    env = _cli_environment()
    if env_overrides:
        env.update(env_overrides)
    process: Optional[subprocess.Popen[str]] = None
    try:
        process = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            cwd=str(cwd) if cwd else None,
            **_hidden_process_kwargs(),
        )
        stdout, _ = process.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        if process is not None:
            _stop_process_tree(process)
        raise SubscriptionUsageError("사용량 조회 시간 초과") from exc
    except OSError as exc:
        raise SubscriptionUsageError("로컬 CLI 실행 실패") from exc

    output = ANSI_ESCAPE_RE.sub("", stdout or "").strip()
    if process.returncode != 0 and not output:
        raise SubscriptionUsageError("로컬 CLI 로그인 필요")
    if not output:
        raise SubscriptionUsageError("사용량 응답 없음")
    return output


def _stop_process_tree(process: subprocess.Popen[Any]) -> None:
    """Stop the CLI and MCP descendants that it may have started."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
                **_hidden_process_kwargs(),
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    if process.poll() is None:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        pass


def _format_epoch_reset(value: Any) -> str:
    try:
        reset_at = datetime.fromtimestamp(float(value), tz=timezone.utc).astimezone()
        return reset_at.strftime("%-m/%-d %H:%M")
    except (OSError, TypeError, ValueError):
        try:
            reset_at = datetime.fromtimestamp(float(value), tz=timezone.utc).astimezone()
            return f"{reset_at.month}/{reset_at.day} {reset_at:%H:%M}"
        except (OSError, TypeError, ValueError):
            return "리셋 시각 미상"


def _format_iso_reset(value: str) -> str:
    try:
        reset_at = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
        return f"{reset_at.month}/{reset_at.day} {reset_at:%H:%M}"
    except (TypeError, ValueError):
        return "리셋 시각 미상"


def _window_label(minutes: Any) -> str:
    try:
        mins = int(minutes)
    except (TypeError, ValueError):
        return "현재 한도"
    if mins == 10080:
        return "주간"
    if mins % 1440 == 0:
        return f"{mins // 1440}일"
    if mins % 60 == 0:
        return f"{mins // 60}시간"
    return f"{mins}분"


def _codex_cache_copy(source: Path) -> Path:
    """Make Store-packaged Codex executable runnable by a normal desktop app."""
    if "windowsapps" not in str(source).lower():
        return source

    try:
        stat = source.stat()
        version_key = f"{stat.st_size}-{stat.st_mtime_ns}"
    except OSError as exc:
        raise SubscriptionUsageError("Codex 실행 파일 접근 실패") from exc

    cache_base = Path(
        os.environ.get("LOCALAPPDATA") or os.path.join(tempfile.gettempdir(), "SynapCap")
    )
    cache_dir = cache_base / "SynapCap" / "bin"
    target = cache_dir / f"codex-app-server-{version_key}.exe"
    if target.is_file() and target.stat().st_size == stat.st_size:
        return target

    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        temp_target = cache_dir / f".{target.name}.{os.getpid()}.tmp"
        shutil.copy2(source, temp_target)
        os.replace(temp_target, target)
        return target
    except OSError as exc:
        raise SubscriptionUsageError("Codex 로컬 실행 준비 실패") from exc


def _find_codex_command(configured: Optional[str]) -> Path:
    try:
        return _command_path(configured, "codex")
    except SubscriptionUsageError:
        pass

    local_app_data = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    cached = sorted(
        (local_app_data / "SynapCap" / "bin").glob("codex-app-server-*.exe"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if cached:
        return cached[0]

    # The Microsoft Store package has an execute ACL tied to the Codex app
    # identity, and its directory is not always enumerable by desktop apps.
    # Querying the user's running Codex process gives us the installed path;
    # _codex_cache_copy then prepares a normal desktop-executable copy.
    if os.name == "nt":
        powershell = shutil.which("powershell") or shutil.which("powershell.exe")
        if powershell:
            query = (
                "$p=Get-CimInstance Win32_Process -Filter \"Name='codex.exe'\" "
                "-ErrorAction SilentlyContinue | Select-Object -First 1; "
                "if($p){$p.ExecutablePath}"
            )
            try:
                completed = subprocess.run(
                    [powershell, "-NoProfile", "-NonInteractive", "-Command", query],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=5,
                    check=False,
                    **_hidden_process_kwargs(),
                )
                candidate = Path((completed.stdout or "").strip())
                if candidate.is_file():
                    return candidate
            except (OSError, subprocess.TimeoutExpired):
                pass

    if sys.platform == "win32":
        raise SubscriptionUsageError("Codex 앱 또는 CLI를 찾을 수 없음")
    raise SubscriptionUsageError("Codex CLI를 찾을 수 없음")


def _stop_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=2)


def _read_codex_app_server(executable: Path, timeout_sec: float) -> dict[str, Any]:
    try:
        process = subprocess.Popen(
            [str(executable), "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            env=_cli_environment(),
            **_hidden_process_kwargs(),
        )
    except OSError as exc:
        raise SubscriptionUsageError("Codex App Server 실행 실패") from exc

    if process.stdin is None or process.stdout is None:
        _stop_process(process)
        raise SubscriptionUsageError("Codex App Server 연결 실패")

    stdout = process.stdout
    lines: queue.Queue[Optional[str]] = queue.Queue()

    def read_stdout() -> None:
        try:
            for line in stdout:
                lines.put(line)
        finally:
            lines.put(None)

    reader = threading.Thread(target=read_stdout, daemon=True)
    reader.start()

    requests = (
        {
            "method": "initialize",
            "id": 0,
            "params": {
                "clientInfo": {
                    "name": "synapcap",
                    "title": "SynapCap",
                    "version": "0.2.0",
                }
            },
        },
        {"method": "initialized", "params": {}},
        {"method": "account/rateLimits/read", "id": 1, "params": {}},
    )

    try:
        for request in requests:
            process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
        process.stdin.flush()

        deadline = time.monotonic() + timeout_sec
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise SubscriptionUsageError("Codex 사용량 조회 시간 초과")
            try:
                line = lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise SubscriptionUsageError("Codex 사용량 조회 시간 초과") from exc
            if line is None:
                raise SubscriptionUsageError("Codex App Server 응답 종료")
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") != 1:
                continue
            if message.get("error"):
                raise SubscriptionUsageError("Codex 로그인 또는 사용량 조회 실패")
            result = message.get("result")
            if not isinstance(result, dict):
                raise SubscriptionUsageError("Codex 사용량 형식 오류")
            return result
    finally:
        try:
            process.stdin.close()
        except OSError:
            pass
        _stop_process(process)


def query_codex_subscription(config: dict[str, Any]) -> SubscriptionSnapshot:
    source = _find_codex_command(config.get("command"))
    executable = _codex_cache_copy(source)
    result = _read_codex_app_server(
        executable,
        float(config.get("timeout_sec", 20)),
    )

    rate_limits = result.get("rateLimits")
    if not isinstance(rate_limits, dict):
        by_id = result.get("rateLimitsByLimitId") or {}
        rate_limits = by_id.get(config.get("limit_id", "codex"))
    if not isinstance(rate_limits, dict):
        raise SubscriptionUsageError("Codex 구독 한도 없음")

    windows = [
        window
        for window in (rate_limits.get("primary"), rate_limits.get("secondary"))
        if isinstance(window, dict) and window.get("usedPercent") is not None
    ]
    if not windows:
        raise SubscriptionUsageError("Codex 사용률 없음")

    active = max(windows, key=lambda item: float(item.get("usedPercent", 0)))
    used = _clamp_percent(float(active.get("usedPercent", 0)))
    window = _window_label(active.get("windowDurationMins"))
    reset = _format_epoch_reset(active.get("resetsAt"))
    plan = str(rate_limits.get("planType") or "ChatGPT").replace("_", " ").title()
    display_windows = tuple(
        SubscriptionWindow(
            label=_window_label(item.get("windowDurationMins")),
            used_percent=_clamp_percent(float(item.get("usedPercent", 0))),
            remaining_percent=_clamp_percent(100.0 - float(item.get("usedPercent", 0))),
            reset_text=_format_epoch_reset(item.get("resetsAt")),
        )
        for item in sorted(
            windows,
            key=lambda value: int(value.get("windowDurationMins") or 0),
        )
    )
    return SubscriptionSnapshot(
        used_percent=used,
        model_name=f"Codex ({plan})",
        status_text=f"{window} · {reset} 리셋",
        windows=display_windows,
    )


def query_antigravity_subscription(config: dict[str, Any]) -> SubscriptionSnapshot:
    home = Path.home()
    local_app_data = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    executable = _command_path(
        config.get("command"),
        "agy",
        (
            home / ".local" / "bin" / "agy",
            local_app_data / "agy" / "bin" / "agy.exe",
        ),
    )
    work_dir = Path(tempfile.gettempdir()) / "SynapCap" / "antigravity"
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        env_overrides = {
            "PATH": _usage_probe_path(),
            # The CLI otherwise spawns a detached self-updater even for the
            # short-lived /usage probe.  Besides being unnecessary here, that
            # child process can briefly flash a console window on Windows.
            "AGY_CLI_DISABLE_AUTO_UPDATE": "true",
        }
    except OSError as exc:
        raise SubscriptionUsageError("Antigravity 임시 실행 환경 준비 실패") from exc
    output = _run_text_command(
        [
            str(executable),
            "--sandbox",
            "--log-file",
            str(work_dir / "agy.log"),
            "--print",
            "/usage",
            "--print-timeout",
            "25s",
        ],
        float(config.get("timeout_sec", 35)),
        cwd=work_dir,
        env_overrides=env_overrides,
    )

    rows: list[dict[str, Any]] = []
    for line in output.splitlines():
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) != 4 or not parts[2].endswith("%"):
            continue
        try:
            remaining = float(parts[2][:-1])
        except ValueError:
            continue
        rows.append(
            {
                "group": parts[0],
                "window": parts[1],
                "remaining": _clamp_percent(remaining),
                "resets_at": parts[3],
            }
        )

    if not rows:
        raise SubscriptionUsageError("Antigravity 사용량 형식 오류")

    requested_group = str(config.get("quota_group", "Gemini Models")).lower()
    group_rows = [row for row in rows if requested_group in row["group"].lower()]
    if not group_rows:
        group_rows = [row for row in rows if "gemini" in row["group"].lower()]
    if not group_rows:
        first_group = rows[0]["group"]
        group_rows = [row for row in rows if row["group"] == first_group]

    active = min(group_rows, key=lambda item: item["remaining"])
    used = _clamp_percent(100.0 - active["remaining"])
    window = "주간" if "weekly" in active["window"].lower() else "5시간"
    reset = _format_iso_reset(active["resets_at"])
    display_windows = tuple(
        SubscriptionWindow(
            label=("주간" if "weekly" in row["window"].lower() else "5시간"),
            used_percent=_clamp_percent(100.0 - row["remaining"]),
            remaining_percent=row["remaining"],
            reset_text=_format_iso_reset(row["resets_at"]),
        )
        for row in sorted(
            group_rows,
            key=lambda value: 1 if "weekly" in value["window"].lower() else 0,
        )
    )
    return SubscriptionSnapshot(
        used_percent=used,
        model_name=active["group"],
        status_text=f"{window} {active['remaining']:.0f}% 남음 · {reset}",
        windows=display_windows,
    )


CLAUDE_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


def _format_claude_reset(value: str) -> str:
    match = re.search(
        r"([A-Za-z]{3})\s+(\d{1,2}),\s+(\d{1,2})(?::(\d{2}))?(am|pm)",
        value,
        re.IGNORECASE,
    )
    if not match:
        return value.split("(", 1)[0].strip()
    month = CLAUDE_MONTHS.get(match.group(1).lower())
    if month is None:
        return value.split("(", 1)[0].strip()
    hour = int(match.group(3)) % 12
    if match.group(5).lower() == "pm":
        hour += 12
    minute = int(match.group(4) or 0)
    return f"{month}/{int(match.group(2))} {hour:02d}:{minute:02d}"


def _read_claude_oauth_token() -> str:
    """Reuse Claude Code's login without logging or copying credentials."""
    config_dir = Path(os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))).expanduser()
    try:
        if sys.platform == "darwin" and not (config_dir / ".credentials.json").is_file():
            result = subprocess.run(
                ["/usr/bin/security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
                capture_output=True, text=True, timeout=5, check=False,
            )
            if result.returncode:
                raise SubscriptionUsageError("Claude Code 로그인 정보 접근 실패")
            credentials = json.loads(result.stdout)
        else:
            credentials = json.loads((config_dir / ".credentials.json").read_text(encoding="utf-8"))
        oauth = credentials.get("claudeAiOauth", {})
        token = oauth.get("accessToken")
        if not isinstance(token, str) or not token:
            raise SubscriptionUsageError("Claude Code 구독 로그인 필요")
        return token
    except (OSError, ValueError, AttributeError, subprocess.TimeoutExpired) as exc:
        raise SubscriptionUsageError("Claude Code 로그인 정보 접근 실패") from exc


class _NoUsageRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward the bearer credential to a redirect destination.
        return None


def _query_claude_oauth_usage(timeout_sec: float) -> SubscriptionSnapshot:
    request = urllib.request.Request(
        "https://api.anthropic.com/api/oauth/usage",
        headers={
            "Authorization": "Bearer " + _read_claude_oauth_token(),
            "anthropic-beta": "oauth-2025-04-20",
            "Accept": "application/json",
        },
    )
    try:
        opener = urllib.request.build_opener(_NoUsageRedirect())
        with opener.open(request, timeout=timeout_sec) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            message = "Claude Code 로그인 갱신 필요 · Claude Code에서 다시 로그인하세요"
        elif exc.code == 429:
            message = "Claude 사용량 조회 제한 · 잠시 후 다시 시도하세요"
        else:
            message = f"Claude 사용량 서버 오류 ({exc.code})"
        raise SubscriptionUsageError(message) from None
    except (OSError, ValueError) as exc:
        raise SubscriptionUsageError("Claude 사용량 서버 응답 오류") from exc

    windows = []
    if not isinstance(data, dict):
        raise SubscriptionUsageError("Claude 사용률 형식 변경됨")
    for key, label in (("five_hour", "5시간"), ("seven_day", "주간")):
        window = data.get(key)
        if not isinstance(window, dict):
            continue
        value = window.get("utilization")
        if (
            isinstance(value, bool) or not isinstance(value, (int, float))
            or not math.isfinite(value) or not 0 <= value <= 100
        ):
            raise SubscriptionUsageError("Claude 사용률 형식 변경됨")
        used = _clamp_percent(value)
        reset = window.get("resets_at")
        if reset is not None and not isinstance(reset, str):
            raise SubscriptionUsageError("Claude 사용률 형식 변경됨")
        windows.append(SubscriptionWindow(
            label, used, _format_iso_reset(reset) if reset else "", 100.0 - used,
        ))
    if not windows:
        raise SubscriptionUsageError("Claude 구독 사용량 한도 없음")
    active = max(windows, key=lambda window: window.used_percent)
    return SubscriptionSnapshot(
        active.used_percent, "Claude Code", f"{active.label} · {active.reset_text} 리셋",
        tuple(windows),
    )


def query_claude_subscription(config: dict[str, Any]) -> SubscriptionSnapshot:
    home = Path.home()
    app_data = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    installed_versions = sorted(
        (app_data / "Claude" / "claude-code").glob("*/claude.exe"),
        reverse=True,
    )
    executable = _command_path(
        config.get("command"),
        "claude",
        (
            home / ".local" / "bin" / "claude",
            home / ".local" / "bin" / "claude.exe",
            *installed_versions,
        ),
    )
    work_dir = Path(tempfile.gettempdir()) / "SynapCap" / "claude"
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        mcp_config = work_dir / "empty-mcp.json"
        mcp_config_text = '{"mcpServers":{}}\n'
        if not mcp_config.is_file() or mcp_config.read_text(encoding="utf-8") != mcp_config_text:
            mcp_config.write_text(mcp_config_text, encoding="utf-8")
    except OSError as exc:
        raise SubscriptionUsageError("Claude 임시 실행 환경 준비 실패") from exc

    output = _run_text_command(
        [
            str(executable),
            "--safe-mode",
            "--no-chrome",
            "--strict-mcp-config",
            "--mcp-config",
            str(mcp_config),
            "-p",
            "/usage",
            "--output-format",
            "text",
            "--tools",
            "",
            "--no-session-persistence",
        ],
        float(config.get("timeout_sec", 25)),
        cwd=work_dir,
        env_overrides={"MCP_CONNECTION_NONBLOCKING": "true"},
    )

    patterns = (
        (
            "5시간",
            r"Current session:\s*([0-9.]+)% used(?:\s*[·-]\s*resets\s*(.+))?$",
        ),
        ("주간", r"Current week(?:\s*\([^)]*\))?:\s*([0-9.]+)% used\s*[·-]\s*resets\s*(.+)$"),
    )
    windows: list[dict[str, Any]] = []
    for label, pattern in patterns:
        match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
        if match:
            windows.append(
                {
                    "label": label,
                    "used": _clamp_percent(float(match.group(1))),
                    "reset": (_format_claude_reset(match.group(2)) if match.group(2) else ""),
                }
            )

    if not windows:
        if "Total cost:" in output and "Total duration" in output:
            # New CLI versions expose cost-only stats in print mode. The
            # subscription endpoint supplies the actual five-hour/week limits.
            return _query_claude_oauth_usage(float(config.get("timeout_sec", 25)))
        if "subscription" in output.lower():
            raise SubscriptionUsageError("Claude 사용률 형식 변경됨")
        raise SubscriptionUsageError("Claude Code 로그인 필요")

    active = max(windows, key=lambda item: item["used"])
    return SubscriptionSnapshot(
        used_percent=active["used"],
        model_name="Claude Code",
        status_text=f"{active['label']} · {active['reset']} 리셋",
        windows=tuple(
            SubscriptionWindow(
                label=item["label"],
                used_percent=item["used"],
                remaining_percent=_clamp_percent(100.0 - item["used"]),
                reset_text=item["reset"],
            )
            for item in windows
        ),
    )


# ==========================================
# 4. GitHub Copilot Subscription
# ==========================================
def _run_copilot_probe_script(account: Optional[str], timeout_sec: float) -> dict[str, Any]:
    """Run Copilot quota probe in a clean subprocess with hidden window."""
    root = Path(__file__).resolve().parent
    script = root / "scripts" / "probe_copilot_usage.py"
    if not script.is_file():
        raise SubscriptionUsageError("Copilot 프로브 스크립트를 찾을 수 없음")

    cmd = [sys.executable, str(script)]
    if account:
        cmd.extend(["--account", str(account)])

    process = None
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=_cli_environment(),
            cwd=str(root),
            **_hidden_process_kwargs(),
        )
        stdout, _ = process.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        if process is not None:
            _stop_process_tree(process)
        raise SubscriptionUsageError("Copilot 사용량 조회 시간 초과") from exc
    except OSError as exc:
        raise SubscriptionUsageError("Copilot 프로브 실행 실패") from exc

    output = (stdout or "").strip()
    if not output:
        raise SubscriptionUsageError("Copilot 응답 없음")

    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise SubscriptionUsageError("Copilot 응답 형식 오류") from exc

    status = data.get("status")
    if status == "github_login_required":
        raise SubscriptionUsageError("GitHub CLI(gh) 로그인 필요")
    if status != "ok":
        msg = data.get("message") or "Copilot 사용량 조회 실패"
        raise SubscriptionUsageError(f"Copilot 조회 실패: {msg}")

    return data


def query_copilot_subscription(config: dict[str, Any]) -> SubscriptionSnapshot:
    account = config.get("account")
    timeout_sec = float(config.get("timeout_sec", 25))
    data = _run_copilot_probe_script(account, timeout_sec)

    quotas = data.get("quotas", {})
    if not quotas:
        return SubscriptionSnapshot(
            used_percent=0.0,
            model_name="GitHub Copilot",
            status_text="조회 가능한 한도 없음",
            windows=(),
        )

    quota_labels = {
        "chat": "채팅",
        "completions": "코드완성",
        "premium_interactions": "프리미엄",
    }

    display_windows: list[SubscriptionWindow] = []
    for key, item in quotas.items():
        if not isinstance(item, dict):
            continue
        label = quota_labels.get(key, key.capitalize())
        included = item.get("included", 0)
        used = item.get("used", 0)
        remaining_pct = float(item.get("remaining_percent", 100.0))
        used_pct = _clamp_percent(100.0 - remaining_pct)
        reset_raw = item.get("reset_at", "")
        reset_text = _format_iso_reset(reset_raw) if reset_raw else ""

        # 프리미엄 한도가 0이고 사용량도 0이면 불필요하게 표시하지 않음
        if key == "premium_interactions" and included == 0 and used == 0:
            continue

        display_windows.append(
            SubscriptionWindow(
                label=label,
                used_percent=used_pct,
                reset_text=reset_text,
                remaining_percent=_clamp_percent(remaining_pct),
            )
        )

    if not display_windows:
        return SubscriptionSnapshot(
            used_percent=0.0,
            model_name="GitHub Copilot",
            status_text="조회 가능한 한도 없음",
            windows=(),
        )

    active = max(display_windows, key=lambda w: (w.used_percent, w.label == "채팅"))
    reset_suffix = f" · {active.reset_text} 리셋" if active.reset_text else ""
    return SubscriptionSnapshot(
        used_percent=active.used_percent,
        model_name="GitHub Copilot",
        status_text=f"{active.label} {active.remaining_percent:.0f}% 남음{reset_suffix}",
        windows=tuple(display_windows),
    )


# ==========================================
# 5. xAI Grok Subscription
# ==========================================
def query_grok_subscription(config: dict[str, Any]) -> SubscriptionSnapshot:
    api_key = config.get("api_key") or os.environ.get("XAI_API_KEY", "")
    api_key = str(api_key).strip()
    if not api_key:
        raise SubscriptionUsageError("xAI API 키 설정 필요")

    timeout_sec = float(config.get("timeout_sec", 15))
    request = urllib.request.Request(
        "https://api.x.ai/v1/api-key",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "User-Agent": "SynapCap/0.3.0",
        },
    )

    try:
        opener = urllib.request.build_opener(_NoUsageRedirect())
        with opener.open(request, timeout=timeout_sec) as response:
            headers = dict(response.headers)
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code in (401, 403):
            raise SubscriptionUsageError("xAI API 키 인증 실패") from None
        if exc.code == 429:
            raise SubscriptionUsageError("xAI 요청 한도 초과 (429)") from None
        raise SubscriptionUsageError(f"xAI 서버 응답 오류 ({exc.code})") from None
    except (OSError, ValueError) as exc:
        raise SubscriptionUsageError("xAI 서버 연결 실패") from exc

    limit_req_str = headers.get("x-ratelimit-limit-requests")
    remaining_req_str = headers.get("x-ratelimit-remaining-requests")
    reset_req_str = headers.get("x-ratelimit-reset-requests")

    windows: list[SubscriptionWindow] = []
    if limit_req_str and remaining_req_str:
        try:
            limit_val = float(limit_req_str)
            rem_val = float(remaining_req_str)
            if limit_val > 0:
                rem_pct = _clamp_percent((rem_val / limit_val) * 100.0)
                used_pct = _clamp_percent(100.0 - rem_pct)
                reset_text = f"{reset_req_str}s 후 리셋" if reset_req_str else ""
                windows.append(
                    SubscriptionWindow(
                        label="요청",
                        used_percent=used_pct,
                        reset_text=reset_text,
                        remaining_percent=rem_pct,
                    )
                )
        except (ValueError, TypeError):
            pass

    key_name = str(body.get("name") or "Grok Key")
    if not windows:
        windows = [
            SubscriptionWindow(
                label="API 가용",
                used_percent=0.0,
                reset_text="정상",
                remaining_percent=100.0,
            )
        ]
        return SubscriptionSnapshot(
            used_percent=0.0,
            model_name=f"Grok ({key_name})",
            status_text="API 키 정상 연결됨 · 가용 100%",
            windows=tuple(windows),
        )

    active = max(windows, key=lambda w: w.used_percent)
    return SubscriptionSnapshot(
        used_percent=active.used_percent,
        model_name=f"Grok ({key_name})",
        status_text=f"{active.label} {active.remaining_percent:.0f}% 남음",
        windows=tuple(windows),
    )
