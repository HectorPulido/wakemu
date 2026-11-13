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
# Runtime-only changes can reuse the same immutable content with a new header.
# If the fast path cannot establish compatibility, normal compilation remains
# authoritative and startup continues through the existing path.
case "${WAKFU_COMPILED_CATALOG_REUSE_EXISTING:-0}" in
  1)
    # Explicit opt-in: select compatible existing data, never regenerate it.
    WAKFU_COMPILED_CATALOG_GENERATION=$(PYTHONPATH=/app python3 /app/tools/select_existing_compiled_catalog.py)
    ;;
  0)
    if ! PYTHONPATH=/app python3 /app/tools/reuse_unchanged_compiled_catalog.py; then
      echo 'Compiled catalog reuse unavailable; using normal publication' >&2
    fi
    WAKFU_COMPILED_CATALOG_GENERATION=$(PYTHONPATH=/app python3 /app/tools/publish_compiled_combat_catalog.py --ensure --print-generation --warm-redis)
    ;;
  *) echo 'WAKFU_COMPILED_CATALOG_REUSE_EXISTING must be 0 or 1' >&2; exit 1 ;;
esac
export WAKFU_COMPILED_CATALOG_GENERATION
if [ "${WAKFU_COMPILED_CATALOG_REUSE_EXISTING:-0}" = 0 ] && ! PYTHONPATH=/app python3 /app/tools/reuse_unchanged_compiled_catalog.py --record "$WAKFU_COMPILED_CATALOG_GENERATION"; then
  echo 'Compiled runtime projections unavailable; future starts use normal publication' >&2
fi
PYTHONPATH=/app python3 /app/tools/compact_compiled_catalog.py --keep "$WAKFU_COMPILED_CATALOG_GENERATION"
# Payload maintenance must not delay player access. Its transactional table
# replacement supports active readers after the new World has acquired pins.
PYTHONPATH=/app python3 /app/tools/maintain_native_catalog_after_startup.py &
exec python3 -m wakfu_server.catalog_gc_bootstrap
