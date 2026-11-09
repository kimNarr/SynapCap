import tempfile
import unittest
from datetime import date
from pathlib import Path

from scripts.manage_version import (
    next_version,
    read_version,
    release_notes,
    unreleased_plan,
    write_version,
)


class VersionManagementTests(unittest.TestCase):
    def test_next_version(self):
        self.assertEqual(next_version("0.1.0", "patch"), "0.1.1")
        self.assertEqual(next_version("0.1.9", "minor"), "0.2.0")
        self.assertEqual(next_version("1.9.9", "major"), "2.0.0")

    def test_write_version_promotes_unreleased_notes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            version_file = root / "version.py"
            changelog_file = root / "CHANGELOG.md"
            version_file.write_text('APP_VERSION = "0.1.0"\n', encoding="utf-8")
            changelog_file.write_text(
                "# Changelog\n\n"
                "## [Unreleased]\n\n"
                "대상 버전: `0.1.1`\n"
                "연결 태스크: SC-001\n\n"
                "### Fixed\n\n"
                "- 오류 수정\n",
                encoding="utf-8",
            )

            write_version(
                "0.1.1",
                version_file,
                changelog_file,
                date(2026, 8, 10),
            )

            self.assertEqual(read_version(version_file), "0.1.1")
            self.assertIn("## [0.1.1] - 2026-08-10", changelog_file.read_text(encoding="utf-8"))
            self.assertIn("오류 수정", release_notes("0.1.1", changelog_file))

    def test_unreleased_plan_reads_target_version_and_unique_task_ids(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            changelog_file = Path(temp_dir) / "CHANGELOG.md"
            changelog_file.write_text(
                "## [Unreleased]\n\n"
                "대상 버전: `0.3.1`\n"
                "연결 태스크: SC-002, SC-005, SC-010\n\n"
                "### 수정\n\n- 수정 내용\n\n"
                "## [0.3.0] - 2026-09-04\n",
                encoding="utf-8",
            )

            self.assertEqual(
                unreleased_plan(changelog_file),
                ("0.3.1", ("SC-002", "SC-005", "SC-010")),
            )

    def test_write_version_rejects_a_version_that_differs_from_release_plan(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            version_file = root / "version.py"
            changelog_file = root / "CHANGELOG.md"
            version_file.write_text('APP_VERSION = "0.3.0"\n', encoding="utf-8")
            changelog_file.write_text(
                "## [Unreleased]\n\n"
                "대상 버전: `0.3.1`\n"
                "연결 태스크: SC-007\n\n"
                "### 수정\n\n- 수정 내용\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "대상 버전"):
                write_version("0.4.0", version_file, changelog_file)


if __name__ == "__main__":
    unittest.main()
