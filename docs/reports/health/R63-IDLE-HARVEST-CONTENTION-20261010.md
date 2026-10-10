# R63 socket maintenance contention

## Incident evidence

User reported extreme lag at approximately 22:57 America/Bogota on October 9,
2026 (03:57 UTC on October 10). Continuous captures covering 03:54–03:59 UTC
and their metadata were copied before rolling retention into the private
directory `.runtime/local/backups/lag-20261010T0357Z`.

In `capture-1791604628088416700.speedscope.json`, both client session threads
repeatedly wait at:

`session -> receive -> idle -> HARVESTS.due_availability -> _serialized.call`

The final frame is acquisition of the harvest registry lock. The two clients
have 478 and 523 samples in that path (0.04-second sample weights). Direct
inspection of the deployed source confirms the maintenance call at line 3203.
This runs on the socket's receive thread, so waiting for unrelated harvest
registry work prevents receiving player commands and processing turn timers.

The reproduction thread holds both the group and harvest locks around its
entire tick. In the same capture it has 306 samples waiting during transaction
exit, 41 decoding JSON and 30 waiting for a query. These stacks prove lock
ownership and the blocking receive-thread path. They do not independently
prove disk latency or a PostgreSQL server-side blocker.

## Narrow correction

`Harvests.due_availability` accepts optional `blocking=True`. Its default
retains existing behavior. Socket idle maintenance explicitly uses
`blocking=False`: if the lock is busy, it returns immediately and retries at
the next idle cycle.

A skipped poll does not inspect, remove, reset, or reschedule any cooldown.
The next successful drain emits each due availability update once. Actual
harvest begin, completion, and cancellation retain their authoritative
blocking synchronization. Rewards and combat logic are unchanged.

Two threaded regressions in `test_monster_availability_contention.py` verify
that a busy poll preserves its overdue record and later drains it exactly
once, and that request cancellation still blocks while preserving the pending
occupation until the lock is released. Catalog-enabled validation is delegated
to the test agent; host imports require the unavailable `psycopg` dependency.

The broader ecology lock-scope proposal remains separate. This patch removes
an unnecessary receive-thread dependency without weakening ecology's mutation
or publication fences.
