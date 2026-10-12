#!/bin/sh
# PostgreSQL runs this only while initializing an empty data directory.
set -eu
archive=/bootstrap/wakemu-runtime-20261012.dump
checksum=/bootstrap/wakemu-runtime-20261012.dump.parts.sha256
if [ ! -s "$checksum" ] || [ ! -s "$archive.sha256" ]; then
    echo 'Database snapshot missing. Fetch Git LFS files before starting PostgreSQL.' >&2
    exit 1
fi
(cd /bootstrap && sha256sum -c "$(basename "$checksum")")
temporary_dir=$(mktemp -d /tmp/wakemu-runtime.XXXXXX)
trap 'rm -rf "$temporary_dir"' EXIT HUP INT TERM
archive=$temporary_dir/wakemu-runtime-20261012.dump
cat /bootstrap/wakemu-runtime-20261012.dump.part-* > "$archive"
(cd "$temporary_dir" && sha256sum -c /bootstrap/wakemu-runtime-20261012.dump.sha256)
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
