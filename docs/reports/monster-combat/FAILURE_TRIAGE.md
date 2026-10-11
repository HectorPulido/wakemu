# Local unit failure triage

Date: 2026-10-10

## Scope and safety

This report classifies local unit-test diagnostics; it does not certify an activation or a production release. The broad run used the active native catalog through `WAKFU_DATABASE_URL`, with `PGOPTIONS='-c default_transaction_read_only=on'`, `WAKFU_POSTGRES_TEST_URL` unset, and Redis catalog reads replaced by an in-process `NoRedis` adapter. No database write opt-ins were enabled. This records the configured test conditions; it is not a claim that an independent write guard was proven. No services were started or restarted.

The checkout and catalog sources changed during this work. Treat the broad result and follow-up probes as diagnostics against the state observed by each run, not as one pinned certification. Logs and ID lists are retained under `.runtime/monster-local-unit-20261010/`.

## Broad discovery result

`unittest` discovered 6,151 tests in 608.343 seconds: 197 failures, 109 errors, and 1,477 skips. The remaining 4,368 result records were neither failures nor errors; this count includes subtest records and is not a count of unique test methods. The 306 failing/error result IDs are in `unittest-discovery-readonly-ids.txt`; grouped module/cause output is in `failure-triage-306-groups.txt`.

The exception-class distribution across those 306 records was 201 `AssertionError`, 46 `ValueError`, 21 `NameError`, 15 `AttributeError`, 10 `KeyError`, 4 `SyntaxError`, 3 `FileNotFoundError`, 2 `IndexError`, 2 `UnboundLocalError`, and one each `ModuleNotFoundError` and `TypeError`.

The highest-count group was `test_combat_character_copy_runtime_book` (144 subtest failures), followed by `test_combat_original_controller_area` (24) and `test_static_map_sync_dispatch` (17). Those counts are clustered records, not independent defects. The other combat groups account for most of the remaining records. There were 52 records outside modules named `test_combat*`; the non-combat module counts were:

| Module | Records |
| --- | ---: |
| `test_static_map_sync_dispatch` | 17 |
| `test_chat_command_routing` | 4 |
| `test_checkpoint_delivery_order`, `test_haven_bag_transfer`, `test_session_cleanup`, `test_placement_deadline` | 2 each |
| `test_captured_class_dependencies`, `test_captured_roster_departure_integration`, `test_captured_summon_native_fixture`, `test_effect_characteristic_registry`, `test_hero_switch_dispatch`, `test_idle_health_regeneration`, `test_monster_growth_catalog`, `test_npc_actor_identity`, `test_owned_native_bootstrap`, `test_planting_package`, `test_scene_registry_dispatch`, `test_shard_identification_dispatch`, `test_social`, `test_spell_audit`, `test_spell_inventory`, `test_swimming`, `test_territory_weather_publish`, `test_wire`, and one import/other record | 1 each |

## Triage by cause

### Test harness omissions confirmed by production source

- AST-extracted server functions that use the imported `PROFILER` raised `NameError` in static-map, checkpoint, and scene-dispatch tests. `local_game_server.py` imports `PROFILER` and applies it as a decorator; isolated harness namespaces need a no-op profiler binding. This is a harness omission, not evidence of a missing runtime symbol.
- `test_chat_command_routing` compiled a nested function declaring `nonlocal fight_messages` while its synthetic outer factory omitted that closure cell. The real `session` initializes it. The fixture should model that binding and the production profiler decorator while retaining behavioral assertions.
- `test_session_cleanup` and `test_idle_health_regeneration` extract code whose production locals include `flora_ticket`, `guild_chest_session`, `combat_session`, and other session state. Missing bindings can mask behavior with `NameError`; only add fixture bindings backed by the real session initialization.
- `test_hero_switch_dispatch`'s mocked leader lacked runtime fields (`level`, `breed`) consumed by the actual statistics path. This is a fixture completeness issue.
- `test_npc_actor_identity`'s fake DB did not model transaction status, durable group/member rows, alias lookup, or update row counts required by `repair_available_group`. The test needs a faithful fake or a narrowly scoped DB fixture before its failure can say anything about the repair behavior.
- `test_owned_native_bootstrap` patched `dungeon_physical_doors` through a different import alias from the one used by `dungeon_native_flow`. A test patch must target the object actually looked up by production code.

### Source/test contract discrepancies retained as red

- Placement tests still assert the former `heartbeat/current_session/if not valid` source sequence and an exact three-callback count. The current idle handler calls `STORE.session_health(..., renew=...)` and closes invalid sessions before deadline/readiness work; current source also has additional serializers. These tests remain red pending a review of the intended lease contract and callback guarantees. Do not make the assertions pass by dropping the lease guard or weakening callback coverage.
- The social company-packet test expects the final active-owner bit to be zero. Both `characters/social.py` and `characters/hero_wire.py` currently emit `int(character is not None)`, so a non-null character produces `1`. The local progress fields remain zero. The test/source protocol expectation needs an explicit decision; no production behavior was changed.
- Weather callback discovery in the test only scans the initial literal callback dictionary. Production adds `territory_weather_tick` later under the `ECOLOGY_MODE == "inline"` guard, and inline is the default mode. Separately, `server/cron-service/config.json` currently disables that cron job. The scheduler activation state is therefore a real unresolved configuration question, not something to fix by changing the test or enabling the cron during triage.
- Checkpoint-order expectations require owner and other-recipient notices before asynchronous submit. The current extracted `checkpoint_fight` drains shared combat before submission, but its current body does not emit those two notices. Preserve this as a potential behavior regression until the notice ownership and ordering contract is checked against the current delivery path; do not alter the expectation to hide it.
- Static-map dispatch has both harness `PROFILER` errors and assertion mismatches around map retry/rearm wiring. A profiler shim only removes the harness error; it does not establish that every join path rearms. Keep the source assertion failures visible for focused review.

### Active data and missing asset mismatches

- `test_spell_audit` pins 722 spells while the active catalog reports 730. `test_swimming` pins 742 verified and 219 unknown map counts while the active topology differs. These are snapshot-dependent assertions; re-run against a pinned catalog before deciding whether source or test data is wrong.
- `test_effect_characteristic_registry` excludes eYO rows even though the active registry includes classes 16, 950, 951, and 952 and runtime code contains eYO dispatch. This merits an explicit registry/runtime contract review, not a blind exclusion or catalog rewrite.
- `test_spell_inventory` and `test_passive_audit_workload` cannot find `server/protocol/spells.json`; this checkout has no such source asset. No private/deployment data was copied into the repository to satisfy those tests.
- `test_planting_package` expects protocol seed inputs in the server image, while the present Dockerfile does not copy them. `.dockerignore` allows protocol assets, but the exact required inputs are absent from this checkout. This is a likely packaging/source-input gap; confirm intended asset provisioning before changing image contents.

### Earlier environment-only run

The first discovery without `WAKFU_DATABASE_URL` ran 3,394 tests with 5 failures, 1,284 errors, and 448 skips. Of those errors, 1,255 were missing-database-URL failures; 467 import failures were nested within the aggregate error total, not additional tests to add. That run is superseded for environment diagnosis by the read-only native-catalog rerun, but remains useful evidence that the first failure shape was configuration-dominated.

## Targeted reproduction records

The active-catalog targeted run before fixture adjustments is `failure-triage-targeted.log` (43 tests, 4 failures, 17 errors, 2 skips) and `failure-triage-other-targeted.log` (86 tests, 4 failures, 18 errors, 10 skips). A profiler-injected static-map probe is in `failure-triage-static-map-profiler-shim.log`. These are earlier snapshots and should be read with the checkout-mutability caveat above.

The later combined targeted run is `failure-triage-fixed-targeted.log` (117 tests, 3 failures, 10 errors, 12 skips). It exposed residual harness omissions and the contract mismatches described above. A follow-up run after restoring the strict placement/social assertions and adjusting AST fixture bindings is recorded as `failure-triage-current-targeted.log`: 117 tests, 7 failures, 2 errors, and 12 skips. The seven failures are the two static-map assertions, two unchanged placement assertions, and one each for social, weather, and checkpoint ordering. The two errors are incomplete AST fixtures in logout cleanup and hero-switch dispatch. No remaining cluster is marked resolved merely because its total changed between snapshots.

To reproduce the full server discovery without writing Redis catalog cache entries, set `WAKFU_DATABASE_URL` to a local PostgreSQL conninfo using a protected `passfile`, leave `WAKFU_POSTGRES_TEST_URL` unset, and use:

```sh
env -u WAKFU_POSTGRES_TEST_URL \
  WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu passfile=/absolute/path/to/pgpass' \
  PGOPTIONS='-c default_transaction_read_only=on' \
  PYTHONPATH=server:server/tests:server/tools \
  .runtime/local/verification-venv/bin/python \
  .runtime/monster-local-unit-20261010/readonly_runner.py
```

Keep `pgpass` mode `0600`; do not print its contents or place credentials in logs. The runner installs a `NoRedis` adapter for both native-catalog entry points, discovers `server/tests/test_*.py`, writes no opt-in variables, and prints test/failure/error/skip counts. The complete raw output, exit code, ID extraction, and grouped summaries are retained in `.runtime/monster-local-unit-20261010/`.

## Recommended next actions

1. Pin the active catalog/source hashes and re-run focused combat groups before treating large combat clusters as code failures.
2. Review placement lease semantics and checkpoint notice ownership with runtime call-path evidence; retain the strict tests until the behavior decision is made.
3. Decide whether the weather cron should be enabled in configuration through the normal deployment review; this triage did not change scheduler configuration.
4. Provision or explicitly declare the protocol spell/seed assets required by inventory, audit, and image tests.
5. Keep fixture-only AST shims local to tests and limited to production globals/locals the extracted code actually references.
