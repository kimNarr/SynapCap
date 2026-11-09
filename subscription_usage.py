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


class StatusKind:
    OK = "ok"
    NOT_INSTALLED = "not_installed"
    LOGIN_REQUIRED = "login_required"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    FORMAT_ERROR = "format_error"
    NO_QUOTA = "no_quota"


STATUS_BADGE_LABELS: dict[str, str] = {
    StatusKind.OK: "정상",
    StatusKind.NOT_INSTALLED: "미설치",
    StatusKind.LOGIN_REQUIRED: "로그인 필요",
    StatusKind.TIMEOUT: "시간 초과",
    StatusKind.RATE_LIMITED: "조회 제한",
    StatusKind.SERVER_ERROR: "서버 오류",
    StatusKind.FORMAT_ERROR: "형식 오류",
    StatusKind.NO_QUOTA: "한도 없음",
}


class SubscriptionUsageError(RuntimeError):
    """A safe, user-facing error raised by a local subscription adapter."""

    def __init__(
        self,
        message: str,
        status_kind: Optional[str] = None,
        retry_after_sec: Optional[int] = None,
        action_hint: Optional[str] = None,
    ):
        super().__init__(message)
        if status_kind is None:
            if "조회 제한" in message or "429" in message:
                status_kind = StatusKind.RATE_LIMITED
            elif "로그인" in message or "인증 실패" in message:
                status_kind = StatusKind.LOGIN_REQUIRED
            elif "시간 초과" in message:
                status_kind = StatusKind.TIMEOUT
            elif "찾을 수 없" in message or "미설치" in message:
                status_kind = StatusKind.NOT_INSTALLED
            elif "한도 없음" in message:
                status_kind = StatusKind.NO_QUOTA
            elif "형식" in message:
                status_kind = StatusKind.FORMAT_ERROR
            else:
                status_kind = StatusKind.SERVER_ERROR
        self.status_kind = status_kind
        self.retry_after_sec = retry_after_sec
        self.action_hint = action_hint


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
    unlimited: bool = False
    quota_group: str = ""


@dataclass(frozen=True)
class SubscriptionSnapshot:
    used_percent: float
    model_name: str
    status_text: str
    windows: tuple[SubscriptionWindow, ...] = ()
    status_kind: str = StatusKind.OK
    retry_after_sec: Optional[int] = None
    action_hint: Optional[str] = None


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

    raise SubscriptionUsageError(
        f"{executable_name} CLI를 찾을 수 없음",
        status_kind=StatusKind.NOT_INSTALLED,
        action_hint=f"{executable_name} CLI 또는 관련 앱을 설치하세요.",
    )


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
        raise SubscriptionUsageError(
            "사용량 조회 시간 초과",
            status_kind=StatusKind.TIMEOUT,
            action_hint="잠시 후 다시 조회하세요.",
        ) from exc
    except OSError as exc:
        raise SubscriptionUsageError(
            "로컬 CLI 실행 실패",
            status_kind=StatusKind.SERVER_ERROR,
            action_hint="실행 권한 및 설치 상태를 확인하세요.",
        ) from exc

    output = ANSI_ESCAPE_RE.sub("", stdout or "").strip()
    if process.returncode != 0 and not output:
        raise SubscriptionUsageError(
            "로컬 CLI 로그인 필요",
            status_kind=StatusKind.LOGIN_REQUIRED,
            action_hint="터미널에서 로그인 명령을 실행하세요.",
        )
    if not output:
        raise SubscriptionUsageError(
            "사용량 응답 없음",
            status_kind=StatusKind.FORMAT_ERROR,
            action_hint="CLI 응답을 확인하세요.",
        )
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
        raise SubscriptionUsageError(
            "Codex 앱 또는 CLI를 찾을 수 없음",
            status_kind=StatusKind.NOT_INSTALLED,
            action_hint="ChatGPT 데스크톱 앱 또는 Codex CLI를 설치하세요.",
        )
    raise SubscriptionUsageError(
        "Codex CLI를 찾을 수 없음",
        status_kind=StatusKind.NOT_INSTALLED,
        action_hint="Codex CLI를 설치하세요.",
    )


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
        raise SubscriptionUsageError(
            "Codex App Server 실행 실패",
            status_kind=StatusKind.SERVER_ERROR,
            action_hint="Codex 실행 권한을 확인하세요.",
        ) from exc

    if process.stdin is None or process.stdout is None:
        _stop_process(process)
        raise SubscriptionUsageError(
            "Codex App Server 연결 실패",
            status_kind=StatusKind.SERVER_ERROR,
        )

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
                raise SubscriptionUsageError(
                    "Codex 사용량 조회 시간 초과",
                    status_kind=StatusKind.TIMEOUT,
                    action_hint="잠시 후 다시 조회하세요.",
                )
            try:
                line = lines.get(timeout=remaining)
            except queue.Empty as exc:
                raise SubscriptionUsageError(
                    "Codex 사용량 조회 시간 초과",
                    status_kind=StatusKind.TIMEOUT,
                    action_hint="잠시 후 다시 조회하세요.",
                ) from exc
            if line is None:
                raise SubscriptionUsageError(
                    "Codex App Server 응답 종료",
                    status_kind=StatusKind.SERVER_ERROR,
                )
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") != 1:
                continue
            if message.get("error"):
                raise SubscriptionUsageError(
                    "Codex 로그인 또는 사용량 조회 실패",
                    status_kind=StatusKind.LOGIN_REQUIRED,
                    action_hint="Codex를 실행해 ChatGPT 계정으로 로그인하세요.",
                )
            result = message.get("result")
            if not isinstance(result, dict):
                raise SubscriptionUsageError(
                    "Codex 사용량 형식 오류",
                    status_kind=StatusKind.FORMAT_ERROR,
                )
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
    unverified_groups: set[str] = set()
    for line in output.splitlines():
        parts = [part.strip() for part in line.split("\t")]
        if len(parts) != 4 or not parts[2].endswith("%"):
            continue
        try:
            percent = float(parts[2][:-1])
        except ValueError:
            continue
        if not math.isfinite(percent) or not 0 <= percent <= 100:
            continue
        window_name = parts[1].casefold()
        if "weekly" in window_name:
            period = "주간"
        elif "five hour" in window_name or "5 hour" in window_name:
            period = "5시간"
        else:
            continue
        # The desktop's Argon title does not say whether its percentage is
        # remaining or used. Only accept a CLI row that states the semantics.
        if "remaining" in window_name:
            remaining = percent
        elif "used" in window_name:
            remaining = 100.0 - percent
        else:
            unverified_groups.add(parts[0])
            continue
        rows.append(
            {
                "group": parts[0],
                "window": period,
                "remaining": _clamp_percent(remaining),
                "resets_at": parts[3],
            }
        )

    if not rows:
        raise SubscriptionUsageError("Antigravity 사용량 형식 오류")

    requested_group = str(config.get("quota_group", "Gemini Models")).strip().casefold()
    # The legacy default selects the Gemini family, including independently
    # reported Argon limits. A custom selector remains an exact group match.
    gemini_family = requested_group in {"gemini models", "gemini"}
    group_rows = [
        row for row in rows
        if (
            row["group"].casefold().startswith("gemini ")
            if gemini_family else row["group"].casefold() == requested_group
        )
    ]
    if not group_rows:
        raise SubscriptionUsageError(
            "Antigravity 요청 한도 그룹을 찾을 수 없습니다",
            status_kind=StatusKind.FORMAT_ERROR,
            action_hint="CLI /usage에 요청한 한도 그룹이 있는지 확인하세요.",
        )

    active = min(group_rows, key=lambda item: item["remaining"])
    used = _clamp_percent(100.0 - active["remaining"])
    window = active["window"]
    reset = _format_iso_reset(active["resets_at"])
    display_windows = tuple(
        SubscriptionWindow(
            label=row["window"],
            used_percent=_clamp_percent(100.0 - row["remaining"]),
            remaining_percent=row["remaining"],
            reset_text=_format_iso_reset(row["resets_at"]),
            quota_group=row["group"],
        )
        for row in sorted(
            group_rows,
            key=lambda value: (
                value["group"].casefold() != requested_group,
                value["group"].casefold(),
                value["window"] != "5시간",
            ),
        )
    )
    argon_supported = any("argon" in row["group"].casefold() for row in group_rows)
    hint = None
    if gemini_family and not argon_supported:
        reason = (
            "CLI 응답에서 잔여량·사용량 기준을 확인할 수 없습니다."
            if any("argon" in group.casefold() for group in unverified_groups)
            else "CLI가 별도 한도를 제공하지 않습니다."
        )
        hint = f"Argon 조회 미지원: {reason}"
    return SubscriptionSnapshot(
        used_percent=used,
        model_name=active["group"],
        status_text=f"{active['group']} · {window} {active['remaining']:.0f}% 남음 · {reset}",
        windows=display_windows,
        action_hint=hint,
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
    config_dir = Path(
        os.environ.get("CLAUDE_CONFIG_DIR", str(Path.home() / ".claude"))
    ).expanduser()
    try:
        if sys.platform == "darwin" and not (config_dir / ".credentials.json").is_file():
            result = subprocess.run(
                [
                    "/usr/bin/security",
                    "find-generic-password",
                    "-s",
                    "Claude Code-credentials",
                    "-w",
                ],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode:
                raise SubscriptionUsageError(
                    "Claude Code 로그인 정보 접근 실패",
                    status_kind=StatusKind.LOGIN_REQUIRED,
                    action_hint="claude auth login을 실행해 로그인하세요.",
                )
            credentials = json.loads(result.stdout)
        else:
            credentials = json.loads((config_dir / ".credentials.json").read_text(encoding="utf-8"))
        oauth = credentials.get("claudeAiOauth", {})
        token = oauth.get("accessToken")
        if not isinstance(token, str) or not token:
            raise SubscriptionUsageError(
                "Claude Code 구독 로그인 필요",
                status_kind=StatusKind.LOGIN_REQUIRED,
                action_hint="claude auth login을 실행해 Anthropic 계정으로 로그인하세요.",
            )
        return token
    except (OSError, ValueError, AttributeError, subprocess.TimeoutExpired) as exc:
        raise SubscriptionUsageError(
            "Claude Code 로그인 정보 접근 실패",
            status_kind=StatusKind.LOGIN_REQUIRED,
            action_hint="claude auth login을 실행해 로그인하세요.",
        ) from exc


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
            raise SubscriptionUsageError(
                message,
                status_kind=StatusKind.LOGIN_REQUIRED,
                action_hint="claude auth login으로 다시 로그인하세요.",
            ) from None
        elif exc.code == 429:
            message = "Claude 사용량 조회 제한 · 잠시 후 다시 시도하세요"
            raise SubscriptionUsageError(
                message,
                status_kind=StatusKind.RATE_LIMITED,
                retry_after_sec=300,
                action_hint="조회 제한이 해제될 때까지 잠시 대기하세요.",
            ) from None
        else:
            message = f"Claude 사용량 서버 오류 ({exc.code})"
            raise SubscriptionUsageError(
                message,
                status_kind=StatusKind.SERVER_ERROR,
                action_hint="잠시 후 다시 시도하세요.",
            ) from None
    except (OSError, ValueError) as exc:
        raise SubscriptionUsageError(
            "Claude 사용량 서버 응답 오류",
            status_kind=StatusKind.SERVER_ERROR,
        ) from exc

    windows = []
    if not isinstance(data, dict):
        raise SubscriptionUsageError(
            "Claude 사용률 형식 변경됨",
            status_kind=StatusKind.FORMAT_ERROR,
        )
    for key, label in (("five_hour", "5시간"), ("seven_day", "주간")):
        window = data.get(key)
        if not isinstance(window, dict):
            continue
        value = window.get("utilization")
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 100
        ):
            raise SubscriptionUsageError(
                "Claude 사용률 형식 변경됨",
                status_kind=StatusKind.FORMAT_ERROR,
            )
        used = _clamp_percent(value)
        reset = window.get("resets_at")
        if reset is not None and not isinstance(reset, str):
            raise SubscriptionUsageError(
                "Claude 사용률 형식 변경됨",
                status_kind=StatusKind.FORMAT_ERROR,
            )
        windows.append(
            SubscriptionWindow(
                label,
                used,
                _format_iso_reset(reset) if reset else "",
                100.0 - used,
            )
        )
    if not windows:
        raise SubscriptionUsageError(
            "Claude 구독 사용량 한도 없음",
            status_kind=StatusKind.NO_QUOTA,
            action_hint="계정 구독 플랜을 확인하세요.",
        )
    active = max(windows, key=lambda window: window.used_percent)
    return SubscriptionSnapshot(
        active.used_percent,
        "Claude Code",
        f"{active.label} · {active.reset_text} 리셋",
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
        raise SubscriptionUsageError(
            "Claude 임시 실행 환경 준비 실패",
            status_kind=StatusKind.SERVER_ERROR,
        ) from exc

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
            raise SubscriptionUsageError(
                "Claude 사용률 형식 변경됨",
                status_kind=StatusKind.FORMAT_ERROR,
            )
        raise SubscriptionUsageError(
            "Claude Code 로그인 필요",
            status_kind=StatusKind.LOGIN_REQUIRED,
            action_hint="claude auth login을 실행하세요.",
        )

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
    if getattr(sys, "frozen", False):
        executable_dir = Path(sys.executable).resolve().parent
        helper_name = "SynapCapCopilotProbe.exe" if os.name == "nt" else "SynapCapCopilotProbe"
        bundle_root = Path(getattr(sys, "_MEIPASS", executable_dir))
        helper = next(
            (
                candidate
                for candidate in (
                    executable_dir / helper_name,
                    bundle_root / helper_name,
                )
                if candidate.is_file()
            ),
            None,
        )
        if helper is None:
            raise SubscriptionUsageError(
                "Copilot 프로브 구성요소를 찾을 수 없음",
                status_kind=StatusKind.NOT_INSTALLED,
                action_hint="최신 SynapCap 설치본으로 다시 설치하세요.",
            )
        cmd = [str(helper)]
        cwd = helper.parent
    else:
        script = root / "scripts" / "probe_copilot_usage.py"
        if not script.is_file():
            raise SubscriptionUsageError(
                "Copilot 프로브 스크립트를 찾을 수 없음",
                status_kind=StatusKind.NOT_INSTALLED,
                action_hint="프로젝트 파일을 다시 확인하세요.",
            )
        cmd = [sys.executable, str(script)]
        cwd = root
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
            cwd=str(cwd),
            **_hidden_process_kwargs(),
        )
        stdout, _ = process.communicate(timeout=timeout_sec)
    except subprocess.TimeoutExpired as exc:
        if process is not None:
            _stop_process_tree(process)
        raise SubscriptionUsageError(
            "Copilot 사용량 조회 시간 초과",
            status_kind=StatusKind.TIMEOUT,
            action_hint="잠시 후 다시 조회하세요.",
        ) from exc
    except OSError as exc:
        raise SubscriptionUsageError(
            "Copilot 프로브 실행 실패",
            status_kind=StatusKind.SERVER_ERROR,
            action_hint="Python 환경 및 프로브 권한을 확인하세요.",
        ) from exc

    output = (stdout or "").strip()
    if not output:
        raise SubscriptionUsageError(
            "Copilot 응답 없음",
            status_kind=StatusKind.FORMAT_ERROR,
        )

    try:
        data = json.loads(output)
    except json.JSONDecodeError as exc:
        raise SubscriptionUsageError(
            "Copilot 응답 형식 오류",
            status_kind=StatusKind.FORMAT_ERROR,
        ) from exc

    status = data.get("status")
    if status == "gh_not_installed":
        raise SubscriptionUsageError(
            "GitHub CLI(gh)를 찾을 수 없음",
            status_kind=StatusKind.NOT_INSTALLED,
            action_hint="GitHub CLI를 설치한 뒤 gh auth login을 실행하세요.",
        )
    if status == "dependency_missing":
        raise SubscriptionUsageError(
            "Copilot 프로브 의존성 누락",
            status_kind=StatusKind.NOT_INSTALLED,
            action_hint=(
                "설치본은 최신 버전으로 다시 설치하세요. 소스 실행 환경은 "
                "requirements-build.txt의 의존성을 설치하세요."
            ),
        )
    if status == "github_login_required":
        raise SubscriptionUsageError(
            "GitHub CLI(gh) 로그인 필요",
            status_kind=StatusKind.LOGIN_REQUIRED,
            action_hint="gh auth login으로 GitHub 계정에 로그인하세요.",
        )
    if status != "ok":
        msg = data.get("message") or "Copilot 사용량 조회 실패"
        raise SubscriptionUsageError(
            f"Copilot 조회 실패: {msg}",
            status_kind=StatusKind.SERVER_ERROR,
            action_hint="GitHub CLI 연동 및 계정 상태를 확인하세요.",
        )

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
            status_kind=StatusKind.NO_QUOTA,
            action_hint="이 GitHub 계정에는 조회 가능한 Copilot 한도가 없습니다.",
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
        unlimited = bool(item.get("unlimited")) or included == -1
        try:
            remaining_pct = float(item.get("remaining_percent", 100.0))
        except (TypeError, ValueError):
            remaining_pct = 100.0
        used_pct = 0.0 if unlimited else _clamp_percent(100.0 - remaining_pct)
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
                remaining_percent=(None if unlimited else _clamp_percent(remaining_pct)),
                unlimited=unlimited,
            )
        )

    if not display_windows:
        return SubscriptionSnapshot(
            used_percent=0.0,
            model_name="GitHub Copilot",
            status_text="조회 가능한 한도 없음",
            windows=(),
            status_kind=StatusKind.NO_QUOTA,
            action_hint="이 GitHub 계정에는 조회 가능한 Copilot 한도가 없습니다.",
        )

    finite_windows = [window for window in display_windows if not window.unlimited]
    if not finite_windows:
        return SubscriptionSnapshot(
            used_percent=0.0,
            model_name="GitHub Copilot",
            status_text="모든 제공 한도 무제한",
            windows=tuple(display_windows),
        )

    active = max(finite_windows, key=lambda w: (w.used_percent, w.label == "채팅"))
    reset_suffix = f" · {active.reset_text} 리셋" if active.reset_text else ""
    return SubscriptionSnapshot(
        used_percent=active.used_percent,
        model_name="GitHub Copilot",
        status_text=f"{active.label} {active.remaining_percent:.0f}% 남음{reset_suffix}",
        windows=tuple(display_windows),
    )


# ==========================================
# 5. xAI API Rate Limit (not a Grok/SuperGrok subscription quota)
# ==========================================
def query_grok_subscription(config: dict[str, Any]) -> SubscriptionSnapshot:
    api_key = config.get("api_key") or os.environ.get("XAI_API_KEY", "")
    api_key = str(api_key).strip()
    if not api_key:
        raise SubscriptionUsageError(
            "xAI API 키 설정 필요",
            status_kind=StatusKind.LOGIN_REQUIRED,
            action_hint="설정에서 xAI API 키를 입력하거나 XAI_API_KEY 환경변수를 설정하세요.",
        )

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
            raise SubscriptionUsageError(
                "xAI API 키 인증 실패",
                status_kind=StatusKind.LOGIN_REQUIRED,
                action_hint="xAI API 키를 다시 확인하세요.",
            ) from None
        if exc.code == 429:
            raise SubscriptionUsageError(
                "xAI 요청 한도 초과 (429)",
                status_kind=StatusKind.RATE_LIMITED,
                retry_after_sec=60,
                action_hint="xAI 요청 한도가 초과되었습니다. 잠시 대기하세요.",
            ) from None
        raise SubscriptionUsageError(
            f"xAI 서버 응답 오류 ({exc.code})",
            status_kind=StatusKind.SERVER_ERROR,
            action_hint="잠시 후 다시 시도하세요.",
        ) from None
    except (OSError, ValueError) as exc:
        raise SubscriptionUsageError(
            "xAI 서버 연결 실패",
            status_kind=StatusKind.SERVER_ERROR,
        ) from exc

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

    key_name = str(body.get("name") or "xAI API Key")
    if not windows:
        # SC-005: 한도 정보가 없는 API 인증 성공은 가상 100% 잔여량을 생성하지 않고
        # '연결됨 · 구독 사용량 미지원' 및 NO_QUOTA 상태로 명확히 표시한다.
        return SubscriptionSnapshot(
            used_percent=0.0,
            model_name=f"xAI API ({key_name})",
            status_text="연결됨 · 구독 사용량 미지원",
            windows=(),
            status_kind=StatusKind.NO_QUOTA,
            action_hint="xAI API는 현재 구독 잔여량 조회를 지원하지 않습니다.",
        )

    active = max(windows, key=lambda w: w.used_percent)
    return SubscriptionSnapshot(
        used_percent=active.used_percent,
        model_name=f"xAI API ({key_name})",
        status_text=f"{active.label} {active.remaining_percent:.0f}% 남음",
        windows=tuple(windows),
    )
