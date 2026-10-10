# Maps, geometry, dungeons and ecology performance audit — 2026-10-10

Scope: current shared checkout, with incident captures from the running world before r73. This is an evidence-ranked audit, not a claim that every map or workload has been benchmarked. No gameplay optimization or deployment was performed for this audit.

## Findings ranked by evidence and impact

| Priority | Finding | Evidence | Status / next action |
| --- | --- | --- | --- |
| P0 | Fight entry blocked 26.228 s; 24.909 s arena stage, 24.728 s thread CPU concentrated in native QI surface construction | Exact request and continuous sampled stack capture, described below | Unresolved process-state anomaly; preserve GC evidence before choosing a policy change |
| P1 | Plant growth still holds the global combat-group registry lock across SQL, complete candidate processing and publication | Current source, `local_game_server.py:10414`, `planting_runtime.py:185` | Confirmed lock scope; contention impact not separately measured in this incident. Instrument wait/held durations, then narrow fences around authoritative operations |
| P1 | Monster command formerly rebuilt full-map adjacency on each request | 9.291 s exact request; 189/198 sampled stacks in map reconstruction | Fixed using published immutable geometry; already delivered independently |
| P2 | Dungeon room preparation repeatedly reconstructs full-map cell membership and filters every edge inside caller transaction | `dungeon_runtime.ensure_current_room`, lines 53–89 | Source-confirmed repeated work, unmeasured hot-path cost. Cache immutable section geometry by pinned topology/catalog identity if profiling justifies it |
| P2 | Room position lookup rebuilds every room's cell set; strict-native fallback scans complete transport catalog | `dungeon_runtime.room_for_position`, lines 99 onward | Source-confirmed work, no measured user-visible stall attribution. Prepared position-to-room index is a candidate |
| P2 | Reproduction builds its own full-map edge index for each newly active map, beside the existing published geometry index | `local_game_server.reproduce_monsters`, lines 10475 onward | Outside registry fences; repeats after map becomes inactive. Reuse immutable published adjacency after checking consumer representation compatibility |
| P3 | Teleport console reconstructs a full-map membership set for each command | `maps/test_console.py:163` | Low-frequency administrative path. Published geometry membership can replace it with targeted regression coverage |
| P3 | Reproduction checks dungeon membership independently for current and previous locations | `monster_reproduction.tick`, lines 436–443 | SQL calls scale with active locations, with overlap repeated; not identified as current primary bottleneck |

## Native surface anomaly: what is proven

On map 527, request `726397447e734e6480632f7bfe174e42` started at 16:36:44.172 UTC and completed at 16:37:10.400 UTC. Capture `capture-1791650174925162271` contains 611 local-arena samples: 585 under native QI loading, 582 at the surface constructor, including 579 top samples at the surface interning lookup. Arena selection/BFS accounts for only 15 samples. The loop is linear in the number of published surfaces; there is no evidence of quadratic arena search here.

The published map is 3,384,935 bytes with 521 chunks, 168,804 columns and 174,052 surfaces. An independent fresh Python process inside the same image built that exact provider in 0.673 s wall / 0.641 s CPU. Consequently, simply removing validation or rewriting the linear dictionary loop is not justified as the solution to the 25-second live stall.

The provider already uses an eight-map LRU. Published geometry already uses a sixteen-map revision-keyed immutable cache. Native catalog readers pin one published release per process (`storage/native_catalog.py`); absence of a revision argument in the QI LRU does not itself imply cross-release mixing. Catalog changes require the established process/image lifecycle. Cache eviction rate and retained heap size need measurement before increasing cache limits; more cached Python objects may worsen memory/collection pressure.

Available GC aggregates before restart contained generation-0/1 maxima below 100 ms and no completed generation-2 record. Two callback samples near construction are insufficient to attribute this stall to GC. A separate minimal diagnostic change preserves the longest completed pause for each generation even if the bounded queue overflows. It changes no collection threshold, scheduling, or gameplay behavior. See [the incident report](START-FIGHT-LATENCY-20261010-1136.md).

## Ecology fences and safe optimization boundaries

Reproduction and maturation now acquire coordination fences per observe, attempt and publish operation rather than around a complete zone cycle. These fences still include authoritative SQL and publication. Their existing guard-wait/guard-held spans should distinguish lock convoying from actual reproduction work. Do not remove claim/harvest exclusion or receipt/outbox revision checks to improve a timer.

Plant growth is different: one outer `COMBAT_GROUPS.lock` covers `PLANTINGS.mature`, including mineral refill, due-resource queries, flora transitions, monster activation, delivery and acknowledgement. Its publication callback additionally loads a complete character for ecology and emits world packets. The caller's player/group snapshot must remain authoritative for spawn occupancy when narrowing this fence; moving SQL outside the lock without revalidation can spawn over players or conflict with combat claims. Durable growth outbox replay and exactly-once ecology receipts must remain intact.

Historic profiler totals for ecology contain large waits and overlapping inclusive spans. They must not be added together as CPU demand. The 11:36 entry incident is predominantly measured CPU, while a blocked registry acquisition is a separate mechanism. Current evidence does not justify attributing all pauses to either one.

## Dungeons and geometry correctness constraints

Dungeon configuration is pinned to a durable run and catalog hash. A prepared room index must use that identity, not merely asset map ID. Keep native cell and directed-edge validation, room roster ordering, entry/re-entry progression, first-matching QI chunk semantics, signed surface ranges and provenance checks. Dynamic player/group/harvest occupancy cannot be cached as terrain.

Automatic room advance/exit deliberately lock party members and durable run state and create transition outbox records atomically. Per-member writes are bounded by party size. No trace reviewed here establishes those transactions as the 25-second CPU culprit. The session transition poll already has a one-second idle throttle; its inclusive aggregate alone cannot establish an optimization target.

## Verification and next measurement

Use separate warm/cold entry timings on ordinary PvE, large duel and dungeon room geometry. Record geometry/surface cache hits and construction durations, GC generation/max pauses, registry wait/held durations, SQL durations and packet-delivery times with one shared request identity. Reproduce with a long-running heap, not only a clean interpreter. Do not run deliberate heap-pressure stress in the live user process.

Acceptance after any relevant change: start a distant PvE fight, relocate during placement, move/cast with both owners, join as a spectator before and after a summon, finish and surrender; verify both clients return with no duplicate objects. In a dungeon, enter room one, clear and advance, re-enter at durable current room, then finish and exit with the full party. Plant flora and a monster resource while another account enters combat; confirm no overlap, duplicate growth, missed ecology update or blocked input. Each implementation change needs targeted automatic regression tests before deployment.

Private evidence remains under `.runtime/local/diagnostics/start-fight-1136/` and `.runtime/local/diagnostics/command-lag-1021/`; captures and credentials are not publication artifacts.

Validation of the separate GC observability change: the delegated test run of `test_gc_pause_monitor` and `test_performance_profiler` passed **11/11**, including long-generation-pause retention after short-collection queue overflow and no duplicate drain. This audit itself changed documentation only. Static review covered surface catalog/constructor and prepared geometry, compact arena call sites, dungeon runtime room lookup/preparation, automatic transition/exit transaction boundaries, ecology reproduction/maturation coordination and planted-resource maturation/publication. It is not exhaustive path coverage of every map module or a fresh load benchmark.
