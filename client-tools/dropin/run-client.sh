#!/bin/bash
set -euo pipefail
umask 077
mod_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
export WAKFU_LAUNCHER_CONFIG="${WAKFU_LAUNCHER_CONFIG:-$mod_dir/config.json}"
exec python3 "$mod_dir/run-client.py" "$@"
