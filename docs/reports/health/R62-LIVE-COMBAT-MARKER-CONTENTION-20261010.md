# R62 combat marker contention

## Evidence

Continuous captures from 2026-10-10 02:04 through 02:16 UTC show a different
profile from the earlier giant combat deepcopy traversal. The old deepcopy
path does not dominate these captures.

In `capture-1791598488935770486.speedscope.json` (02:14:48 UTC), the deployed
world source was inspected directly to map sampled line numbers:

- Session thread 223 has 53 samples at `publish_external_marker`, line 2337:
  acquisition of `COMBAT_GROUPS.lock`.
- Reproduction thread 166 has 566 samples at `monster_reproduction.attempt`
  exiting its PostgreSQL transaction, through `connection.wait`.
- That reproduction call holds both `COMBAT_GROUPS.lock` and `HARVESTS.lock`
  around the entire `tick` call (deployed lines 9259–9276).
- Resource growth, maturation, and wandering also show many samples waiting
  to acquire the same group lock.

Samples use 0.04-second weights. Waiting samples establish the Python call
and lock ownership, **not** PostgreSQL storage latency, database contention,
or CPU consumption. GIL scheduling and other execution delays remain possible.

AI preparation independently repeats source inventory scans. The 02:11:45
capture has 59 and 36 samples in `_inventory_scan -> register -> pathlib.stat`,
36 in inventory SQL waiting, and 41 in the decision HTTP response wait. The
02:15:51 capture has 48 decision HTTP wait samples, 19 catalog HTTP wait
samples, and seven instance-upload HTTP wait samples. The bridge work is
owned by a separate agent.

Placement-ready timing includes the synchronous first AI turn. Its observed
17.633-second maximum must not be assigned entirely to class initialization.
Initialization samples also show repeated baseline player spellbook decoding
through `OrdinaryActorAuthority.__call__`; any future cache must preserve live
morph and temporary spell-grant overlays.

## Narrow change

`publish_external_marker` now bypasses the group lock for placement and active
marker batches. These branches only enqueue already-owned actor and marker
packets; they do not inspect or mutate world groups. The actor descriptor
still precedes the marker in one batch. Participant and observer exclusions
are preserved.

Every finished-fight branch retains the existing group lock through its
durable defeated snapshot, corpse snapshot, and final publication. This also
preserves the fence for abandonment. No ecology mutation or database
durability change was made here.

`test_combat_marker_lock_scope.py` exercises the actual extracted callback:
placement and active delivery avoid the group fence, packet order and
exclusions remain intact, and terminal publication holds the fence. Local
validation: one test passed. Existing marker dispatch and withdrawal tests
are included in the broader catalog-enabled validation by the test agent.

## Deferred general lock-scope work

Do not simply drop the outer ecology locks or reuse an unfenced harvest
snapshot. A possible future design moves timer observation and enumeration
outside the whole-tick group fence, then reacquires group and harvest guards
for each authoritative birth attempt and each outbox publication. It must
refresh player and excluded-harvest facts under those guards and preserve
claim, defeat, revision, removal-before-spawn, and acknowledgment ordering.
This requires dedicated concurrency regressions. The proposal has not been
implemented; measure the narrow release before changing the ecology API.
