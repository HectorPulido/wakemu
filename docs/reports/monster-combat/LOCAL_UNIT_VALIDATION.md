# Local unit validation: monster combat work

Run date: 2026-10-10. These runs are local diagnostics against a mutable checkout. They do not certify activation or prove source stability. No production code was changed as part of this test-and-document task.

## Safety and reproducibility

All Python runs used `.runtime/local/verification-venv/bin/python`. The server discovery used `PYTHONPATH=server:server/tests:server/tools`. Tests which require `WAKFU_POSTGRES_TEST_URL` were left disabled; no DB test opt-ins were set. For the later server pass, `WAKFU_DATABASE_URL` used libpq `passfile=` (the password itself was kept in a mode-0600 `.runtime/monster-local-unit-20261010/pgpass` file and is not included here), and `PGOPTIONS='-c default_transaction_read_only=on'`. A preflight reported `default_read_only=on` and `transaction_read_only=on` for database `wakemu_runtime`. Redis calls were replaced with a no-op `NoRedis` (`get -> None`, `setex -> None`) in both native catalog module import paths. The test loop did not enable any database-writing test suite. No Docker commands, service starts, or restarts were run.

The exact discovery harness is preserved at `.runtime/monster-local-unit-20261010/readonly_runner.py`. From repository root, set a password-file-only connection string in `WAKFU_DATABASE_URL` (for example `host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu passfile=/absolute/path/to/private/pgpass`), then run:

```sh
env -u WAKFU_POSTGRES_TEST_URL \
env -u WAKFU_POSTGRES_TEST_URL \
WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu passfile=/absolute/path/to/private/pgpass' \
PGOPTIONS='-c default_transaction_read_only=on' \
PYTHONPATH=server:server/tests:server/tools \
.runtime/local/verification-venv/bin/python \
.runtime/monster-local-unit-20261010/readonly_runner.py \
> .runtime/monster-local-unit-20261010/unittest-discovery-readonly.log 2>&1
```

Do not put a password in the connection string or command line. The runner imports both catalog modules before discovery to patch their Redis adapters; it otherwise uses standard `unittest` discovery order. This run did not disable GC. Its test runner completed in 608.343 seconds; interpreter cleanup continued after the summary because the discovered suite retained large catalog fixtures. Future repeated runs may try `gc.disable()` at harness startup to reduce full-heap scans, but that would be a distinct run configuration and should be recorded as such.

## Results

The first broad server discovery intentionally had no database URL, to reveal tests that import without local DB configuration. The later count is larger because the database URL activates additional tests/import paths; the two test totals are separate runs and must not be compared as a single suite delta:

- Command: `PYTHONPATH=server:server/tests:server/tools .runtime/local/verification-venv/bin/python -m unittest discover -s server/tests -p 'test_*.py'`
- Result: 3,394 tests; 1,657 passed; 448 skipped; 1,284 errors; 5 failures.
- The dominant error was absent `WAKFU_DATABASE_URL` (1,255). The 467 import errors are included in the 1,284 total, not additional failures. This first run is an environment diagnostic, not a product regression count.
- Full output and summarized IDs: `.runtime/monster-local-unit-20261010/unittest-discovery.log`, `discovery-summary.txt`, `error-ids.txt`, and `failure-ids.txt`.

The later pass supplied the local PostgreSQL connection while keeping it read-only and Redis disabled:

- Result: 6,151 tests; 197 failures; 109 errors; 1,477 skipped; 4,368 tests neither failed nor errored (608.343 seconds).
- This is not a green run. Failures and errors are test/fixture/code issues observed in the current shared checkout; the complete tracebacks are in `.runtime/monster-local-unit-20261010/unittest-discovery-readonly.log`, with all 306 IDs in `unittest-discovery-readonly-ids.txt`.
- Concentrations (the unittest output includes subtests, so these are result records rather than unique test methods): 144 records are in `test_combat_character_copy_runtime_book` and report absent copied native spell entries; 24 are in `test_combat_original_controller_area` with expected opcode `1008` versus `16777219`; 17 are in `test_static_map_sync_dispatch`; 11 in `test_combat_summon`; 8 in `test_combat_melee`; 20 failures report `PROFILER` undefined. Other errors include missing native QI/timeline/casting fixture populations, malformed static fixtures (`direction`, obstacle identities), a missing `server/protocol/spells.json`, and individual test doubles missing newly required attributes. These clusters should be triaged against the intended mutable source/test fixture state before interpreting them as regressions.
- Some tests share cached/global native catalog state; discovery-order effects are possible. No assertion was weakened and no source changes were made to force a pass. The 1,477 skips include intentionally disabled database integration tests because `WAKFU_POSTGRES_TEST_URL` and write opt-ins remained unset.

Combat class baseline/candidate diagnostics were run separately by the class-test agent:

- Baseline: 173/173 passed in 160 seconds; the source-stability check was false because a shared test fixture changed outside that run.
- Candidate: 173/173 passed in 134.12 seconds with sources stable.
- Both are local unit diagnostics only. Baseline and candidate were sequential; no world service was involved.

Independent service and language checks used separate runs and should not be added to the server totals:

- `server/profiler-service/tests`: 21 tests, all passed.
- `server/ai-service/tests` without a database URL: 501 tests, 40 errors; remaining tests passed. Full log: `.runtime/monster-local-unit-20261010/ai-service.log`.
- AI service rerun with the local PostgreSQL connection in read-only mode and NoRedis: 531 tests, 2 failures, 7 errors, 0 skips; 522 records neither failed nor errored (61.465 seconds). This run activated extra DB-backed catalog imports/tests, so its total differs from the first AI pass. Error IDs and tracebacks are in `.runtime/monster-local-unit-20261010/ai-service-readonly.log`. Three native-oracle cases fail casting eligibility (`twI`); three world-entry/metrics cases lack `map_id`; one stats test double lacks `native_fight_property_counts`. The two failures are `test_registered_creature_ownership_wire_and_unsupported_lifecycle_are_explicit` (expected lifecycle wording but received cast-eligibility rejection) and `test_real_search_and_native_session_select_freshly_certified_cast` (selected `move`, expected `cast`).
- `client-tools/tests`: 4 tests, 2 errors from a config fixture missing `open_dungeon_missions`; full log: `.runtime/monster-local-unit-20261010/client-tools.log`.
- Java loopback/network guard checks: 2 tests, both passed (`.runtime/monster-local-unit-20261010/java-guards/summary.json`).
- Root-run fast checks: 82 Python tests passed; AST parsing covered 2,022 Python files. These are separate scopes.

The observed environment-only failure groups, code/test fixture failures, skips, and diagnostic runs remain distinct. No result here should be read as activation approval.
