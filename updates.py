from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import sys
import tempfile
from dataclasses import dataclass
from http.client import HTTPException
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Signal

from version import APP_NAME, APP_VERSION, REPOSITORY_URL

VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
LATEST_RELEASE_API = "https://api.github.com/repos/kimNarr/SynapCap/releases/latest"


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    url: str
    asset_name: str = ""
    asset_url: str = ""
    checksum_url: str = ""
    asset_digest: str = ""

    @property
    def supports_one_click(self) -> bool:
        return bool(self.asset_name and self.asset_url and self.checksum_url)


class UpdateDownloadError(RuntimeError):
    """A safe message for a failed or untrusted update download."""


def parse_version(value: str) -> Optional[tuple[int, int, int]]:
    match = VERSION_RE.fullmatch(str(value).strip())
    if match is None:
        return None
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch)


def _platform_asset_name(
    platform_name: str | None = None,
    machine: str | None = None,
) -> str:
    platform_name = platform_name or sys.platform
    if platform_name == "win32":
        return "SynapCap-Windows-x64-Setup.exe"
    if platform_name == "darwin":
        architecture = (machine or platform.machine()).lower()
        suffix = "arm64" if architecture in {"arm64", "aarch64"} else "x64"
        return f"SynapCap-macOS-{suffix}.dmg"
    return ""


def _trusted_release_download_url(url: str, version: str, filename: str) -> bool:
    parsed = urlparse(url)
    expected_path = f"/kimNarr/SynapCap/releases/download/v{version}/{filename}"
    return (
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and parsed.path == expected_path
        and not parsed.query
        and not parsed.fragment
    )


def _release_downloads(payload: dict, version: str) -> dict[str, str]:
    desired_name = _platform_asset_name()
    selected = {
        "asset_name": "",
        "asset_url": "",
        "checksum_url": "",
        "asset_digest": "",
    }
    assets = payload.get("assets")
    if not isinstance(assets, list):
        return selected

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if name not in {desired_name, "SHA256SUMS.txt"}:
            continue
        if not _trusted_release_download_url(url, version, name):
            continue
        if name == desired_name:
            selected["asset_name"] = name
            selected["asset_url"] = url
            digest = str(asset.get("digest", ""))
            if digest.startswith("sha256:"):
                selected["asset_digest"] = digest.removeprefix("sha256:").lower()
        else:
            selected["checksum_url"] = url
    return selected


def check_for_update(current_version: str = APP_VERSION) -> Optional[UpdateInfo]:
    current = parse_version(current_version)
    if current is None:
        return None

    request = Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{APP_NAME}/{current_version}",
        },
    )
    try:
        with urlopen(request, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeError, ValueError):
        return None

    latest_text = str(payload.get("tag_name", "")).removeprefix("v")
    latest = parse_version(latest_text)
    if latest is None or latest <= current:
        return None

    release_url = str(payload.get("html_url", ""))
    parsed_url = urlparse(release_url)
    if parsed_url.scheme != "https" or parsed_url.hostname != "github.com":
        release_url = f"{REPOSITORY_URL}/releases/latest"
    return UpdateInfo(
        version=latest_text,
        url=release_url,
        **_release_downloads(payload, latest_text),
    )


def _request(url: str) -> Request:
    return Request(
        url,
        headers={
            "Accept": "application/octet-stream",
            "User-Agent": f"{APP_NAME}/{APP_VERSION}",
        },
    )


def _read_checksum(url: str, max_bytes: int = 1024 * 1024) -> str:
    try:
        with urlopen(_request(url), timeout=10) as response:
            content = response.read(max_bytes + 1)
    except (OSError, HTTPException) as exc:
        raise UpdateDownloadError("체크섬을 다운로드하지 못했습니다.") from exc
    if len(content) > max_bytes:
        raise UpdateDownloadError("체크섬 파일이 허용 크기를 초과했습니다.")
    try:
        return content.decode("utf-8")
    except UnicodeError as exc:
        raise UpdateDownloadError("체크섬 파일 형식이 올바르지 않습니다.") from exc


def _expected_checksum(text: str, asset_name: str) -> str:
    for line in text.splitlines():
        fields = line.strip().split()
        if len(fields) < 2:
            continue
        digest = fields[0].lower()
        filename = fields[-1].lstrip("*")
        if filename == asset_name and re.fullmatch(r"[0-9a-f]{64}", digest):
            return digest
    raise UpdateDownloadError("설치 파일의 SHA-256 체크섬을 찾지 못했습니다.")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_and_verify_update(
    info: UpdateInfo,
    progress_callback=None,
    cancel_callback=None,
    destination_root: Path | None = None,
) -> Path:
    if not info.supports_one_click:
        raise UpdateDownloadError("이 운영체제의 설치 파일을 찾지 못했습니다.")
    if not re.fullmatch(r"\d+\.\d+\.\d+", info.version):
        raise UpdateDownloadError("업데이트 버전 형식이 올바르지 않습니다.")
    expected_asset_name = _platform_asset_name()
    if not expected_asset_name or info.asset_name != expected_asset_name:
        raise UpdateDownloadError("현재 운영체제용 설치 파일이 아닙니다.")
    if Path(info.asset_name).name != info.asset_name:
        raise UpdateDownloadError("설치 파일명이 올바르지 않습니다.")
    if not _trusted_release_download_url(
        info.asset_url, info.version, info.asset_name
    ) or not _trusted_release_download_url(info.checksum_url, info.version, "SHA256SUMS.txt"):
        raise UpdateDownloadError("신뢰할 수 없는 업데이트 주소입니다.")

    checksum_text = _read_checksum(info.checksum_url)
    expected = _expected_checksum(checksum_text, info.asset_name)
    if info.asset_digest and info.asset_digest != expected:
        raise UpdateDownloadError("Release 체크섬 정보가 서로 일치하지 않습니다.")

    root = destination_root or (Path(tempfile.gettempdir()) / "SynapCap" / "updates")
    destination = root / f"v{info.version}" / info.asset_name
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_file() and _sha256(destination) == expected:
            if progress_callback:
                progress_callback(100)
            return destination

        partial.unlink(missing_ok=True)
        request = _request(info.asset_url)
        with urlopen(request, timeout=15) as response, partial.open("wb") as stream:
            length_text = response.headers.get("Content-Length", "")
            total = int(length_text) if str(length_text).isdigit() else 0
            if total > 512 * 1024 * 1024:
                raise UpdateDownloadError("설치 파일이 허용 크기를 초과했습니다.")
            downloaded = 0
            while True:
                if cancel_callback and cancel_callback():
                    raise UpdateDownloadError("업데이트 다운로드가 취소되었습니다.")
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                downloaded += len(chunk)
                if downloaded > 512 * 1024 * 1024:
                    raise UpdateDownloadError("설치 파일이 허용 크기를 초과했습니다.")
                stream.write(chunk)
                if progress_callback and total:
                    progress_callback(min(99, round(downloaded * 100 / total)))

        if _sha256(partial) != expected:
            raise UpdateDownloadError("다운로드 파일의 SHA-256이 일치하지 않습니다.")
        os.replace(partial, destination)
    except UpdateDownloadError:
        partial.unlink(missing_ok=True)
        raise
    except (OSError, HTTPException) as exc:
        partial.unlink(missing_ok=True)
        raise UpdateDownloadError("업데이트 파일을 저장하지 못했습니다.") from exc

    if progress_callback:
        progress_callback(100)
    return destination


class UpdateCheckWorker(QThread):
    update_available = Signal(object)

    def __init__(self, current_version: str = APP_VERSION, parent=None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self):
        update = check_for_update(self.current_version)
        if update is not None and not self.isInterruptionRequested():
            self.update_available.emit(update)


class UpdateDownloadWorker(QThread):
    progress = Signal(int)
    ready = Signal(str)
    failed = Signal(str)

    def __init__(self, info: UpdateInfo, parent=None):
        super().__init__(parent)
        self.info = info

    def run(self):
        try:
            path = download_and_verify_update(
                self.info,
                progress_callback=self.progress.emit,
                cancel_callback=self.isInterruptionRequested,
            )
        except UpdateDownloadError as exc:
            if not self.isInterruptionRequested():
                self.failed.emit(str(exc))
            return
        if not self.isInterruptionRequested():
            self.ready.emit(str(path))
