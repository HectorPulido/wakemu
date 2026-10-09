# Native catalogs in PostgreSQL and Redis

Native exports are staged as plain JSON outside the runtime catalog directory and removed after verified import. World and AI protocol readers always use PostgreSQL and Redis. There is no backend selector or protocol-file fallback. Tests inject fixtures or use isolated PostgreSQL; source JSON is used by the importer. Missing database catalogs fail explicitly.

## Storage and indexing

`native_catalog_releases` identifies reproducible source releases. `native_catalog_documents` retains exact source bytes and SHA256 with a composite primary key `(revision, path)`, preserving native checksum validation. `native_catalog_records` exposes entity collections as JSONB, keyed by `(revision, path, collection, record_key)`, with another index on `(revision, collection, record_key)`. Repeated native references remain separate variants. `native_catalog_active` publishes a complete release atomically.

Spatial grids remain exact documents, and existing runtime coordinate indexes remain in memory; importing a document does not pretend to normalize every spatial cell into a relational table. Existing spell, monster and coordinate dictionaries and caches are preserved, avoiding a database query for each combat action.

Redis stores versioned catalog entries for one hour, with a 2 MiB per-entry limit. Large catalogs come from PostgreSQL once per existing reader cache. PostgreSQL is authoritative; missing or invalid Redis data is rebuilt from it. A process pins its release so cache keys and native catalogs cannot mix revisions.

## Automatic import

`tools/import_native_catalogs.py --directory <staging-directory>` imports exported data before a release is built. The world entrypoint applies migrations and verifies the complete published release pinned by the image before opening listeners. It never reimports local files. Import staging is resumable per document. A failed document does not publish a partial release. Import sources are hashed in chunks; exact bytes and parsed entity records are committed together. Existing releases are preserved.

## Manual acceptance

1. Connect DBeaver using [the local connection settings](dbeaver-postgresql-access.md).
2. Run the queries below. Expect one complete active release, catalog documents and indexed entity records.
3. Log in without moving. Inspect the character and nearby interactables. Walk between the Tainela dragoturkey and Gobball dungeon, use both, enter the dungeon, fight, leave and return. Expect the same behavior as before catalog migration, without missing objects or spell data.
4. Check world health after restart. Native catalog data must come from the published database release; there are no JSON files in `server/protocol`.

```sql
SELECT r.* FROM native_catalog_active a
JOIN native_catalog_releases r USING (revision);

SELECT collection, count(*)
FROM native_catalog_records n
JOIN native_catalog_active a USING (revision)
GROUP BY collection ORDER BY count(*) DESC;

SELECT record_key, payload->'combat_drops' AS combat_drops,
       payload->'collect_items' AS collect_items
FROM native_catalog_records n
JOIN native_catalog_active a USING (revision)
WHERE path = 'monster-encyclopedia.json' AND collection = 'monsters'
ORDER BY record_key;
```

## Validation

Conversion-sensitive checks cover drops/collection, terrain, spell and state catalogs, byte integrity, database activation/retry and Redis misses/corruption. Full runtime image verification compares source hashes, preserving concurrent combat and spell changes. Deployment evidence is recorded after the import and complete image are verified.

## Verified migration snapshot — 2026-10-08

Published release `7071a8d8c8664e9e0d5fe8f44bf2a948d4138060fc1353ea70f65f2dcf00b568`: 7,482 documents, 1,211,086 indexed records and 2,261,560,691 source bytes. PostgreSQL SHA256 checks over every raw document found zero mismatches. The 7,482 protocol JSON files and 6,589 compressed JSON files were removed after verification.

Private full dump: `database/backups/wakemu-runtime-20261008-native-catalogs.dump` (312,043,217 bytes, mode 600). SHA256 `5916a0f1b0443e8ec3696afef80197c742b30aa557a823f4c7db2c4b938f96b2`. `pg_restore --file=/dev/null` successfully read the complete custom archive. The adjacent `.dump.sha256` file records its checksum.

Final source image `wakemu-world:postgres-redis-catalogs-20261008-r46` matched all 644 packaged source files. Provider checks: 13 passed, including one decode for 24 concurrent loads and no file fallback. Importer checks: 7 passed. AI bridge checks: 28 passed. Earlier conversion-sensitive checks: 80 drops/collection, 54 catalog/terrain/combat and 13 state/territory checks passed. Two unrelated existing fixtures failed (timeline snapshot completeness and passive count 339 versus 483); a heavyweight collision suite was stopped without claiming a pass.

Deployment completed: world and AI are healthy. AI catalog preloading now runs before its HTTP listener starts, and world depends on AI health. Its content-addressed cache persists in `ai-context-data`; source catalogs remain authoritative in PostgreSQL. World startup completed a full context seal before opening game listeners. A shared decoded-document cache avoids multiple readers allocating duplicate state catalogs; 24 concurrent cold calls were verified to decode once. Complete cold catalog prewarm validated 62,691 effect definitions. Runtime image and checkout both contain zero protocol JSON/compressed JSON files. Inspector login and indexed Gobball reference lookup were reverified over localhost15432.
