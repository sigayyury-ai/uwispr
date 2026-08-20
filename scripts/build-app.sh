#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

APP_NAME="Flow"
DIST="$ROOT/dist"
APP="$DIST/${APP_NAME}.app"
CONTENTS="$APP/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
SRC_ICON="$ROOT/assets/micTemplate@2x.png"

rm -rf "$APP"
mkdir -p "$MACOS" "$RESOURCES"

if [[ ! -f "$SRC_ICON" ]]; then
  echo "Missing icon: $SRC_ICON"
  exit 1
fi

ICONSET="$(mktemp -d)/AppIcon.iconset"
mkdir -p "$ICONSET"

add_icon() {
  local px="$1"
  local name="$2"
  sips -z "$px" "$px" "$SRC_ICON" --out "$ICONSET/$name" >/dev/null
}

add_icon 16 icon_16x16.png
add_icon 32 icon_16x16@2x.png
add_icon 32 icon_32x32.png
add_icon 64 icon_32x32@2x.png
add_icon 128 icon_128x128.png
add_icon 256 icon_128x128@2x.png
add_icon 256 icon_256x256.png
add_icon 512 icon_256x256@2x.png
add_icon 512 icon_512x512.png
add_icon 1024 icon_512x512@2x.png

iconutil -c icns "$ICONSET" -o "$RESOURCES/AppIcon.icns"
rm -rf "$(dirname "$ICONSET")"

cat >"$CONTENTS/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleExecutable</key>
  <string>flow</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon</string>
  <key>CFBundleIdentifier</key>
  <string>com.flow.dictation</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>Flow</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>LSUIElement</key>
  <true/>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

cat >"$MACOS/flow" <<LAUNCHER
#!/usr/bin/env bash
set -euo pipefail
ROOT='$ROOT'
cd "\$ROOT"
"\$ROOT/scripts/stop.sh" || true
exec "\$ROOT/.venv/bin/python" -m flow
LAUNCHER

chmod +x "$MACOS/flow"

DESKTOP="$HOME/Desktop/${APP_NAME}.app"
ditto "$APP" "$DESKTOP"

echo "Built: $APP"
echo "Copied to: $DESKTOP"
echo "Project root embedded in launcher: $ROOT"
