# Database snapshot

`backups/wakemu-runtime-20261012.dump.part-*` is a complete PostgreSQL custom-format snapshot, including native catalogs and the current development accounts, characters, sessions, ecology state and test schemas. It is not an empty installation seed.

The snapshot is **773,917,699 bytes (774 MB)** compressed, split into **450,000,000** and **323,917,699** byte parts. It uses PostgreSQL custom-format Zstandard level 3 compression and is split into parts of at most 450,000,000 bytes, each below 500 MB. All parts are required. Git LFS tracks `*.dump.part-*`; the checksums remain normal text files. [The manifest](backups/wakemu-runtime-20261012.dump.manifest.json) records the exact compressed size, snapshot timestamp, checksums and retained revisions. This captures PostgreSQL, not Redis, game-process memory or runtime files.

Verify from the repository root:

```sh
(cd database/backups && shasum -a 256 -c wakemu-runtime-20261012.dump.parts.sha256)
cat database/backups/wakemu-runtime-20261012.dump.part-* > /tmp/wakemu-runtime-20261012.dump
shasum -a 256 /tmp/wakemu-runtime-20261012.dump
# Compare with database/backups/wakemu-runtime-20261012.dump.sha256.
```

Restore into a **new, empty database** with a PostgreSQL 17 client. This imports the snapshot; it does not merge player state. Supply the connection through normal PostgreSQL environment variables or a private password file:

```sh
createdb wakemu_restore
pg_restore --no-owner --no-acl --exit-on-error --dbname wakemu_restore \
  /tmp/wakemu-runtime-20261012.dump
psql --dbname wakemu_restore -c "SELECT revision, document_count FROM native_catalog_releases ORDER BY revision;"
# Expected: exactly four releases, matching the manifest.
```

The archive excludes global roles/role passwords. Create deployment roles and permissions separately. Restoring the file does not start the server or generate protocol replay templates.

## Docker initialization

Compose mounts the backup directory into PostgreSQL, verifies part checksums, reconstructs a temporary archive, and runs `docker/20-restore-runtime.sh` **only when `postgres-data` is empty**. The initial database is `wakemu_runtime`; world and AI use that database. Normal restarts retain the database volume and do not restore the snapshot again. New migrations are applied by the world entrypoint after PostgreSQL initialization.

For a fresh checkout:

```sh
git lfs pull
python3 tools/prepare-local-runtime.py
docker compose up -d postgres redis
```

An existing installation keeps its current volume. Do not delete that volume to apply ordinary code changes. Build world before AI with `bash tools/build-local.sh`, then use `docker compose up -d --build` to build the remaining services and start the stack. Persistent private credentials belong in `.database/secrets/`; `database/` contains the repository bootstrap scripts and snapshot. See the [setup guide](../docs/getting-started.md#current-setup-requirements) before upgrading an existing installation. Current world source reads verified bootstrap records from PostgreSQL; verify their presence rather than assuming catalog restoration supplies them. See [bootstrap internals](../docs/protocol/world-synchronization.md).

## Catalog retention

The snapshot follows a verified live cleanup of 16 obsolete releases, 18,369,041 catalog records and 112,293 catalog documents. Four complete releases remain: the active catalog, the pinned mining and fishing releases, and the dungeon launcher's required source revision. Their document counts, source sizes and path/hash inventories were preserved. All other gameplay data was retained.

The full pre-cleanup snapshot was archived privately under `.runtime/local/backups/wakemu-runtime-20261012-full-before-cleanup.dump`, outside Git. It is 5,547,093,201 bytes and passed a complete archive read/decompression check before cleanup. The superseded October 8 snapshot and checksum were removed from Git after verification. The game stack was shut down with its data volumes preserved, so the old archive mount and its temporary compatibility marker were also removed. Fresh and existing checkouts use the backup directory mount configured in Compose.
