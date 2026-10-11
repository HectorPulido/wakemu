# Combat latency incident, 2026-10-10 18:25 America/Bogota

## Confirmed execution delays

World boot `568573d1b9f746db81b9f8cf3ef64ae4`, map 1134, fight 175.
Request `9de3132e9271440d9f43c9a650073fe2` began at 23:24:47.325 UTC and
finished at 23:25:10.781 UTC (23,456 ms). The `arena_selected` stage alone
used 23,278 ms wall time and 23,219 ms thread CPU. Subsequent resource
construction took 12 ms and durable placement took 85 ms. This establishes
a CPU-heavy fight terrain preparation or selection path. Subsequent
profiler inspection found one generation-2 garbage collection in this
boot, taking 22,857 ms wall and 22,833 ms thread CPU. This accounts for
almost all of the delay; the aggregate GC record does not retain the
original request timestamp. An isolated fresh-process measurement of
the same map took 477 ms for arena selection and 1,282 ms for QI surface
construction under cProfile. These results do not justify changing the
arena selection algorithm to address this incident.

Turn acknowledgement requests also took 4.7–7.2 seconds. Request
`467e2b26aa734ea78377e76981d4c9af` completed at 23:27:13.971 UTC after
7,160 ms. Its four sequential tactical decisions were move, move, cast,
and end turn. Approximately 5,244 ms were native search waits and 941 ms
were context preparation. The repeated preview effects are not evidence
of repeated authoritative damage application.

## Independent ecology delivery defect

The ecology worker reached its 256-proposal pending limit. The world mob
handler returned benign compare-and-set rejection statuses (`absent`,
`stale_group`, and related statuses), while the delivery bridge accepted
only its transport vocabulary. It converted these rejections into
`ValueError` and retried indefinitely. PostgreSQL sampling found no
ungranted locks or active blocking transaction. A causal connection to
the fight entry delay has not been established.

The bridge now normalizes lost live-world conditions to terminal `stale`,
logs the original rejection status, and retains retry behavior for actual
errors and unknown statuses. No proposals were cleared manually. Bridge
and transport verification: 34 tests passed initially. The follow-up retry
limit and bridge suite passed 43 tests against an isolated database.

Delivery now allows five attempts by default, configured through
`WAKFU_ECOLOGY_MAX_ATTEMPTS` (1–100). HTTP failures count too. Exhausted
proposals are archived with `last_error_code=retry_exhausted`, freeing
pending capacity without claiming successful application. Historical rows
already above the limit are retired before the queue capacity check. The
same proposal is not resurrected in the same world epoch. Existing archive
retention is seven days or 4,096 completed entries, whichever bound trims
the row first.

At 19:22 local time the deployed worker reported healthy, max_attempts=5,
pending=0 and no domain errors. The previous world restart's terminal
stale handling had already drained the old 256 rows, so the live archive
had zero retry_exhausted rows; isolated SQL tests verify exhaustion itself.
The planting attempt received at 18:57:35 had been enqueued in 81.5 ms but
never planned while capacity was saturated. Its session intent was
cancelled on reconnect; manual acceptance must make a fresh planting.

## Observability

The external profiler was absent from the current Compose stack and was
reattached to the running world PID namespace without restarting world.
It is healthy, records continuously, and retains up to one hour under a
1 GiB cap. Its new capture coverage begins after the original incident;
request-stage logs, rather than a retrospective sampled stack, establish
the timings above.

World completed the early static-heap bootstrap and is healthy. Its
startup reported 23,747,997 frozen objects with cyclic GC still enabled;
747 current shared Python/migration/entrypoint hashes matched the running
image. No arena selection rules were changed. Six arena phase timings
are now recorded, with diagnostics isolated from gameplay failures.
Five bootstrap subprocess tests, including the exotic-type regression, verify
the startup boundary; future game cycles remain collectible. Full
catalogue smoke validation succeeded separately before accepting readiness.
Fresh gameplay acceptance remains pending, and AI search latency is still
open as described below.

Final deployment checks after the shared full-checkout restart: world,
ecology and the continuous profiler respond healthy; pending ecology is
zero and the configured maximum is five. The profiler process selector
now recognizes the exact `-m wakfu_server.catalog_gc_bootstrap` invocation
as well as the original direct script. Its 22 tests passed; this prevents
the startup change from silently removing continuous stack coverage.
The latest startup freeze completed in 99,623 ms before listeners opened.

## Manual acceptance

1. Reconnect and run `!item 1752 10`. Outside combat, plant a wheat seed on
   a valid nearby cell. The action should begin without a queue stall,
   complete or report its normal failure, and preserve correct inventory
   consumption. A biological planting failure is distinct from a request
   remaining indefinitely pending.
2. Plant again and move before completion. The action must cancel without
   creating a resource or consuming a seed for an uncommitted planting.
3. Run `!monster 2 4 1` in a valid outdoor combat area and attack the new
   group. Placement should appear without the previous 23-second pause;
   move during placement, ready, cast, and finish or surrender. Observe
   actor/marker cleanup and reconnect to confirm inventory persistence.
   Remaining AI search pauses of 4–7 seconds are a known separate issue,
   not an accepted claim of instant turns.

Baseline automated validation passed 109 tests covering arena selection,
borders, placement, movement, spectators, tactical AI, and duels. Private
evidence: `.runtime/local/diagnostics/incident1825-performance.json` and
`.runtime/local/diagnostics/incident1825-arena-combat-baseline.log`.


## Residual AI computation after the GC incident

The combat 175 request at 23:27 UTC also has a separately measured 7159.904 ms ACK containing four sequential decisions (move, move, cast, end turn). Search stages total 6417.780 ms; native commits total only 177.154 ms. Native preview wrapper metrics are inclusive of execution and some transport publication, so they must not be summed with nested execution/HTTP totals. Approximately 4–7 seconds of AI computation can remain after the GC fix; this is not claimed solved. Exact metrics, preserved evidence and the reason raw forecast-plan reuse is unsafe are in [Combat 175 turn ACK latency](COMBAT175-TURNACK-LATENCY-20261010.md). No tactical or search-budget change was made in this audit.
