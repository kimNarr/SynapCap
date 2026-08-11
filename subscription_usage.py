from __future__ import annotations

import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
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


def _command_path(
    configured: Optional[str],
    executable_name: str,
    known_paths: Sequence[Path] = (),
) -> Path:
    candidates: list[Path] = []
    if configured:
        candidates.append(Path(os.path.expandvars(configured)).expanduser())

    discovered = shutil.which(executable_name)
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
    env = os.environ.copy()
    env.update({"NO_COLOR": "1", "TERM": "dumb", "LANG": "en_US.UTF-8"})
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
        os.environ.get("LOCALAPPDATA")
        or os.path.join(tempfile.gettempdir(), "SynapCap")
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

    local_app_data = Path(
        os.environ.get("LOCALAPPDATA")
        or Path.home() / "AppData" / "Local"
    )
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

    raise SubscriptionUsageError("Codex 앱 또는 CLI를 찾을 수 없음")


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
            **_hidden_process_kwargs(),
        )
    except OSError as exc:
        raise SubscriptionUsageError("Codex App Server 실행 실패") from exc

    if process.stdin is None or process.stdout is None:
        _stop_process(process)
        raise SubscriptionUsageError("Codex App Server 연결 실패")

    lines: queue.Queue[Optional[str]] = queue.Queue()

    def read_stdout() -> None:
        try:
            for line in process.stdout:
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
            remaining_percent=_clamp_percent(
                100.0 - float(item.get("usedPercent", 0))
            ),
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
        (local_app_data / "agy" / "bin" / "agy.exe",),
    )
    work_dir = Path(tempfile.gettempdir()) / "SynapCap" / "antigravity"
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        serena_home = work_dir / "serena-home"
        serena_home.mkdir(parents=True, exist_ok=True)
        serena_config = serena_home / "serena_config.yml"
        serena_config_text = (
            "projects: []\n"
            "gui_log_window: false\n"
            "web_dashboard: false\n"
            "web_dashboard_open_on_launch: false\n"
        )
        if (
            not serena_config.is_file()
            or serena_config.read_text(encoding="utf-8") != serena_config_text
        ):
            serena_config.write_text(
                serena_config_text,
                encoding="utf-8",
            )

        env_overrides = {"SERENA_HOME": str(serena_home)}
        serena_command = shutil.which("serena")
        if serena_command and '"' not in serena_command:
            wrapper_dir = work_dir / "hidden-tools"
            wrapper_dir.mkdir(parents=True, exist_ok=True)
            resolved_serena = Path(serena_command).resolve()
            if os.name == "nt":
                serena_wrapper = wrapper_dir / "serena.cmd"
                wrapper_text = (
                    "@echo off\r\n"
                    f'"{resolved_serena}" %* '
                    "--enable-web-dashboard false "
                    "--enable-gui-log-window false "
                    "--open-web-dashboard false\r\n"
                )
            else:
                serena_wrapper = wrapper_dir / "serena"
                wrapper_text = (
                    "#!/bin/sh\n"
                    f'exec "{resolved_serena}" "$@" '
                    "--enable-web-dashboard false "
                    "--enable-gui-log-window false "
                    "--open-web-dashboard false\n"
                )
            if (
                not serena_wrapper.is_file()
                or serena_wrapper.read_text(encoding="utf-8") != wrapper_text
            ):
                serena_wrapper.write_text(wrapper_text, encoding="utf-8")
            if os.name != "nt":
                serena_wrapper.chmod(0o700)
            env_overrides["PATH"] = (
                str(wrapper_dir)
                + os.pathsep
                + os.environ.get("PATH", "")
            )
    except OSError as exc:
        raise SubscriptionUsageError(
            "Antigravity 임시 실행 환경 준비 실패"
        ) from exc
    output = _run_text_command(
        [str(executable), "--print", "/usage", "--print-timeout", "25s"],
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
            label=(
                "주간" if "weekly" in row["window"].lower() else "5시간"
            ),
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
        (home / ".local" / "bin" / "claude.exe", *installed_versions),
    )
    output = _run_text_command(
        [
            str(executable),
            "--safe-mode",
            "--no-chrome",
            "-p",
            "/usage",
            "--output-format",
            "text",
            "--tools",
            "",
            "--no-session-persistence",
        ],
        float(config.get("timeout_sec", 25)),
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
                    "reset": (
                        _format_claude_reset(match.group(2))
                        if match.group(2)
                        else ""
                    ),
                }
            )

    if not windows:
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
