import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ReleaseScriptTests(unittest.TestCase):
    def test_logo_source_is_packaged_for_both_desktop_builds(self):
        windows_script = (ROOT / "scripts" / "build_windows.ps1").read_text(
            encoding="utf-8"
        )
        macos_script = (ROOT / "scripts" / "build_macos.sh").read_text(encoding="utf-8")

        self.assertTrue((ROOT / "assets" / "synapcap-logo-source.png").is_file())
        self.assertIn(
            '--add-data "assets\\synapcap-logo-source.png;assets"', windows_script
        )
        self.assertIn(
            '--add-data "assets/synapcap-logo-source.png:assets"', macos_script
        )

    def test_windows_shortcuts_use_a_versioned_icon_path(self):
        script = (ROOT / "packaging" / "windows" / "SynapCap.iss").read_text(
            encoding="utf-8"
        )

        versioned_icon = r"SynapCap-v{#MyAppVersion}.ico"
        self.assertIn('ChangesAssociations=yes', script)
        self.assertIn(f'DestName: "{versioned_icon}"', script)
        self.assertIn(r'Name: "{app}\SynapCap-v*.ico"', script)
        self.assertEqual(script.count(f'IconFilename: "{{app}}\\{versioned_icon}"'), 3)

    def test_macos_bundle_is_resigned_before_disk_image_creation(self):
        script = (ROOT / "scripts" / "build_macos.sh").read_text(encoding="utf-8")

        plist_update = script.index('if ! /usr/libexec/PlistBuddy')
        plist_validation = script.index('plutil -lint "$APP_BUNDLE/Contents/Info.plist"')
        bundle_signing = script.index('codesign --force --deep --sign - "$APP_BUNDLE"')
        signature_validation = script.index(
            'codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"'
        )
        bundle_staging = script.index('cp -R "$APP_BUNDLE" "$STAGING_DIR/SynapCap.app"')
        disk_image_creation = script.index("hdiutil create")

        self.assertLess(plist_update, plist_validation)
        self.assertLess(plist_validation, bundle_signing)
        self.assertLess(bundle_signing, signature_validation)
        self.assertLess(signature_validation, bundle_staging)
        self.assertLess(bundle_staging, disk_image_creation)


if __name__ == "__main__":
    unittest.main()
