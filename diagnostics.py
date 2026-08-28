from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

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
}


def _candidate_paths(provider_type: str, config: dict) -> list[Path]:
    home = Path.home()
    app_data = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
    local_app_data = Path(
        os.environ.get("LOCALAPPDATA", home / "AppData" / "Local")
    )
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
        candidates.extend(
            (app_data / "Claude" / "claude-code").glob("*/claude.exe")
        )
    if provider_type == "codex":
        candidates.extend(
            (local_app_data / APP_NAME / "bin").glob("codex-app-server-*.exe")
        )
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
    provider_type = str(provider_config.get("type", "codex"))
    details = CLI_DETAILS.get(provider_type, CLI_DETAILS["codex"])
    provider_name = str(provider_config.get("name", details["name"]))
    cli_path = detect_cli_path(provider_type, provider_config)
    if usage is None:
        status = "아직 조회 결과 없음"
    elif usage.error:
        status = usage.error
    else:
        status = "최근 조회 성공"

    fetched = (
        usage.fetched_at.astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
        if usage is not None and usage.fetched_at is not None
        else "기록 없음"
    )
    return "\n".join(
        (
            f"{APP_NAME} v{APP_VERSION} 진단 정보",
            f"운영체제: {sys.platform}",
            f"프로바이더: {provider_name} ({provider_type})",
            f"조회 상태: {status}",
            f"마지막 조회: {fetched}",
            f"CLI 경로: {cli_path or '찾지 못함 또는 앱 연동 사용'}",
            f"확인 명령: {details['command']} --version",
            f"로그인 안내: {details['login']}",
            "",
            "이 보고서에는 계정 토큰이나 API 키가 포함되지 않습니다.",
        )
    )
