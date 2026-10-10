# Parallel review regression checks — 2026-10-09

## Scope

Ran focused offline regression tests for native remote effects and spectator snapshots, account-shared Haven Bags and visitor permission policy, mount feeding/identity/publication, dungeon achievement authority, and profiler counters/storage. No runtime code, database service, Docker service, or running world process was changed by this review.

## Results

Interpreter: `.runtime/local/verification-venv/bin/python` (Python 3.12.9).

The focused command ran 140 tests across these modules:

- Combat: `test_combat_remote_effects`, `test_combat_remote_effects_active`, `test_combat_spectator_snapshot`, `test_combat_spectator_return_dispatch`, `test_combat_spectator_events`, `test_combat_spectators`, `test_aborted_spectator_terminal`.
- Haven Bag: `test_account_haven_bag`, `test_haven_bag_exterior`, `test_haven_bag_furniture_world`.
- Mounts: `test_mount_feeding`, `test_mount_feeding_dispatch`, `test_mount_feeding_wire`, `test_mount_publication`, `test_mount_inventory`.
- Dungeons: `test_dungeon_achievement_authority`.
- Profiler: `test_performance_profiler`, `test_storage_performance_profiling`.

The standard invocation completed with **139 passing tests and one skipped fixture-dependent test**. Two AST-based tests had been missing the `PROFILER` global introduced by the profiler decorators in their isolated execution namespaces. Their fixtures now explicitly provide the imported global, and the complete focused command passes without runtime changes.

The skipped case, `test_full_format11_build_and_feed_refresh_uses_owned_public_characteristics`, requires a mounted-character capture that was not present in the checkout.

The external profiler service suite also passed **14 tests** (`server/profiler-service/tests/test_service.py`, 0.578 s). Coverage includes one-hour capture-group expiry, oldest-first byte-cap eviction and truncation status, PID/start-time metrics, five-second timeline sampling, successful chunk chaining, and retry after a failed sampler chunk. These are offline lifecycle tests; they do not start the profiler service or the world process.

PostgreSQL case tests emitted the existing “Catalog Redis read/write failed; using PostgreSQL: KeyError” fallback messages. These were non-fatal; relevant tests completed against PostgreSQL.

## What these checks establish

- Remote effect decoding rejects malformed or unverified payloads, and complete spectator snapshots preserve tracked effects and fail closed for missing/private effect state.
- Spectator event delivery deduplicates recipient copies, keeps terminal events ordered, and retires observer state after terminal acknowledgements.
- Haven Bag persistence is account-scoped, cross-account access is rejected, and visitor permissions are checked before entry.
- Mount feeding consumes food once, persists XP and mount state, enforces or disables the daily XP policy, and publishes refreshed mount state in the expected order. Inventory tests cover UID ownership and active-build reconciliation.
- Dungeon achievement snapshots distinguish absent, running, completed, and objective states; Miabuelita’s negated criterion maps to objective 11515.
- Profiler counters aggregate wall time, CPU time, errors, and bounded feature labels; storage instrumentation separates connection-pool wait from transaction time.

## Limits

These tests are offline unit/integration checks and do not establish successful client behavior for the current live reports. They do not prove that a late spectator sees or can target newly created beacons, that beacon attacks trigger their elemental explosion, or that a rejected request had no already-committed mutation. They do not exercise Tofullero’s real gate traversal or prove its first encounter composition/order. Haven Bag tests do not verify that the management-center UI opens for the second character or that its native client can move to and use the workshop. Mount persistence tests do not settle the reported live two-mount deletion/display confusion. Profiler core/storage tests do not measure the currently deployed external sidecar lifecycle or one-hour retention policy.

Live acceptance evidence and those unresolved outcomes remain documented in the per-issue review reports and `docs/soluciones-wakemu/USER-ACCEPTANCE-20261009.md`.
