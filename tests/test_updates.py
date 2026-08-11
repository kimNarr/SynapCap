import hashlib
import json
import tempfile
import unittest
from http.client import IncompleteRead
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from updates import (
    UpdateDownloadError,
    UpdateInfo,
    _platform_asset_name,
    check_for_update,
    download_and_verify_update,
    parse_version,
)


class FakeResponse:
    def __init__(self, content: bytes, headers=None):
        self._stream = BytesIO(content)
        self.headers = headers or {}

    def read(self, size=-1):
        return self._stream.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class UpdateTests(unittest.TestCase):
    def test_parse_version_accepts_release_tags(self):
        self.assertEqual(parse_version("v1.2.3"), (1, 2, 3))
        self.assertEqual(parse_version("1.2.3"), (1, 2, 3))
        self.assertIsNone(parse_version("latest"))

    @patch("updates.urlopen")
    def test_newer_release_is_returned(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {
                "tag_name": "v0.1.1",
                "html_url": "https://github.com/kimNarr/SynapCap/releases/tag/v0.1.1",
            }
        ).encode("utf-8")
        urlopen.return_value.__enter__.return_value = response

        self.assertEqual(
            check_for_update("0.1.0"),
            UpdateInfo(
                "0.1.1",
                "https://github.com/kimNarr/SynapCap/releases/tag/v0.1.1",
            ),
        )

    @patch("updates.urlopen")
    def test_current_release_does_not_notify(self, urlopen):
        response = MagicMock()
        response.read.return_value = json.dumps(
            {"tag_name": "v0.1.0", "html_url": "https://github.com/example"}
        ).encode("utf-8")
        urlopen.return_value.__enter__.return_value = response

        self.assertIsNone(check_for_update("0.1.0"))

    def test_platform_asset_names(self):
        self.assertEqual(
            _platform_asset_name("win32"),
            "SynapCap-Windows-x64-Setup.exe",
        )
        self.assertEqual(
            _platform_asset_name("darwin", "arm64"),
            "SynapCap-macOS-arm64.dmg",
        )
        self.assertEqual(
            _platform_asset_name("darwin", "x86_64"),
            "SynapCap-macOS-x64.dmg",
        )

    @patch("updates.sys.platform", "win32")
    @patch("updates.urlopen")
    def test_release_selects_matching_one_click_assets(self, urlopen):
        version = "0.2.0"
        asset_name = "SynapCap-Windows-x64-Setup.exe"
        asset_url = f"https://github.com/kimNarr/SynapCap/releases/download/v{version}/{asset_name}"
        checksum_url = (
            f"https://github.com/kimNarr/SynapCap/releases/download/v{version}/SHA256SUMS.txt"
        )
        response = FakeResponse(
            json.dumps(
                {
                    "tag_name": f"v{version}",
                    "html_url": (f"https://github.com/kimNarr/SynapCap/releases/tag/v{version}"),
                    "assets": [
                        {
                            "name": asset_name,
                            "browser_download_url": asset_url,
                            "digest": "sha256:" + "a" * 64,
                        },
                        {
                            "name": "SHA256SUMS.txt",
                            "browser_download_url": checksum_url,
                        },
                    ],
                }
            ).encode("utf-8")
        )
        urlopen.return_value = response

        info = check_for_update("0.1.4")

        self.assertIsNotNone(info)
        self.assertTrue(info.supports_one_click)
        self.assertEqual(info.asset_name, asset_name)
        self.assertEqual(info.asset_digest, "a" * 64)

    @patch("updates.sys.platform", "win32")
    @patch("updates.urlopen")
    def test_download_is_saved_only_after_sha256_verification(self, urlopen):
        content = b"verified installer"
        digest = hashlib.sha256(content).hexdigest()
        version = "0.2.0"
        asset_name = "SynapCap-Windows-x64-Setup.exe"
        base = f"https://github.com/kimNarr/SynapCap/releases/download/v{version}"
        info = UpdateInfo(
            version,
            f"https://github.com/kimNarr/SynapCap/releases/tag/v{version}",
            asset_name,
            f"{base}/{asset_name}",
            f"{base}/SHA256SUMS.txt",
            digest,
        )
        urlopen.side_effect = [
            FakeResponse(f"{digest}  {asset_name}\n".encode("utf-8")),
            FakeResponse(content, {"Content-Length": str(len(content))}),
        ]
        progress = []

        with tempfile.TemporaryDirectory() as directory:
            path = download_and_verify_update(
                info,
                progress_callback=progress.append,
                destination_root=Path(directory),
            )
            self.assertEqual(path.read_bytes(), content)
            self.assertFalse(path.with_suffix(".exe.part").exists())

        self.assertEqual(progress[-1], 100)

    @patch("updates.sys.platform", "win32")
    @patch("updates.urlopen")
    def test_checksum_mismatch_never_promotes_partial_download(self, urlopen):
        content = b"tampered installer"
        version = "0.2.0"
        asset_name = "SynapCap-Windows-x64-Setup.exe"
        base = f"https://github.com/kimNarr/SynapCap/releases/download/v{version}"
        expected = "a" * 64
        info = UpdateInfo(
            version,
            f"https://github.com/kimNarr/SynapCap/releases/tag/v{version}",
            asset_name,
            f"{base}/{asset_name}",
            f"{base}/SHA256SUMS.txt",
            expected,
        )
        urlopen.side_effect = [
            FakeResponse(f"{expected}  {asset_name}\n".encode("utf-8")),
            FakeResponse(content, {"Content-Length": str(len(content))}),
        ]

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(UpdateDownloadError):
                download_and_verify_update(
                    info,
                    destination_root=Path(directory),
                )
            self.assertEqual(list(Path(directory).rglob("*.exe")), [])

    @patch("updates.sys.platform", "win32")
    @patch("updates.urlopen")
    def test_interrupted_http_download_restores_update_ui_path(self, urlopen):
        version = "0.2.0"
        asset_name = "SynapCap-Windows-x64-Setup.exe"
        digest = hashlib.sha256(b"complete installer").hexdigest()
        base = f"https://github.com/kimNarr/SynapCap/releases/download/v{version}"
        info = UpdateInfo(
            version,
            f"https://github.com/kimNarr/SynapCap/releases/tag/v{version}",
            asset_name,
            f"{base}/{asset_name}",
            f"{base}/SHA256SUMS.txt",
            digest,
        )
        broken_response = FakeResponse(b"", {"Content-Length": "100"})
        broken_response.read = MagicMock(side_effect=IncompleteRead(b"partial", 93))
        urlopen.side_effect = [
            FakeResponse(f"{digest}  {asset_name}\n".encode("utf-8")),
            broken_response,
        ]

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(UpdateDownloadError):
                download_and_verify_update(
                    info,
                    destination_root=Path(directory),
                )
            self.assertEqual(list(Path(directory).rglob("*.part")), [])

    @patch("updates.sys.platform", "win32")
    @patch("updates.urlopen")
    def test_untrusted_asset_url_is_rejected_before_network(self, urlopen):
        info = UpdateInfo(
            "0.2.0",
            "https://github.com/kimNarr/SynapCap/releases/tag/v0.2.0",
            "SynapCap-Windows-x64-Setup.exe",
            "https://example.com/installer.exe",
            ("https://github.com/kimNarr/SynapCap/releases/download/v0.2.0/SHA256SUMS.txt"),
        )

        with self.assertRaises(UpdateDownloadError):
            download_and_verify_update(info)
        urlopen.assert_not_called()

    @patch("updates.sys.platform", "win32")
    @patch("updates.urlopen")
    def test_noncanonical_version_is_rejected_before_network(self, urlopen):
        info = UpdateInfo(
            "0.2.0+../escape",
            "https://github.com/kimNarr/SynapCap/releases/latest",
            "SynapCap-Windows-x64-Setup.exe",
            (
                "https://github.com/kimNarr/SynapCap/releases/download/"
                "v0.2.0+../escape/SynapCap-Windows-x64-Setup.exe"
            ),
            (
                "https://github.com/kimNarr/SynapCap/releases/download/"
                "v0.2.0+../escape/SHA256SUMS.txt"
            ),
        )

        with self.assertRaises(UpdateDownloadError):
            download_and_verify_update(info)
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
