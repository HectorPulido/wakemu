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
PYTHONPATH=/app python3 -c 'from wakfu_server.native_catalog import release; print("Native catalog release:", release())'
# Compile in a separate process so its temporary source graph is reclaimed
# before World opens sockets. Existing complete publications are reused.
WAKFU_COMPILED_CATALOG_GENERATION=$(PYTHONPATH=/app python3 /app/tools/publish_compiled_combat_catalog.py --ensure --print-generation --warm-redis)
export WAKFU_COMPILED_CATALOG_GENERATION
exec python3 -m wakfu_server.catalog_gc_bootstrap
