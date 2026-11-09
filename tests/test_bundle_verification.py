import json
import os
import plistlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.verify_bundle import _windows_version_fields, verify_bundle


class BundleVerificationTests(unittest.TestCase):
    def test_windows_bundle_records_relative_paths_hashes_and_probe_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = Path(temp_dir)
            app = bundle / "SynapCap.exe"
            helper = bundle / "_internal" / "SynapCapCopilotProbe.exe"
            helper.parent.mkdir()
            app.write_bytes(b"app-binary")
            helper.write_bytes(b"probe-binary")

            completed = Mock(returncode=0, stdout='{"status": "ready"}\n', stderr="")
            with (
                patch("scripts.verify_bundle.subprocess.run", return_value=completed) as run,
                patch("scripts.verify_bundle._windows_version_fields", return_value={
                    "FileVersion": "0.3.1.0", "ProductVersion": "0.3.1.0",
                }),
            ):
                report = verify_bundle(bundle, "windows", "0.3.1")

            run.assert_called_once_with(
                [str(helper.resolve()), "--self-check"],
                capture_output=True,
                check=False,
                text=True,
                timeout=30,
            )
            self.assertEqual(report["app_version"], "0.3.1")
            self.assertEqual(report["version_metadata"]["ProductVersion"], "0.3.1.0")
            self.assertEqual(report["app"]["path"], "SynapCap.exe")
            self.assertEqual(
                report["copilot_probe"]["path"],
                "_internal/SynapCapCopilotProbe.exe",
            )
            self.assertEqual(report["copilot_probe"]["self_check"], "ready")
            self.assertEqual(len(report["app"]["sha256"]), 64)

    def test_macos_bundle_finds_the_packaged_probe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = Path(temp_dir) / "SynapCap.app"
            app = bundle / "Contents" / "MacOS" / "SynapCap"
            helper = bundle / "Contents" / "Frameworks" / "SynapCapCopilotProbe"
            app.parent.mkdir(parents=True)
            helper.parent.mkdir(parents=True)
            app.write_bytes(b"app")
            helper.write_bytes(b"probe")
            (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps({
                "CFBundleShortVersionString": "0.3.1", "CFBundleVersion": "0.3.1",
            }))

            completed = Mock(returncode=0, stdout='{"status": "ready"}\n', stderr="")
            with patch("scripts.verify_bundle.subprocess.run", return_value=completed):
                report = verify_bundle(bundle, "macos", "0.3.1")

            self.assertEqual(report["platform"], "macos")
            self.assertEqual(
                report["copilot_probe"]["path"],
                "Contents/Frameworks/SynapCapCopilotProbe",
            )

    def test_bundle_verification_rejects_unready_probe(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            bundle = Path(temp_dir)
            app = bundle / "SynapCap.exe"
            helper = bundle / "_internal" / "SynapCapCopilotProbe.exe"
            helper.parent.mkdir()
            app.write_bytes(b"app")
            helper.write_bytes(b"probe")

            completed = Mock(
                returncode=0,
                stdout=json.dumps({"status": "error", "detail": "missing SDK"}),
                stderr="",
            )
            with (
                patch("scripts.verify_bundle.subprocess.run", return_value=completed),
                patch("scripts.verify_bundle._windows_version_fields", return_value={
                    "FileVersion": "0.3.1.0", "ProductVersion": "0.3.1.0",
                }),
                self.assertRaisesRegex(ValueError, "준비되지 않았습니다"),
            ):
                verify_bundle(bundle, "windows", "0.3.1")

    def test_windows_rejects_wrong_product_or_file_version_before_running_helper(self):
        for fields in (
            {"FileVersion": "0.3.0.0", "ProductVersion": "0.3.0.0"},
            {"FileVersion": "0.3.1.0", "ProductVersion": "0.3.0.0"},
            {"FileVersion": "0.3.0.0", "ProductVersion": "0.3.1.0"},
            {"FileVersion": "0.3.1.1", "ProductVersion": "0.3.1.0"},
            {},
        ):
            with self.subTest(fields=fields), tempfile.TemporaryDirectory() as temp_dir:
                bundle = Path(temp_dir)
                (bundle / "SynapCap.exe").write_bytes(b"app")
                helper = bundle / "_internal" / "SynapCapCopilotProbe.exe"
                helper.parent.mkdir()
                helper.write_bytes(b"helper")
                with (
                    patch("scripts.verify_bundle._windows_version_fields", return_value=fields),
                    patch("scripts.verify_bundle._probe_self_check") as probe,
                    self.assertRaisesRegex(ValueError, "버전"),
                ):
                    verify_bundle(bundle, "windows", "0.3.1")
                probe.assert_not_called()

    @unittest.skipUnless(os.name == "nt", "Windows version resource API")
    def test_windows_rejects_an_executable_without_version_resource(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            app = Path(temp_dir) / "SynapCap.exe"
            app.write_bytes(b"not-a-PE-file")
            with self.assertRaisesRegex(ValueError, "버전 리소스"):
                _windows_version_fields(app)

    def test_macos_rejects_mismatched_missing_or_invalid_metadata(self):
        for metadata in (
            {"CFBundleShortVersionString": "0.3.0", "CFBundleVersion": "0.3.1"},
            {"CFBundleShortVersionString": "0.3.1", "CFBundleVersion": "0.3.0"},
            {"CFBundleShortVersionString": "0.3.1"},
            {"CFBundleShortVersionString": 3, "CFBundleVersion": "0.3.1"},
            {},
            [],
            None,
        ):
            with self.subTest(metadata=metadata), tempfile.TemporaryDirectory() as temp_dir:
                bundle = Path(temp_dir) / "SynapCap.app"
                app = bundle / "Contents" / "MacOS" / "SynapCap"
                app.parent.mkdir(parents=True)
                app.write_bytes(b"app")
                (app.parent / "SynapCapCopilotProbe").write_bytes(b"probe")
                if metadata is not None:
                    (bundle / "Contents" / "Info.plist").write_bytes(plistlib.dumps(metadata))
                with (
                    patch("scripts.verify_bundle._probe_self_check") as probe,
                    self.assertRaisesRegex(ValueError, "버전|메타데이터"),
                ):
                    verify_bundle(bundle, "macos", "0.3.1")
                probe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
