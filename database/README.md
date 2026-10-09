# Database snapshot

`backups/wakemu-runtime-20261008-native-catalogs.dump` is a complete PostgreSQL custom-format snapshot, including native catalogs and disposable development accounts, characters, sessions and test schemas. It is not an empty installation seed.

The snapshot is approximately 298 MiB, above GitHub's regular Git file limit. Use Git LFS for `*.dump` and ensure LFS storage is available before pushing. The checksum remains a normal text file.

Verify from the repository root:

```sh
(cd database/backups && shasum -a 256 -c wakemu-runtime-20261008-native-catalogs.dump.sha256)
```

Restore into a **new, empty database** with a PostgreSQL 17 client. This imports the snapshot; it does not merge player state. Supply the connection through normal PostgreSQL environment variables or a private password file:

```sh
createdb wakemu_restore
pg_restore --no-owner --no-acl --exit-on-error --dbname wakemu_restore \
  database/backups/wakemu-runtime-20261008-native-catalogs.dump
```

The archive excludes global roles/role passwords. Create deployment roles and permissions separately. Restoring the file does not start the server or generate protocol replay templates.

## Docker initialization

Compose mounts this archive into PostgreSQL and runs `docker/20-restore-runtime.sh` **only when `postgres-data` is empty**. The initial database is `wakemu_runtime`; world and AI use that database. Normal restarts retain the database volume and do not restore the snapshot again. New migrations are applied by the world entrypoint after PostgreSQL initialization.

For a fresh checkout:

```sh
git lfs pull
python3 tools/prepare-local-runtime.py
docker compose up -d postgres redis
```

An existing installation keeps its current volume. Do not delete that volume to apply ordinary code changes. Build all source images in dependency order with `bash tools/build-local.sh`, then start with `docker compose up -d`. Restoring this archive supplies the catalog data but does not remove the captured protocol-template dependency described in `docs/reports/runtime-portability-audit.md`.
