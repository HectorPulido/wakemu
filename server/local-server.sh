#!/bin/bash
set -euo pipefail
umask 077
experiment_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$experiment_dir"
mkdir -p .runtime/local/logs
if [[ ! -f .runtime/local/server.key || ! -f .runtime/local/server.crt ]]; then
  openssl req -x509 -newkey rsa:2048 -nodes -keyout .runtime/local/server.key \
    -out .runtime/local/server.crt -days 365 -subj '/CN=localhost' 2>.runtime/local/logs/certificate.log
fi
openssl pkey -in .runtime/local/server.key -pubout -outform DER -out .runtime/local/public-key.der
exec /usr/bin/sandbox-exec -f "$experiment_dir/client/tools/local-network.sb" python3 server/local_game_server.py
