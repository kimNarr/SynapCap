from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from PySide6.QtCore import QThread, Signal

from version import APP_NAME, APP_VERSION, REPOSITORY_URL


VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:[-+].*)?$")
LATEST_RELEASE_API = (
    "https://api.github.com/repos/kimNarr/SynapCap/releases/latest"
)


@dataclass(frozen=True)
class UpdateInfo:
    version: str
    url: str


def parse_version(value: str) -> Optional[tuple[int, int, int]]:
    match = VERSION_RE.fullmatch(str(value).strip())
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


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
    return UpdateInfo(version=latest_text, url=release_url)


class UpdateCheckWorker(QThread):
    update_available = Signal(object)

    def __init__(self, current_version: str = APP_VERSION, parent=None):
        super().__init__(parent)
        self.current_version = current_version

    def run(self):
        update = check_for_update(self.current_version)
        if update is not None and not self.isInterruptionRequested():
            self.update_available.emit(update)
