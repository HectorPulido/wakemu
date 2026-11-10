# Clean PostgreSQL installation backup

`backups/wakemu-clean.dump` is a PostgreSQL 17 custom-format installation seed, stored with Git LFS. It is built in a new isolated database from the versioned schema and verified public installation data, not by deleting players from a production dump.

It contains the active native catalog, its mining and fishing dependencies, the synthetic identity-free protocol bootstrap, public dungeon/shop/treasure definitions and static environmental policies. It contains no existing accounts, characters, sessions, tokens, inventories, live creatures, planted resources, ecological progress or private captured bootstrap. The only account is a newly generated administrator:

- Username: `admin`
- Password: `admin`
- Characters: none
- Wallet: zero

Compiled catalog caches are omitted because they can be rebuilt. World prepares them on its first startup and reuses unchanged publications thereafter. Static ecology definitions let a new world generate its own population; no running world's ecology is restored.

## Fetch and verify

```sh
git lfs install
git lfs pull --include='database/backups/*.dump'
(cd database/backups && shasum -a 256 -c wakemu-clean.dump.sha256)
```

The accompanying `wakemu-clean.dump.manifest.json` records the schema, public inputs, allowed seed tables, privacy audit, archive size and checksum.

## Restore

For a fresh installation, copy `.env.example` to `.env`, configure its local secrets and run `docker compose up -d --build` so service images match the current schema. The default native revision matches this seed.

The standard Compose PostgreSQL service mounts this directory and runs `docker/20-restore-runtime.sh` only while initializing an empty data volume. The script validates the manifest/checksum/archive, restores it and verifies the administrator and empty player state. Existing volumes are preserved on normal restarts and never receive the seed again.

For a separate empty database using PostgreSQL 17 tools:

```sh
createdb wakemu_restore
pg_restore --no-owner --no-acl --exit-on-error --dbname wakemu_restore \
  database/backups/wakemu-clean.dump
```

Do not import this installation seed over an existing player database. Server secrets, TLS keys and Redis state are generated/configured separately and are not part of the archive.
