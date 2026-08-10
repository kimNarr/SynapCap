#!/usr/bin/env bash
set -euo pipefail

VERSION="${1:-0.1.0}"
ARCH_NAME="${2:-$(uname -m)}"
OUTPUT_DIR="${3:-artifacts}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARTIFACT_DIR="$REPO_ROOT/$OUTPUT_DIR"
STAGING_DIR="$REPO_ROOT/build/dmg-$ARCH_NAME"

cd "$REPO_ROOT"
mkdir -p "$ARTIFACT_DIR"

python scripts/generate_icons.py
python -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --onedir \
  --name SynapCap \
  --icon assets/synapcap.icns \
  --osx-bundle-identifier io.github.kimNarr.SynapCap \
  main.py

rm -rf "$STAGING_DIR"
mkdir -p "$STAGING_DIR"
cp -R dist/SynapCap.app "$STAGING_DIR/SynapCap.app"
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

codesign --verify --deep --strict dist/SynapCap.app
echo "Created $DMG_PATH"

