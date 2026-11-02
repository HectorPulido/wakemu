#!/bin/bash
set -euo pipefail
source_dir="$(cd "$(dirname "$0")" && pwd)"
package_dir="${1:?Usage: build-macos.sh PACKAGE_DIRECTORY}"
mkdir -p "$package_dir"
package_dir="$(cd "$package_dir" && pwd)"
swift_args=(-O)
if [[ "${WAKFU_LAUNCHER_QA:-0}" == "1" ]]; then swift_args=(-O -D LAUNCHER_QA); fi
app_dir="$package_dir/Wakfu Minilauncher.app"
mkdir -p "$app_dir/Contents/MacOS" "$app_dir/Contents/Resources"
# Build both supported Mac architectures from one source; WebKit ships with macOS.
for arch in arm64 x86_64; do
    xcrun swiftc -swift-version 5 "${swift_args[@]}" -target "$arch-apple-macosx12.0" \
        -framework AppKit -framework WebKit \
        "$source_dir/Launcher.swift" -o "$app_dir/Contents/MacOS/Launcher-$arch"
    mkdir -p "$package_dir/mini-launcher"
    xcrun swiftc -swift-version 5 -O -target "$arch-apple-macosx12.0" \
        -framework Security "$source_dir/KeychainHelper.swift" \
        -o "$package_dir/mini-launcher/keychain-helper-$arch"
done
xcrun lipo -create "$app_dir/Contents/MacOS/Launcher-arm64" "$app_dir/Contents/MacOS/Launcher-x86_64" -output "$app_dir/Contents/MacOS/Launcher"
rm "$app_dir/Contents/MacOS/Launcher-arm64" "$app_dir/Contents/MacOS/Launcher-x86_64"
xcrun lipo -create "$package_dir/mini-launcher/keychain-helper-arm64" "$package_dir/mini-launcher/keychain-helper-x86_64" -output "$package_dir/mini-launcher/keychain-helper"
rm "$package_dir/mini-launcher/keychain-helper-arm64" "$package_dir/mini-launcher/keychain-helper-x86_64"
codesign --force --sign - "$package_dir/mini-launcher/keychain-helper"
cat > "$app_dir/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>Wakfu Minilauncher</string>
<key>CFBundleDisplayName</key><string>Wakfu Minilauncher</string>
<key>CFBundleIdentifier</key><string>net.hectorpulido.wakfu.minilauncher</string>
<key>CFBundleExecutable</key><string>Launcher</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>2.0</string>
<key>CFBundleVersion</key><string>2</string>
<key>LSMinimumSystemVersion</key><string>12.0</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSRequiresAquaSystemAppearance</key><true/>
<key>NSAppTransportSecurity</key><dict><key>NSAllowsArbitraryLoadsInWebContent</key><true/></dict>
</dict></plist>
PLIST
codesign --force --sign - "$app_dir"
printf '%s\n' "$app_dir"
