# Combat latency correction and server audit

The user explicitly authorized performance optimization after live combat stalled.
Beacon functionality is deferred at the user's request.

## Evidence and bounded changes

Continuous profiles captured recursive copies during shared turn expiry, timed
effect expiry and native AI forecasts. The shared expiry copy ran under the fight
lock even when no turn was due. A later feature summary measured an AI turn at
43.087 seconds and a turn acknowledgement at 43.230 seconds. These are measured
request durations; stack sample weights are not certified exclusive CPU time.

Three runtime files change the copying boundary:

- `combat_runtime_messages.py` retains six injected service callbacks by identity
  while copying owned mutable state with one memo. This prevents bound-method
  owners and their service graphs from becoming speculative combat state.
- `combat_shared.py` checks the existing expiration predicate under the same
  fight lock before copying. Due transitions retain their ordinary candidate,
  validation, acknowledgement and rollback paths.
- `combat_ordinary_authority.py` shares an internal immutable native property
  view. Public catalog callers still receive their original dict/list contract;
  custom mutable catalogs, characters and decks remain independently copied.

Synthetic callback-owner copies improved from median 241.804 ms to 0.0128 ms
with 20,000 definitions. The actor property asset improved from 6.973 ms to
0.147 ms. Neither benchmark establishes an end-to-end gameplay speedup.

Background locks were audited and retained: sampled waiting does not justify
removing atomicity. Startup point-area metadata already uses dictionary lookup;
no speculative indexing rewrite was made. The continuous profiler remains the
authority for measuring the deployed result.

## Verification and limitations

The initial clean targeted run passed 64 tests covering shared combat, idle
expiry, runtime messages, timed effects and the new copy/isolation regressions.
A wider 124-test run found existing QI, LOS and timeline fixture failures. A
separate temporary baseline with only these optimizations reversed reproduced
the three unrelated failures and representative authority errors. The one new
dict/list compatibility regression was corrected before deployment; final
verification passed 67 tests in 21.792 seconds. A lightweight native-oracle fork
probe also verified callback rebinding and mutable-state isolation.

The complete shared image `wakemu-world:performance-20261009-r59` is deployed
with digest `5720e6f2156f19976b5958070c923db62b951eb17c7ed826ec5da707d1a79f62`.
All 648 Python/protocol/migration files matched both the built image and the
running container. World restarted at 22:57:36 UTC, applied zero migrations,
opened both TLS listeners and returned a successful PostgreSQL health response.
The profiler was recreated against the new world PID namespace, finalized its
first new 60-second chunk successfully, and continued recording. Its 51-second
coverage gap is the explicit deployment restart, not an unexplained capture gap.
The previous r58 image is retained as `wakemu-world:backup-r58-before-performance`;
a completed private database dump and source manifest are retained under
`.runtime/local/backups/performance-audit-20261009/`. No database schema or
catalog release was changed by this correction.

Live post-deployment combat acceptance is pending. Do not claim the latency
problem completely resolved from health checks or synthetic benchmarks alone.

### Follow-up profile review

A post-restart summary covering approximately 2,899 seconds contains only one
new fight and four spell requests. Starting combat took 5,277.55 ms; Ready took
6,291.85 ms; one AI turn took 5,544.21 ms; the slowest spell took 2,230.88 ms.
This small sample does not reproduce the previous minute-long stall, but still
shows unacceptable multi-second paths. It does not establish a reliable p95 or
complete gameplay acceptance.

Monster reproduction accounts for 230.93 calling-thread CPU seconds over 1,953
iterations in that summary. It is the largest measured recurring CPU consumer;
growth accounts for 17.92 CPU seconds. These inclusive totals are not an
additive process budget. Recent reproduction stacks include SQL waits and JSON
decoding. The wrapper holds group and harvest locks across its database-backed
tick. Reducing repeated reads or lock duration requires preserving ecology
transactions, exclusion rules, leases and event publication; no locks have been
removed and no additional ecology optimization is claimed here.

The summary is preserved privately at
`.runtime/local/diagnostics/post-r59-review-20261009/performance-summary.json`.

Full-suite attempts were not successful: missing host dependencies/environment
prevented early collection, and a configured attempt was interrupted after a
large recursive copy exceeded five GB. Do not describe the complete suite as
passing. Raw test output and captures are private under `.runtime/local/`.

## Manual acceptance after deployment

Use two clients A and B in the same outdoor map.

1. A runs `!mob 1 10 1`, starts that encounter and presses Ready. Confirm the
   first turn becomes actionable without a long pause.
2. Move, cast an ordinary damaging spell, then end the turn. Repeat for three
   turns. Actions must complete during their turn; NPC turns must advance
   without minute-long gaps.
3. In a second encounter, let one controlled turn expire naturally. The next
   actor must receive the turn once, with no duplicated transition or lockup.
4. B joins as spectator after combat starts. Repeat ordinary movement/spells,
   then finish. Confirm both return to exploration and only A receives rewards.
   Beacon visibility and activation are excluded from this acceptance.
5. During a third encounter, run `!checkpoint`. Continue moving/casting and
   compare responsiveness. A zero-position receipt is not proof of a full save.

Record local time and the last action for any pause. Continuous captures require
no manual start command and retain the previous hour while enabled.
