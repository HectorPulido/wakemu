#!/bin/bash
set -euo pipefail
umask 077
experiment_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$experiment_dir"
world_state="$experiment_dir/.local-state/wakemu/world"
mkdir -p "$world_state" .runtime/local/logs
if [[ ! -f "$world_state/server.key" || ! -f "$world_state/server.crt" ]]; then
  openssl req -x509 -newkey rsa:2048 -nodes -keyout "$world_state/server.key" \
    -out "$world_state/server.crt" -days 365 -subj '/CN=localhost' 2>.runtime/local/logs/certificate.log
fi
openssl pkey -in "$world_state/server.key" -pubout -outform DER -out "$world_state/public-key.der"
exec /usr/bin/sandbox-exec -f "$experiment_dir/client-tools/runtime/local-network.sb" python3 server/local_game_server.py
