from __future__ import annotations

import os
import platform
import re
import shutil
import sys
from pathlib import Path

from config import CONFIG_FILE_PATH
from providers import ModelUsage
from version import APP_NAME, APP_VERSION

CLI_DETAILS = {
    "codex": {
        "name": "Codex 앱/CLI",
        "command": "codex",
        "login": "codex를 한 번 실행해 ChatGPT 계정으로 로그인하세요.",
    },
    "antigravity": {
        "name": "Antigravity CLI",
        "command": "agy",
        "login": "agy를 실행한 뒤 브라우저 인증 코드를 터미널에 붙여 넣으세요.",
    },
    "claude": {
        "name": "Claude Code CLI",
        "command": "claude",
        "login": "claude를 실행해 Anthropic 계정으로 로그인하세요.",
    },
    "copilot": {
        "name": "GitHub Copilot",
        "command": "gh",
        "login": "gh auth login을 실행해 GitHub 계정으로 로그인하세요.",
    },
    "grok": {
        "name": "xAI API Rate Limit",
        "command": "xai",
        "login": "설정에 xAI API 키를 입력하거나 XAI_API_KEY 환경변수를 설정하세요. SuperGrok 구독 잔여량은 지원하지 않습니다.",
    },
}

_SECRET_PATTERNS = (
    re.compile(
        r"\b(?:ghp_|github_pat_|sk-|xai-)[A-Za-z0-9_-]{12,}\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~-]{12,}\b", re.IGNORECASE),
)


def sanitize_diagnostic_text(value: object) -> str:
    """Remove user-directory prefixes and obvious credentials from copied reports."""
    text = str(value)
    path_aliases = {
        os.environ.get("LOCALAPPDATA", ""): "<LOCALAPPDATA>",
        os.environ.get("APPDATA", ""): "<APPDATA>",
        os.environ.get("USERPROFILE", ""): "<HOME>",
        str(Path.home()): "<HOME>",
    }
    for raw_path, alias in sorted(
        ((path, alias) for path, alias in path_aliases.items() if path),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        variants = {raw_path, raw_path.replace("\\", "/"), raw_path.replace("/", "\\")}
        for variant in variants:
            text = re.sub(re.escape(variant), alias, text, flags=re.IGNORECASE)
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("<REDACTED>", text)
    return text


def _runtime_details() -> tuple[str, str, str]:
    system = platform.system() or sys.platform
    release = platform.release() or "unknown"
    machine = platform.machine() or "unknown"
    runtime = f"{system} {release} ({machine})"
    mode = "배포 번들" if getattr(sys, "frozen", False) else "소스/개발 환경"
    python_version = platform.python_version()
    return runtime, mode, python_version


def _candidate_paths(provider_type: str, config: dict) -> list[Path]:
    home = Path.home()
    app_data = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    local_app_data = Path(os.environ.get("LOCALAPPDATA", home / "AppData" / "Local"))
    details = CLI_DETAILS.get(provider_type, CLI_DETAILS["codex"])
    executable = details["command"]
    candidates: list[Path] = []
    configured = config.get("command")
    if isinstance(configured, str) and configured.strip():
        candidates.append(Path(os.path.expandvars(configured)).expanduser())

    discovered = shutil.which(executable)
    if discovered:
        candidates.append(Path(discovered))

    candidates.extend(
        (
            home / ".local" / "bin" / executable,
            home / ".local" / "bin" / f"{executable}.exe",
            app_data / "npm" / f"{executable}.cmd",
            local_app_data / executable / "bin" / f"{executable}.exe",
        )
    )
    if provider_type == "claude":
        candidates.extend((app_data / "Claude" / "claude-code").glob("*/claude.exe"))
    if provider_type == "codex":
        candidates.extend((local_app_data / APP_NAME / "bin").glob("codex-app-server-*.exe"))
    return candidates


def detect_cli_path(provider_type: str, config: dict) -> str | None:
    for candidate in _candidate_paths(provider_type, config):
        try:
            if candidate.is_file():
                return str(candidate.resolve())
        except OSError:
            continue
    return None


def build_diagnostic_report(
    provider_config: dict,
    usage: ModelUsage | None,
) -> str:
    from subscription_usage import STATUS_BADGE_LABELS

    provider_type = str(provider_config.get("type", "codex"))
    details = CLI_DETAILS.get(provider_type, CLI_DETAILS["codex"])
    provider_name = str(provider_config.get("name", details["name"]))
    cli_path = detect_cli_path(provider_type, provider_config)
    if usage is None:
        status = "아직 조회 결과 없음"
        status_category = "미조회"
        action = details["login"]
    elif usage.error:
        status = usage.error
        status_category = STATUS_BADGE_LABELS.get(usage.status_kind, "조회 오류")
        action = usage.action_hint or details["login"]
    else:
        status = "최근 조회 성공"
        status_category = STATUS_BADGE_LABELS.get(usage.status_kind, "정상")
        action = details["login"]

    fetched = (
        usage.fetched_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        if usage is not None and usage.fetched_at is not None
        else "기록 없음"
    )
    last_success = (
        usage.last_success_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        if usage is not None and usage.last_success_at is not None
        else "기록 없음"
    )
    is_stale_str = "예" if (usage is not None and usage.is_stale) else "아니오"
    retry_after = (
        f"약 {usage.retry_after_sec}초"
        if usage is not None and usage.retry_after_sec is not None
        else "해당 없음"
    )
    runtime, execution_mode, python_version = _runtime_details()
    safe_status = sanitize_diagnostic_text(status)
    safe_action = sanitize_diagnostic_text(action)
    safe_cli_path = (
        sanitize_diagnostic_text(cli_path) if cli_path else "찾지 못함 또는 앱 연동 사용"
    )
    safe_executable = sanitize_diagnostic_text(sys.executable)
    log_directory = Path(CONFIG_FILE_PATH).resolve().parent / "logs"
    safe_log_directory = sanitize_diagnostic_text(log_directory)
    crash_log_status = "있음" if (log_directory / "crash.log").is_file() else "없음"

    return "\n".join(
        (
            f"{APP_NAME} v{APP_VERSION} 진단 정보",
            f"운영체제: {runtime}",
            f"실행 형태: {execution_mode}",
            f"실행 파일: {safe_executable}",
            f"Python 런타임: {python_version}",
            f"로컬 진단 로그: {safe_log_directory} (충돌 로그 {crash_log_status})",
            f"프로바이더: {provider_name} ({provider_type})",
            f"조회 상태: {safe_status}",
            f"상태 분류: {status_category}",
            f"마지막 조회: {fetched}",
            f"마지막 성공: {last_success}",
            f"오래된 값(stale) 유지: {is_stale_str}",
            f"다시 조회 가능까지: {retry_after}",
            f"CLI 경로: {safe_cli_path}",
            f"확인 명령: {details['command']} --version",
            f"해결 방법: {safe_action}",
            f"로그인 안내: {details['login']}",
            "",
            "이 보고서에는 계정 토큰이나 API 키가 포함되지 않습니다.",
        )
    )
