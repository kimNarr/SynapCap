from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import plistlib
import subprocess
from pathlib import Path

try:
    from scripts.manage_version import normalize_version
except ModuleNotFoundError:  # Direct execution: python scripts/verify_bundle.py
    from manage_version import normalize_version


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise ValueError(f"{label} 파일이 없습니다: {path}")
    if path.stat().st_size <= 0:
        raise ValueError(f"{label} 파일이 비어 있습니다: {path}")
    return path


def _bundle_files(bundle: Path, platform_name: str) -> tuple[Path, Path]:
    if platform_name == "windows":
        return (
            _required_file(bundle / "SynapCap.exe", "앱 실행"),
            _required_file(
                bundle / "_internal" / "SynapCapCopilotProbe.exe",
                "Copilot 프로브",
            ),
        )

    if platform_name != "macos":
        raise ValueError(f"지원하지 않는 플랫폼입니다: {platform_name}")
    app_path = _required_file(bundle / "Contents" / "MacOS" / "SynapCap", "앱 실행")
    # PyInstaller exposes the same helper through multiple bundle symlinks.
    helpers = sorted({
        path.resolve()
        for path in bundle.rglob("SynapCapCopilotProbe")
        if path.is_file() and path != app_path
    })
    if any(not path.is_relative_to(bundle) for path in helpers):
        raise ValueError("macOS Copilot 프로브가 번들 밖을 가리킵니다.")
    if len(helpers) != 1:
        raise ValueError(
            "macOS 번들에서 Copilot 프로브를 정확히 하나 찾지 못했습니다: "
            f"{len(helpers)}개"
        )
    return app_path, helpers[0]


def _windows_version_fields(app: Path) -> dict[str, str]:
    """Read the EXE's fixed version resource, not the source tree version."""
    if os.name != "nt":
        raise ValueError("Windows 실행 파일 버전 검증은 Windows에서 실행해야 합니다.")
    from ctypes import wintypes

    class FixedFileInfo(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint32) for name in (
            "signature", "structure_version", "file_ms", "file_ls",
            "product_ms", "product_ls", "flags_mask", "flags", "os",
            "type", "subtype", "date_ms", "date_ls",
        )]

    api = ctypes.WinDLL("version", use_last_error=True)
    api.GetFileVersionInfoSizeW.argtypes = [
        wintypes.LPCWSTR, ctypes.POINTER(wintypes.DWORD),
    ]
    api.GetFileVersionInfoSizeW.restype = wintypes.DWORD
    api.GetFileVersionInfoW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
    ]
    api.GetFileVersionInfoW.restype = wintypes.BOOL
    api.VerQueryValueW.argtypes = [
        ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(wintypes.UINT),
    ]
    api.VerQueryValueW.restype = wintypes.BOOL
    size = api.GetFileVersionInfoSizeW(str(app), None)
    if not size:
        raise ValueError("Windows 실행 파일 버전 리소스가 없거나 읽을 수 없습니다.")
    buffer = ctypes.create_string_buffer(size)
    if not api.GetFileVersionInfoW(str(app), 0, size, buffer):
        raise ValueError("Windows 실행 파일 버전 리소스 읽기 실패")
    pointer = ctypes.c_void_p()
    length = wintypes.UINT()
    if (
        not api.VerQueryValueW(buffer, "\\", ctypes.byref(pointer), ctypes.byref(length))
        or not pointer.value
        or length.value < ctypes.sizeof(FixedFileInfo)
    ):
        raise ValueError("Windows 실행 파일 버전 정보가 잘못되었습니다.")
    info = ctypes.cast(pointer, ctypes.POINTER(FixedFileInfo)).contents
    if info.signature != 0xFEEF04BD:
        raise ValueError("Windows 실행 파일 버전 서명이 잘못되었습니다.")

    def version(ms: int, ls: int) -> str:
        return ".".join(str(part) for part in (ms >> 16, ms & 0xFFFF, ls >> 16, ls & 0xFFFF))

    return {
        "FileVersion": version(info.file_ms, info.file_ls),
        "ProductVersion": version(info.product_ms, info.product_ls),
    }


def _bundle_versions(bundle: Path, app: Path, platform_name: str) -> dict[str, str]:
    if platform_name == "windows":
        return _windows_version_fields(app)
    plist_path = _required_file(bundle / "Contents" / "Info.plist", "앱 메타데이터")
    try:
        with plist_path.open("rb") as file:
            metadata = plistlib.load(file)
    except (ValueError, OSError) as exc:
        raise ValueError("macOS 앱 버전 메타데이터를 읽을 수 없습니다.") from exc
    if not isinstance(metadata, dict):
        raise ValueError("macOS 앱 메타데이터가 사전 형식이 아닙니다.")
    fields = ("CFBundleShortVersionString", "CFBundleVersion")
    if any(not isinstance(metadata.get(key), str) or not metadata[key].strip() for key in fields):
        raise ValueError("macOS 앱 버전 메타데이터가 누락되었거나 잘못되었습니다.")
    return {key: metadata[key] for key in fields}


def _verified_version(fields: dict[str, str], expected: str) -> str:
    for key, actual in fields.items():
        # Windows' fixed resource uses four numeric components; release
        # builds use a zero fourth component for the three-part app version.
        comparable = actual[:-2] if actual.count(".") == 3 and actual.endswith(".0") else actual
        if comparable != expected:
            raise ValueError(f"번들 버전 불일치: {key}={actual}, 기대 버전={expected}")
    if not fields:
        raise ValueError("번들 버전 메타데이터가 없습니다.")
    return expected


def _probe_self_check(helper: Path) -> dict:
    completed = subprocess.run(
        [str(helper), "--self-check"],
        capture_output=True,
        check=False,
        text=True,
        timeout=30,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise ValueError(f"Copilot 프로브 자체 검사 실패({completed.returncode}): {detail}")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("Copilot 프로브 자체 검사 응답이 비어 있습니다.")
    try:
        result = json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise ValueError("Copilot 프로브 자체 검사 응답이 JSON이 아닙니다.") from exc
    if result != {"status": "ready"}:
        raise ValueError(f"Copilot 프로브가 준비되지 않았습니다: {result!r}")
    return result


def verify_bundle(bundle: Path, platform_name: str, expected_version: str) -> dict:
    bundle = bundle.resolve()
    if not bundle.is_dir():
        raise ValueError(f"번들 폴더가 없습니다: {bundle}")
    version = normalize_version(expected_version)
    app_path, helper_path = _bundle_files(bundle, platform_name)
    version_fields = _bundle_versions(bundle, app_path, platform_name)
    version = _verified_version(version_fields, version)
    self_check = _probe_self_check(helper_path)

    def file_record(path: Path) -> dict:
        return {
            "path": path.relative_to(bundle).as_posix(),
            "size": path.stat().st_size,
            "sha256": _sha256(path),
        }

    return {
        "schema_version": 1,
        "app_version": version,
        "version_metadata": version_fields,
        "platform": platform_name,
        "bundle_kind": "onedir",
        "app": file_record(app_path),
        "copilot_probe": {
            **file_record(helper_path),
            "self_check": self_check["status"],
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SynapCap 배포 번들 자체 검사")
    parser.add_argument("bundle", type=Path)
    parser.add_argument("--platform", choices=("windows", "macos"), required=True)
    parser.add_argument("--expected-version", required=True)
    parser.add_argument("--report", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = verify_bundle(args.bundle, args.platform, args.expected_version)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
