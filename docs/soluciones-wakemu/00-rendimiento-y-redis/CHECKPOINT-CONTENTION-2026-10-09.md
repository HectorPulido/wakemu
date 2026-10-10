# Redis position checkpoint contention — 2026-10-09

Status: source correction verified against offline contention regressions and an isolated PostgreSQL schema. Not deployed. The minutes-long live incident has not been captured with thread stacks; the confirmed lock amplification below can freeze all position consumers whenever one database row or pool slot stalls.

## Confirmed failure mechanism

`Positions.flush()` formerly held the single position-buffer RLock while acquiring a PostgreSQL pool connection, locking every selected session row with `FOR UPDATE`, updating every character, and committing one global transaction. `RedisPositions.flush()` also performed Redis acknowledgments under this lock. Movement, health/build merges and attach used the same lock. PostgreSQL statements had no local lock/statement deadline. Thus a single blocked row stopped every player using the buffer; a failure also rolled back unrelated owners.

The login takeover path also held this global lock while flushing positions and replacing the session. A database wait could therefore extend across world/session ownership operations. The periodic cron configuration currently requests checkpoints every two seconds. The local fallback flusher is disabled when the external scheduler is enabled; these are alternative schedulers, not proven duplicate workers. The historical README reference to a twenty-minute interval does not describe the current configuration.

## Correction and durability

- Account-specific ownership barriers replace the global I/O lock. The registry lock only protects short dictionary snapshots/mutations.
- A periodic flush commits each account independently, continues healthy accounts after another owner's failure, then reports the failure for retry. Atomicity is preserved within each account, not across unrelated accounts.
- Checkpoints obtain a pool connection before trying the account barrier. Barrier acquisition is nonblocking: an occupied owner fails for retry and returns its connection, preventing pool/account lock inversion with login takeover.
- Checkpoint pool acquisition is bounded to 250 ms. Position attach uses the same pool deadline. Checkpoint/attach row-lock wait is bounded to 250 ms and each SQL statement to 1,000 ms.
- Redis writes still precede authoritative movement mutation. PostgreSQL commits still precede clean-buffer state and Redis acknowledgment. Generation checks, position CAS, revision-aware ACK, recovery and lifecycle flush barriers remain intact.
- Login takeover uses its account barrier. Friendly duel acceptance checkpoints only the two pending invitation owners, through a separately reviewed helper.
- `position_batch_timing` records total latency, result and count. `position_checkpoint_stage` records pool acquisition, successful PostgreSQL commit and Redis ACK stages.

Redis network failure may still delay the affected account up to its configured socket timeout (two seconds). It does not retain the global position-buffer lock. Other locks held by callers and unrelated background jobs remain separate investigation targets if the live stall persists.

## Validation

Thirty tests passed without skips: 24 existing position/Redis-journal integration tests and six new contention tests, including a real PostgreSQL row lock in a temporary schema in `wakemu_migration_test`. The published native catalog was read from `wakemu_runtime`; runtime game rows were not changed. No service was started, restarted or deployed.

The real contention test locks account A's session row, starts the global checkpoint, and verifies account B moves within 100 ms while A remains blocked. PostgreSQL raises `LockNotAvailable`; A remains dirty. The checkpoint still commits B, and retry after releasing the lock commits A's exact latest coordinates. Offline tests additionally verify pool checkout waits do not retain ownership locks, a busy account promptly returns the acquired connection, takeover barriers remain reentrant, and failed commit preserves both dirty memory and Redis mirror.

Commands (from repository root):

```sh
export WAKFU_POSTGRES_TEST_URL='host=127.0.0.1 port=15432 dbname=wakemu_migration_test user=wakemu'
export WAKFU_DATABASE_URL='host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu'
export WAKFU_DATABASE_PASSWORD_FILE="$PWD/.runtime/local/secrets/postgres-password"
PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest \
  test_position_buffer test_position_redis.RedisPositionTests \
  test_position_redis.RedisFailureTests test_position_buffer_contention -v
```

Real network Redis cases require a separate isolated Redis test namespace/URL; the 30-test result uses the existing in-memory revision-CAS Redis backend together with real PostgreSQL, not a claimed network Redis acceptance.

## Complete manual acceptance after a full shared world build

1. Form a group with two development-authorized accounts. On both accounts run `!tp 1134 51 8 0` and `!pos`. On A run `!mob 4196 1 1`, attack the spawned group, and have B join during placement. Play multiple turns, including movement, spells and turn changes. If joining markers are unavailable, use the already accepted shared-combat entry flow; missing swords are a separate open issue. A third available account can move outside combat at the same time.
2. Keep playing through several scheduled checkpoints; the current interval is two seconds. Neither spell resolution nor turn progression should freeze. Capture timestamps if a delay recurs.
3. Finish normally, travel outside, enter/exit a Haven Bag and reconnect both accounts. Positions, rewards and account ownership must remain correct.
4. Run `rg 'position_batch_timing|position_checkpoint_stage|position_batch_flush_failed' .runtime/local/logs/game-server.jsonl` (use the configured runtime mount if different) and review `position_batch_timing` / `position_checkpoint_stage` alongside `position_batch_flush_failed` and scheduler outcomes. Repeated failed saves are not acceptance even if play remains responsive. Do not induce database locks in the live game to test this.

Do not close issue 0 until the complete image is deployed and this manual acceptance confirms the live behavior.

## Live recurrence after the first correction (r56)

The first checkpoint correction was deployed, and the issue **recurred**. It is not an accepted fix for the reported freeze. Boot `1d1b2b97d0da4da4975cbeef72eb5f03` records a global checkpoint at 19:54:10–19:54:51 UTC taking **41,430.534 ms with zero characters committed**, while its individual pool stages took 13.903 and 32.829 ms and Redis ACK stages took 0.003 and 0.005 ms. The same interval contains `session_idle_slow` at **41,967.685 ms** during scene synchronization (outbound 12344 updates). This demonstrates a real pause that the earlier SQL/Redis-only correction did not remove; it does not identify the responsible thread by itself.

A subsequent read-only PostgreSQL sample found no blockers and idle runtime pool connections. A later py-spy nonblocking dump found normal idle client receive stacks and idle checkpoint writers. A 60-second 10 Hz recording produced 76 active samples, with 15 read errors; the clients disconnected during this diagnostic window, so the problematic interval was not captured. Private artifacts are under `.runtime/local/diagnostics/live-freeze-20261009-*`. No signal, restart or deployment was used. A concurrent test container and high PostgreSQL CPU were observed before the test workload ended; correlation alone does not prove the freeze's cause.

A separate confirmed amplification remains in the live source: `write_records()` synchronously writes the bind-mounted diagnostic file while holding **the same global `LOCK` used by LIVE ownership and `position_lease_active()`**. A stalled diagnostic filesystem write can therefore stop otherwise fast checkpoints, lease checks and game sessions. New source removes this coupling through `AsyncDiagnosticLog`: a dedicated writer, a bounded memory queue, reserved capacity for failed/rejected/exception/shutdown diagnostics, request-batch ordering, explicit overflow counters and a one-second shutdown bound. Authoritative saves remain synchronous at their existing barriers; only diagnostics become asynchronous. This second correction is not deployed and is not proof that the observed 41-second pause was a filesystem stall. A fresh live reproduction with stacks remains necessary before closure.
