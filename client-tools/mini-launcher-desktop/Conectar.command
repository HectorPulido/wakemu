#!/bin/bash
set -euo pipefail
package_dir="$(cd "$(dirname "$0")" && pwd)"
export WAKFU_LAUNCHER_ROOT="$package_dir"
exec "$package_dir/Wakfu Minilauncher.app/Contents/MacOS/Launcher" "$@"
