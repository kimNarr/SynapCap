from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "version.py"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSION_LINE_RE = re.compile(r'^APP_VERSION = "(\d+\.\d+\.\d+)"$', re.MULTILINE)


def normalize_version(value: str) -> str:
    normalized = value.strip().removeprefix("v")
    if SEMVER_RE.fullmatch(normalized) is None:
        raise ValueError(f"유효한 버전이 아닙니다: {value}")
    return normalized


def read_version(path: Path = VERSION_FILE) -> str:
    match = VERSION_LINE_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        raise ValueError(f"APP_VERSION을 찾을 수 없습니다: {path}")
    return match.group(1)


def next_version(current: str, change: str) -> str:
    major, minor, patch = (int(part) for part in normalize_version(current).split("."))
    if change == "major":
        return f"{major + 1}.0.0"
    if change == "minor":
        return f"{major}.{minor + 1}.0"
    if change == "patch":
        return f"{major}.{minor}.{patch + 1}"
    return normalize_version(change)


def write_version(
    new_version: str,
    version_path: Path = VERSION_FILE,
    changelog_path: Path = CHANGELOG_FILE,
    release_date: date | None = None,
) -> None:
    normalized = normalize_version(new_version)
    current = read_version(version_path)
    if normalized == current:
        raise ValueError(f"이미 현재 버전입니다: {normalized}")

    version_text = version_path.read_text(encoding="utf-8")
    version_text = VERSION_LINE_RE.sub(
        f'APP_VERSION = "{normalized}"', version_text, count=1
    )

    changelog = changelog_path.read_text(encoding="utf-8")
    heading = f"## [{normalized}]"
    if heading in changelog:
        raise ValueError(f"CHANGELOG에 이미 버전이 있습니다: {normalized}")
    marker = "## [Unreleased]"
    if marker not in changelog:
        raise ValueError("CHANGELOG에서 [Unreleased] 섹션을 찾을 수 없습니다.")
    released_on = release_date or date.today()
    changelog = changelog.replace(
        marker,
        f"{marker}\n\n{heading} - {released_on.isoformat()}",
        1,
    )

    version_path.write_text(version_text, encoding="utf-8")
    changelog_path.write_text(changelog, encoding="utf-8")


def release_notes(version: str, changelog_path: Path = CHANGELOG_FILE) -> str:
    normalized = normalize_version(version)
    changelog = changelog_path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"^## \[{re.escape(normalized)}\](?: - .*?)?\n(.*?)(?=^## \[|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(changelog)
    if match is None or not match.group(1).strip():
        return f"SynapCap {normalized} 릴리스"
    return match.group(1).strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SynapCap 버전 및 패치 관리")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("current", help="현재 앱 버전 출력")

    check = subparsers.add_parser("check", help="태그와 앱 버전 일치 확인")
    check.add_argument("tag")

    bump = subparsers.add_parser("bump", help="버전과 CHANGELOG 릴리스 섹션 갱신")
    bump.add_argument("change", help="patch, minor, major 또는 1.2.3")
    bump.add_argument("--dry-run", action="store_true")

    notes = subparsers.add_parser("notes", help="CHANGELOG 릴리스 노트 출력")
    notes.add_argument("version")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    current = read_version()
    if args.command == "current":
        print(current)
        return 0
    if args.command == "check":
        tag_version = normalize_version(args.tag)
        if tag_version != current:
            raise SystemExit(
                f"태그 버전({tag_version})과 APP_VERSION({current})이 다릅니다."
            )
        print(f"버전 확인 완료: {current}")
        return 0
    if args.command == "bump":
        target = next_version(current, args.change)
        if args.dry_run:
            print(target)
            return 0
        write_version(target)
        print(f"버전 갱신: {current} -> {target}")
        print(f"다음 단계: 변경 내용을 커밋한 뒤 v{target} 태그를 푸시하세요.")
        return 0
    if args.command == "notes":
        print(release_notes(args.version))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
