# Dedicated dungeon configuration storage

Dungeon configurations no longer belong in generic `settings` rows. Migration 114 introduces two domain tables:

| Table | Purpose |
| --- | --- |
| `dungeon_runtime_configurations` | Immutable JSON configuration per `(route_key, policy_version)` |
| `dungeon_runtime_active_configurations` | Active version per route, with a foreign key to an existing configuration |

The migration copies every legacy `dungeon_runtime_config:<route>:v<version>` document and `dungeon_runtime_active:<route>` selection, verifies identities and conflicts, and only then removes those exact legacy prefixes from `settings`. An invalid document, missing selected version or conflict aborts the transaction. Unrelated settings and the single `dungeon_runtime_routes` registry remain unchanged. Database constraints validate route/version identity, and a trigger prevents modification or deletion of a stored version.

Runtime installation, active selection, pinned-instance lookup and native exit checks use the new tables. Context-policy tables retain their existing role. Existing instances still resolve their original version, including versions that are no longer active. The admin API preserves direct access through its existing names as virtual aliases backed by the domain tables, including optimistic revisions, audited updates and version history; those aliases do not create settings rows and are excluded from the general Settings listing, its search results and pagination counts. Configuration generation, activation backups and database auditing also use the dedicated tables. Historical migration 094 remains intact so a clean installation runs the original migrations before migration 114 moves their data.

## Delivery and acceptance

Deployed on 2026-10-10 at 20:28 America/Bogota after explicit user authorization. The previous world and admin processes were stopped before a final gameplay database backup and legacy-document snapshot; the complete shared server image then applied migration 114 through the normal startup sequence. World and admin are healthy, and both HTTP health endpoints return 200. Other services were not restarted.

Runtime readback verified all **134 immutable configuration versions** and **87 active selections** against the final legacy snapshot, with exact JSON equality and **zero legacy configuration/selection rows** remaining in `settings`. Both pre-existing active dungeon instances retain their route/version pins and resolve them through the new table. The administrative alias `dungeon_runtime_config:native_dungeon_142:v2` still reads version 2, while the active alias selects version 3 and lists both historical versions.

World image: `sha256:af994a64bc39fe82ada08968143efc14f9b4b3114b42bd3bd5c3a7148a0ee588`. Admin image: `sha256:28a027510ddc4d906010c9e9be49ece703f17fac3ab9fb9829aab5e2bed1d737`. All 759 runtime source/migration files match the verified shared checkout; full image compilation passed. Private backups and deployment manifests are under `.runtime/local/dungeon-storage-deployment-20261010/`. The gameplay dump excludes the data of the two large immutable native-catalog tables; their data was not changed by this migration. Previous images were retained for recovery.

This deployment migrates existing configuration storage. It does not activate the complete set of 107 prepared ordinary dungeon routes or constitute graphical acceptance of their flows.

After deployment, inspect:

```sql
SELECT route_key, policy_version
FROM dungeon_runtime_active_configurations
ORDER BY route_key;

SELECT route_key, policy_version
FROM dungeon_runtime_configurations
WHERE route_key = 'native_dungeon_142'
ORDER BY policy_version;

SELECT name FROM settings
WHERE starts_with(name, 'dungeon_runtime_config:')
   OR starts_with(name, 'dungeon_runtime_active:');
```

The last query must return zero rows. Previously installed versions must remain in the configuration table. In the admin panel, open a dungeon configuration, publish a new version, switch back to a previous version, and confirm history and stale-edit rejection still work. Complete a fresh dungeon entry/exit cycle and, if an old instance exists, confirm it retains its pinned version rather than adopting the new active one.

Automated verification uses isolated PostgreSQL schemas, including migration preservation/rollback, immutable versions, active-pointer foreign keys, pinned runtime access, admin editing and generated SQL. It does not certify deployment or change any dungeon topology, roster, spell or combat behavior.

The final deployment-gate rerun passed **87/87 tests** in 258.963 seconds, with no skips or failures. Combat event replay and cast-event regressions separately passed **24/24 tests**. A broader 154-test smoke run found four existing combat/hero test failures; a read-only comparison against the previous running image reproduced all four, and the five implicated implementation modules were byte-identical. They are not introduced by this storage migration. It includes an actual schema 113 upgrade, malformed migration rollback, preservation of a run pinned to version one while version two is active, database immutability/identity/foreign-key constraints, unrelated similarly named settings, bulk installation, administrative revisions and native/shared-arena exit regressions. Tool verification separately passed five unit tests and two generated-SQL PostgreSQL tests.

With read-only runtime catalog access and `WAKFU_POSTGRES_TEST_URL` pointing to the isolated test database, reproduce the combined suite using:

```sh
PYTHONPATH=server:server/tests:server/tools \
  .runtime/local/verification-venv/bin/python -m unittest \
  test_dungeon_runtime_config test_install_dungeon_bulk \
  test_dungeon_runtime_postgres test_admin_settings test_admin_http \
  test_dungeon_configuration_storage_constraints test_dungeon_exit \
  test_dungeon_shared_arena test_dungeon_shared_arena_postgres
```

## Settings listing follow-up

At 20:36 America/Bogota, deployed an administration-only correction after the user reported that virtual dungeon aliases still cluttered Settings. Both dungeon prefixes are now excluded before pagination/count and search; direct version/history API access remains available. The complete admin image was hash-verified and compiled; 20/20 Settings/API tests passed. Runtime readback confirmed zero matching listing entries and preserved direct version access. World was not restarted. Current admin image: `sha256:69675f50bae2ac0d81097584e443763d773c8158a9045490506383c876c8c2bd`.
