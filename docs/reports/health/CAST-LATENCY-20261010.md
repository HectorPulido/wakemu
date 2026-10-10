# Residual player spell latency, 2026-10-10

Evidence retained in `.runtime/local/diagnostics/cast-latency-20261010/`. Read-only investigation; no runtime changes or restarts.

## Two comparable casts

| UTC completion | Request | Total wall | Root effect 326384 | Child 326970 / family 400 | Child 326971 / family 304 |
| --- | --- | --- | --- | --- | --- |
| 07:11:10 | accb84c2d852444aac6c7caa2c20ce14 | approximately 4,509 ms | 3,914.597 ms | 1,983.333 ms | 657.036 ms |
| 07:33:38.563 | eb137bee312a42e182e530f742920a9b | 5,002.048 ms | 4,195.496 ms | 2,082.819 ms | 704.416 ms |

Both casts spend most of the measured interval executing the same nested effect subtree: 326384 → 326388 → 328349. Effect timings are inclusive and overlap; never sum them. The later cast has 219 effect trace events. This is residual synchronous effect execution beyond catalog parsing alone.

For the later cast, source validation, actor serialization and source revalidation total approximately 34 ms. Checkpoint queue preparation takes 7.794 ms. All 166 request-associated outgoing packets are logged between 07:33:38.503476 and 07:33:38.505883, a 2.407 ms window, after almost all computation. No evidence of a long send backlog in this request. Log timestamps are send invocation evidence, not proof of client display/animation completion. Client-click-to-request queueing before `request_started` is unmeasured.

## Samples and limits

Continuous profiler artifacts have a coverage gap from approximately 07:28 to 07:43 UTC; consequently the 07:33 cast cannot be assigned an exact CPU hotspot from stacks. Do not reuse another cast's samples as if they measured this request.

The persisted 07:10:42 capture `capture-1791616242705288963` includes 91 shared-cast samples; 75 traverse ordered child-group effect execution. Largest repeated identical stack (8 samples) traverses native LOS → topology_columns → catalog load → JSON decode; parser caching addresses that component. Other samples are distributed across conditions/properties, registered summon counts, owned spell records, available spells and retained condition effects. These provide investigation targets rather than certified percentages for the later cast.

Per-effect events provide wall timings only; no request-specific thread CPU metric is available in these logs. Continue measuring authority-view/replay setup and condition resolution around the expensive child effects, preserving effect order and state semantics. A cache of parsed catalogs alone cannot remove the measured 4.2-second execution tree.

## Common engine improvements prepared

1. `NativeRetainedRuntime.synchronize` computes a fresh operation-local set of state-container users in one scan of owned stat/group/area children. Previously each container independently scanned all children. Deletion/reparenting is observed on the next call; no mutable fight state is cached. Unhashable malformed state IDs keep legacy equality fallback. Synthetic 1000-child/300-container repeated pruning improved 253.7x for this isolated scan; live total-cast gain is unmeasured.
2. `evaluate_condition` privately caches only parsed criterion ASTs: at most 512 entries, each at most 2048 characters and 256 AST nodes. Large trees bypass caching; invalid syntax is not retained. Public parser calls still return fresh mutable trees. Every evaluation revalidates and reads the current context, so HP, states, decks, summons and ownership cannot use stale outcomes. A 10,000-parse benchmark improved from 0.4010s to 0.0047s; this is parsing-only, not whole-cast latency.

Six focused regressions pass, including changed context, external AST mutation isolation, cache bounds, all three owned collections and next-call liveness updates. The broader retained synchronization core passes 33/33. Broad authority-heavy suites contain existing missing-authority/catalog fixture failures; an uncached-parser baseline reproduces the same 1 failure and 8 errors in the four affected authority modules. Two additional deck catalogue count expectations are unrelated to criterion evaluation. Concurrent dungeon coverage passes 103/103. Complete r70 image matches 692 current server source/migration files.

Manual acceptance after release: start a fresh fight, launch the same spells repeatedly, apply/remove a state between casts, summon/dismiss and attack again; verify current costs, damage, target eligibility and effects. Repeat with a spectator and record the exact local time for any delay. Do not equate isolated benchmark gains with an eliminated 5-second live cast until this replay is captured.

Deployment verified at 03:10 local: single world uses `wakemu-world:performance-20261010-r70`; all 692 image source/migration hashes matched the shared checkout before restart. Health OK, deployed condition/retention implementation hashes checked, continuous profiler reattached after world became healthy. Live total-cast improvement is pending acceptance.
