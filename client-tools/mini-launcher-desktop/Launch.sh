#!/bin/sh
set -eu
launcher_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
export WAKFU_LAUNCHER_ROOT="$launcher_dir"
exec python3 "$launcher_dir/mini-launcher/launcher_entry.py" "$@"
