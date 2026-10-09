#!/bin/bash
set -euo pipefail
umask 077
mod_dir="$(cd -- "$(dirname -- "$0")" && pwd)"
export WAKFU_LAUNCHER_CONFIG="$mod_dir/config.json"
cd "$mod_dir"
python3 -c 'from portable_config import settings; settings()'
python3 -c 'import tkinter' || { echo 'Necesitas Python 3 con Tkinter para abrir este launcher.' >&2; exit 1; }
exec python3 "$mod_dir/local-launcher.py"
