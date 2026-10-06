#!/bin/sh
set -eu
umask 077
mkdir -p "$WAKFU_RUNTIME/logs"
if [ ! -f "$WAKFU_RUNTIME/server.key" ] || [ ! -f "$WAKFU_RUNTIME/server.crt" ]; then
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$WAKFU_RUNTIME/server.key" -out "$WAKFU_RUNTIME/server.crt" \
    -days 365 -subj '/CN=localhost' 2>"$WAKFU_RUNTIME/logs/certificate.log"
fi
openssl pkey -in "$WAKFU_RUNTIME/server.key" -pubout -outform DER -out "$WAKFU_RUNTIME/public-key.der"
PYTHONPATH=/app python3 /app/tools/migrate_postgres.py
exec python3 /app/local_game_server.py
