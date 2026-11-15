#!/bin/bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
target_dir="${1:?Usage: build-keychain.sh TARGET_DIRECTORY}"
mkdir -p "$target_dir"
for arch in arm64 x86_64; do
  xcrun swiftc -swift-version 5 -O -target "$arch-apple-macosx13.0" \
    -framework Security "$source_dir/KeychainHelper.swift" \
    -o "$target_dir/keychain-helper-$arch"
done
xcrun lipo -create "$target_dir/keychain-helper-arm64" "$target_dir/keychain-helper-x86_64" \
  -output "$target_dir/keychain-helper"
rm "$target_dir/keychain-helper-arm64" "$target_dir/keychain-helper-x86_64"
codesign --force --sign - "$target_dir/keychain-helper"
