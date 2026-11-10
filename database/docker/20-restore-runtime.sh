#!/bin/sh
# PostgreSQL runs this only while initializing an empty data directory.
set -eu
bootstrap_dir=${WAKEMU_BOOTSTRAP_DIR:-/bootstrap}
archive=$bootstrap_dir/wakemu-clean.dump
checksum=$archive.sha256
manifest=$archive.manifest.json
if [ ! -s "$archive" ] || [ ! -s "$checksum" ] || [ ! -s "$manifest" ]; then
    echo 'Clean database seed missing. Fetch Git LFS files before starting PostgreSQL.' >&2
    exit 1
fi
(cd "$bootstrap_dir" && sha256sum -c "$(basename "$checksum")")
if [ "$(head -c 5 "$archive")" != PGDMP ]; then
    echo 'Clean database archive is not materialized. Run git lfs pull.' >&2
    exit 1
fi
if ! pg_restore --list "$archive" >/dev/null; then
    echo 'Invalid clean database archive. Run git lfs pull and verify its checksum.' >&2
    exit 1
fi
psql --no-psqlrc --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set ON_ERROR_STOP=1 --set "backup_manifest=$(cat "$manifest")" <<'SQL'
SELECT 1 / CASE WHEN :'backup_manifest'::jsonb ->> 'format' = 'wakemu-clean-database-v1'
    THEN 1 ELSE 0 END AS clean_seed_manifest_valid;
SQL
pg_restore --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --no-owner --no-acl --exit-on-error --single-transaction "$archive"
psql --no-psqlrc --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    --set ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
    IF (SELECT count(*) FROM public.accounts) <> 1
       OR NOT EXISTS (SELECT 1 FROM public.accounts
                      WHERE username = 'admin' AND username_key = 'admin' AND is_admin)
       OR (SELECT count(*) FROM public.account_wallets) <> 1
       OR NOT EXISTS (SELECT 1 FROM public.account_wallets w
                      JOIN public.accounts a ON a.id = w.account_id
                      WHERE a.username_key = 'admin' AND w.kamas = 0)
       OR EXISTS (SELECT 1 FROM public.characters)
       OR EXISTS (SELECT 1 FROM public.sessions)
       OR EXISTS (SELECT 1 FROM public.tokens) THEN
        RAISE EXCEPTION 'Clean database seed contains unexpected player or account state';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM public.native_catalog_active a
                   JOIN public.native_catalog_releases r ON r.revision = a.revision
                   WHERE a.id = 1 AND r.complete) THEN
        RAISE EXCEPTION 'Clean database seed has no complete active catalog';
    END IF;
END;
$$;
SQL
echo 'Wakemu clean seed restored (admin/admin); subsequent starts use the persistent volume.'
