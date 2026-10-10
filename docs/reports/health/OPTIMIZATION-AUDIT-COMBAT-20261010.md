# Combat and session optimization audit, 2026-10-10

Scope: authoritative combat transitions, effect transactions, packet delivery, session synchronization, and their entry points in `local_game_server.py`. AI search/transport, maps, and storage internals belong to separate audit owners. This is a read-only audit; no behavior change or deployment is included.

## Ranked findings

| Priority | Finding | Evidence | Proposed next step | Risk |
| --- | --- | --- | --- | --- |
| P0 correctness | Turn-counter and dead-current ACK mistakes resemble severe performance stalls | Captured controlled-summon end-turn requests waited approximately 30 seconds after rejection; death presentation was acknowledged promptly while subsequent combat stopped | Complete native global-round validation and dead-current ACK regression coverage before measuring throughput | High if protocol semantics are replaced with guessed counters or timeout shortcuts |
| P1 | Shared casts copy the entire fight twice and flatten it three times | `Registry.execute` clones `(fight, runtime)`; `prepare_spell_transaction` records a complete source snapshot and clones the candidate again; `commit_spell_transaction` creates two more source snapshots | Instrument copy and snapshot stages separately, then introduce an explicitly detached-candidate transaction path only if rollback and callback-mutation guarantees remain equivalent | High: failures must never leak AP, HP, RNG, retained effects, events, or packets |
| P1 | Cumulative event history makes these copies and snapshots progressively more expensive | `Fight._event` appends to `fight.events`; it is part of `fight.__dict__`, so all copies and `source_snapshot` traverse it. No general truncation was found in these critical paths | Measure real event counts and history bytes by fight age. Consider an immutable history prefix plus private append segment, preserving complete durable history and existing event indexing | High: arbitrary truncation breaks checkpoints, event consumers, transaction offsets, and replay evidence |
| P1 | Expensive callback work runs while holding the per-fight transition lock | `Registry.execute`, `execute_server`, `acknowledge`, and expiry clone and execute inside `shared.lock` | First measure lock wait, clone, callback, and commit separately. Keep one serialized owner per fight; consider immutable input plus generation-checked detached preparation only after concurrency proofs | High: speculative unlocked work can reorder spells or commit stale decisions |
| P2 | Every successful spell serializes every actor's full stat packet | `commit_spell_transaction` calls `stats_serializer` for every actor and emits 12873 regardless of which actor changed | Measure bytes and serializer time by actor count. Investigate protocol-safe unchanged-presentation suppression or immutable serialization fragments, with summon birth/reconnect/retained changes tested | Medium/high: equal visible HP does not mean native state is unchanged |
| P2 | A slow socket can delay other recipients of the same fight | `dispatch_connected` releases fight/registry locks before I/O, but holds a per-fight dispatch lock and sends recipients sequentially. `Connection.sendall` holds a per-connection write lock across synchronous socket send | Measure send-lock and send spans by recipient. Only if observed, introduce bounded ordered per-connection writers with explicit disconnect/backpressure semantics | Medium/high: parallel unordered sends corrupt action ordering and ACK barriers |
| P2 | Global registry operations can retain the registry lock while doing fight work | Placement join holds registry then fight locks while cloning, initializing newcomers, serializing bootstrap, and optionally persisting membership | Add lock-duration spans; move only immutable preparation outside admission locks with final generation/sequence checks | High: actor reservation and alias resolution must stay atomic |
| P3 | Rift accepted-action persistence has a synchronous exception path | `_prepare_accepted` calls the rift provider under the fight lock; `checkpoint_fight` uses synchronous `CHECKPOINTS.save/end` under the shared lock for rifts, unlike normal queued checkpoints | Storage audit should measure this path separately and preserve accepted-wave durability requirements | High: simply queueing these writes could publish an undurable wave |

## Small synthetic measurement

Command: private performance-test Python with `PYTHONPATH=server`, importing `Fight`, `Actor`, `freeze_terrain`, and `source_snapshot`. A two-actor 7 by 7 fight was given 0, 1,000, or 10,000 synthetic event dictionaries. Each operation was repeated five times and mean wall time measured with `perf_counter`.

| Synthetic history length | `deepcopy(fight)` | `source_snapshot(fight)` |
| --- | --- | --- |
| 0 | 0.212 ms | 0.575 ms |
| 1,000 | 4.321 ms | 7.013 ms |
| 10,000 | 42.430 ms | 64.852 ms |

This demonstrates history-dependent linear work, not live fight latency. At 10,000 synthetic events, the shared-cast structure alone implies roughly two copies plus three snapshots, around 279 ms in this simplified case before effect execution or serialization. Real state shape and runtime graph differ; the estimate must not be advertised as measured production overhead or a guaranteed optimization gain.

## Existing safeguards and completed optimizations to preserve

- Terrain is already wrapped in `ImmutableTerrainSet` with identity-preserving deepcopy; do not reintroduce copying or sorting every terrain cell during previews.
- Source snapshots intentionally exclude only `native_rail_movement_authority`; removing additional fields to speed comparisons would silently weaken stale-source detection.
- Native retained-container synchronization now builds a fresh operation-local user set; live fight state is not cached across actions.
- Condition parse trees and native binary identity parsing have bounded immutable-fact caches. Evaluation results, resources, targets, and actor state remain fresh.
- `send_batch` joins ordered frames and acquires the connection writer once per batch. Normal shared delivery does not hold the fight or registry lock during socket I/O.
- Socket timeout is configured to one second; the sequential-recipient finding is bounded socket/backpressure exposure, not proof of an unbounded network stall.
- Normal fight checkpoints use a background writer after publishing accepted packets. Queued persistence does not eliminate the cost of constructing the immutable checkpoint snapshot.
- Effect recursion is explicitly bounded. Replacing native child traversal or pruning apparently duplicate effects requires semantic evidence, since repeated applications can be intentional.

## Validation required before any structural change

Use isolated database schemas and Luna regression tests. Cover a cast rejected after partial effect execution, serializer callback mutation, RNG rollback, state removal/reparenting, summon creation/death, controlled-summon end turn, delayed/duplicate ACKs, two owners plus an observer, reconnect, and terminal settlement. Test long event histories as well as fresh fights. Compare exact packet ordering and authoritative state, not merely final damage.

The highest-confidence performance next step is attribution: separate `shared clone`, `transaction source snapshot`, `transaction clone`, `effect execution`, `source revalidation`, `actor serialization`, `dispatch-lock wait`, and `socket send`. Current broad cast timing merges several of these. No risky transaction or synchronization rewrite was made during this audit.
