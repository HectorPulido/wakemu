# Live slow combat: continuous sample evidence

Read-only investigation on 2026-10-09; timestamps below are UTC. No runtime code, gameplay, database, or service changes were made by this investigation. Raw captures, metadata and machine-readable stack counts were preserved under `.runtime/local/diagnostics/slow-combat-20261009/` before rolling retention removes them.

## Primary finding

Long recursive deep copies occur on live turn transitions. This is stronger evidence than attributing the incident to checkpoint or PostgreSQL merely from aggregate totals. Captures include idle threads: counts measure sampled stack occupancy, not certified thread CPU seconds. Deep-copy leaves indicate Python work; SSL receive, HTTP read and lock entry indicate waiting and must not be counted as CPU work.

| Capture UTC window | Session | Relevant sampled stacks |
| --- | --- | --- |
| 22:19:46.137–22:20:44.485 | 1729 | 823/1473 samples contain `expire_current_turn`; 825 contain `_deepcopy_method`; 817 have the identical recursive copying stack. |
| Same window | 1725 | 835/1473 contain `pending_transitions`; 807 have the identical psycopg `_maybe_prepare_gen:300` stack. A transaction/pool/native generator stall cannot be classified as CPU solely from this leaf. |
| 22:24:40.014–22:25:42.707 | 1725 | 458/1467 samples contain `_prepare_npc_turn`; 440 have leaf `deepcopy`; 431 have an identical copying stack during timed expiration. |

First path (`capture-1791584386136070067`):

`session → receive → idle:2893 → combat_session_adapter.expire_current_turn:587 → combat_shared.expire_current_turn:683 → deepcopy((shared.fight, shared.runtime)) → _deepcopy_method → recursive _reconstruct / _deepcopy_dict`.

The copy runs under the shared fight lock. In the checked source it occurs before checking whether the current actor is controlled, and the runtime expiration routine determines whether a deadline requires action only after the copy. `_deepcopy_method` proves a bound-method reference is traversed, but the exact callback owner and copied graph size still require object-level inspection. Do not claim that a particular catalog was copied without that evidence.

Second path (`capture-1791584680013536330`):

`session:6627 → pass_test_monster_turn → run_shared_npc_attempt → run_test_monster_turn → run_shared_turn → _prepare_npc_turn → native_turn.run_turn:183 → native_oracle.commit:877 → combat_native_action_ids.apply:94 → combat_area_boundary.apply:42 → runtime.end_server_turn:421 → _end_owned:183 → combat_timed_expiration.prepare_timed_expiration:92 → deepcopy`.

The later AI spike is predominantly deep-copy occupancy, not source fingerprinting: only one sample in that window contains `_source_hash`, one contains `fingerprint`, and four AI samples have HTTP `readinto` leaves. The earlier 22:19 window has 189 AI preparation samples, including 39 fingerprint samples and 34 identical HTTP response-wait samples; those secondary costs exist but do not explain away the copying spike.

## Limits and next diagnostic target

The 25 Hz nonblocking sampler includes all thread states and occasionally repeats identical stacks. Correlate exact start/end request timestamps and OS per-thread CPU deltas before assigning CPU seconds or proving GIL starvation. Inspect runtime-bound callbacks and timed-expiration candidate cloning, then establish a safe clone boundary that preserves fight rollback, runtime identity, acknowledgement state and spell semantics. No optimization was implemented here.
