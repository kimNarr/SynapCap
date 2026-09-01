#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-0.1.0}"
ARCH_NAME="${2:-$(uname -m)}"
OUTPUT_DIR="${3:-artifacts}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARTIFACT_DIR="$REPO_ROOT/$OUTPUT_DIR"
STAGING_DIR="$REPO_ROOT/build/dmg-$ARCH_NAME"
APP_BUNDLE="$REPO_ROOT/dist/SynapCap.app"

cd "$REPO_ROOT"
mkdir -p "$ARTIFACT_DIR"

APP_VERSION="$(python scripts/manage_version.py current)"
if [[ "$VERSION" != "$APP_VERSION" ]]; then
  echo "Build version '$VERSION' does not match APP_VERSION '$APP_VERSION'." >&2
  exit 1
fi

python scripts/generate_icons.py
python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name SynapCap \
  --icon assets/synapcap.icns \
  --add-data "assets/synapcap-logo-source.png:assets" \
  --add-data "assets/synapcap-wordmark.png:assets" \
  --osx-bundle-identifier io.github.kimNarr.SynapCap \
  main.py

# SynapCap is a menu-bar utility. Keep it out of the Dock and app switcher;
# the status item remains available through QSystemTrayIcon.
if ! /usr/libexec/PlistBuddy \
  -c "Set :LSUIElement true" \
  "$APP_BUNDLE/Contents/Info.plist"; then
  /usr/libexec/PlistBuddy \
    -c "Add :LSUIElement bool true" \
    "$APP_BUNDLE/Contents/Info.plist"
fi

# PyInstaller ad-hoc signs the bundle during creation. Changing Info.plist
# invalidates that signature, so sign and validate the final bundle before it
# is copied into the disk image.
plutil -lint "$APP_BUNDLE/Contents/Info.plist"
codesign --force --deep --sign - "$APP_BUNDLE"
codesign --verify --deep --strict --verbose=2 "$APP_BUNDLE"

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -R "$APP_BUNDLE" "$STAGING_DIR/SynapCap.app"
ln -s /Applications "$STAGING_DIR/Applications"
cp LICENSE "$STAGING_DIR/LICENSE.txt"

DMG_PATH="$ARTIFACT_DIR/SynapCap-macOS-$ARCH_NAME.dmg"
rm -f "$DMG_PATH"
hdiutil create \
  -volname "SynapCap $VERSION" \
  -srcfolder "$STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Created $DMG_PATH"
