#!/bin/sh
# PostgreSQL runs this only while initializing an empty data directory.
set -eu
archive=/bootstrap/wakemu-runtime.dump
if [ ! -s "$archive" ]; then
    echo 'Database snapshot missing. Fetch Git LFS files before starting PostgreSQL.' >&2
    exit 1
fi
if ! pg_restore --list "$archive" >/dev/null; then
    echo 'Invalid database snapshot. Run git lfs pull and verify its checksum.' >&2
    exit 1
fi
pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --no-owner --no-acl --exit-on-error "$archive"
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set ON_ERROR_STOP=1 --command \
    'SELECT revision FROM public.native_catalog_active WHERE id = 1;'
echo 'Wakemu database snapshot restored; subsequent starts use the persistent volume.'
