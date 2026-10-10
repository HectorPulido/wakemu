# AI service performance audit — 2026-10-10

## Scope and method

Audit covers the embedded world-side AI SDK as well as the separate HTTP planner: catalogue inventory, complete context and graph serialization, integrity guards, repertoire metadata, action search, native previews, transport, deadline propagation, receiver validation, memory lifetime and concurrency. Evidence combines continuous sampled stacks, request wall/thread-CPU metrics, isolated catalogue-backed benchmarks and regression tests. Inclusive spans must not be summed; duplicate decision telemetry is deduplicated.

## Confirmed live bottlenecks

| Incident (local) | Confirmed cost | Correction / status |
| --- | --- | --- |
| 01:20 | Inventory scan 45.81 s wall | Component-equivalent path sort replaces expensive Path ordering; fresh enumeration and content verification retained. This does not prove every scan is cheap. |
| 01:54 | Integrity source guard 26.29 s CPU | Actual dictionary storage inspected without invoking lazy catalogue views; complete fields, identity and mutation coverage retained. Deployed r68. |
| 01:54 | Player spell ~8.87 s wall, repeated effect identity parsing | Bounded immutable parser-result cache, fresh caller dictionaries and unchanged validation. Deployed r68; synthetic 4.96x parser improvement is not whole-spell latency evidence. |
| 02:10 | Repertoire query 15.55 s CPU; source guards only 7.27 ms CPU | Per-visit cooperative checks now include primitives/aliases; byte graph transport avoids duplicate graph/JSON traversal. Exact cause of exceptional CPU pause remains under investigation. |

The 02:10 casting metadata is not intrinsically huge: actual three-spell repertoire encoded to 155,966 bytes in 7–12 ms in an isolated warm benchmark. A separate larger-record reproduction measured a 629 ms generation-1 GC pause while collecting no objects. This confirms GC can pause this path, but **does not establish that GC caused the live 15-second stall**. Live GC telemetry is being added before selecting a collector-policy optimization.

## General deadline holes found

Checks tied only to new graph-node count missed arbitrarily long scalar and memo-reference sequences. Encoder traversal, NativeGraph reference validation/projection and geometry partition unpack/remap traversal now account for actual work. Timeouts reject partial results through the existing end-turn safety path; no authority or metadata is truncated. Full C-level JSON/compression/deepcopy calls remain cooperative-deadline limitations and must be measured before further changes.

## Preservation criteria

Keep complete authority, aliases/cycles, canonical graph ordering, mutation certification, malformed-payload validation, fresh runtime ownership checks and player resources. Do not reduce spell definitions, skip hash verification or cache mutable fight views to obtain a faster benchmark. Every deployment uses the complete current shared checkout and one world container.

## Detailed evidence

- [02:10 live incident](LIVE-SLOW-COMBAT-20261010-0710.md)
- [01:54 live incident](LIVE-SLOW-COMBAT-20261010-0654.md)
- [Inventory sort](AI-INVENTORY-PATH-SORT-20261010.md)
- [Integrity guard](AI-SOURCE-GUARD-DEADLINE-20261010.md)

## Manual acceptance

1. Start a new fight, ready, cast several spells and record any delay with exact local time.
2. Allow at least three NPC turns, including the first cold turn; verify attacks and end-turn progress.
3. Join with a spectator before and after a summon; verify movement, spells and turn progress.
4. Repeat another fight immediately to compare cold/warm behavior.
5. If stalled, leave continuous capture active; correlate request, native-query, GC and sampled stacks before restarting.

Passing unit tests establish behavioral invariants, not a claim that every production lag has been eliminated.

## Prioritized remaining work

1. Measure live GC pauses before changing collector policy. New bounded generation-specific telemetry queues callback facts without acquiring profiler locks; monitor export records wall and thread CPU.
2. Reduce repeated complete snapshots and preview publication after measuring duplicate rates; dedup currently happens after some expensive work. Any cache must preserve ownership/revision semantics.
3. Separate/attribute search compute allowance from owner wall deadline. The planner's local allowance excludes native-query waiting; the owner deadline is the actual turn bound.
4. Measure whole JSON/gzip/decompression and receiver-side sealing before redesigning transport. Frame size is not a total decoded-memory or disk-retention bound.
5. Bound byte retention as well as entry counts where memory can grow with a few large contexts. Preserve checksum verification and full authority.

Detailed audits: [search](AI-SEARCH-AUDIT-20261010.md), [transport](AI-TRANSPORT-AUDIT-20261010.md), [deadline regression coverage](AI-NATIVE-GRAPH-DEADLINES-20261010.md).

Validation: 130 focused AI/context/monitor tests pass with no skips. Complete r69 image matches 690 current server files. Additional shared-checkout validation initially had three reward-policy fixture failures. After concurrent fixture corrections, the complete reward-policy module passes 20/20; the other 27 tests passed in the original run. No unresolved failure remains in these targeted suites; this is not a claim that the whole repository suite passes. Complete r69 deployment started at 02:42 local.

Deployment verified: r69 started at 02:42 local; world health OK and continuous profiler running with 3600-second retention and no current error. Complete image manifest matched all 690 server source/migration files. Live acceptance and attribution of the exceptional cold-turn pause remain open.
