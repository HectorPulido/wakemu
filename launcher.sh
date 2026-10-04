#!/bin/bash
set -euo pipefail
launcher_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$launcher_dir"
exec python3 "$launcher_dir/client/tools/local-launcher.py"
