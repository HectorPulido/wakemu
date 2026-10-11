# Fight 187 latency audit — 2026-10-11

Read-only incident support during the active Monsters qualification matrix. No runtime source changes, tests, builds, restarts or catalogue operations were performed. Existing last 16 MB of World JSONL logs were scanned once and a bounded 19:52–19:54 UTC extract saved privately under `.runtime/local/diagnostics/ai-transport-fight187-20261011/bounded-events.json`. User local timezone is UTC−5.

## Findings

Fight187/map527 confirms expensive native **cast previews**, rather than HTTP waiting or complete-state source hashing, dominate AI stalls:

| UTC completion | Turn | Actor suffix | Preview wall / thread CPU | Slowest single preview | HTTP time | Outcome |
| --- | ---: | --- | ---: | ---: | ---: | --- |
| 19:52:58.821 | 4 | 3875 | 6,461 / 6,416 ms | 6,426 ms | 90 ms | Deadline fallback |
| 19:53:07.559 | 5 | 3872 | 4,288 / 4,242 ms | 4,090 ms | 330 ms | Move |
| 19:53:19.806 | 6 | 3873 | 9,742 / 9,553 ms | 9,451 ms | 256 ms | Deadline fallback |
| 19:53:32.508 | 7 | 3879 | 8,200 / 7,901 ms | 7,327 ms | 102 ms | Deadline fallback |

Turn6 had nine previews, seven failed; repertoire cost96 ms and source guards113 ms. Turn7 had five previews, all failed; repertoire43 ms and source guards65 ms. Near-equal thread CPU and wall for the dominant preview argues for computation in that thread, not prolonged network/SQL wait or pure CPU starvation. Host memory pressure may still aggravate the workload; these logs do not record GC or historical host-memory samples. Do not sum nested `preview:cast` with `preview_execution`, or duplicated fallback events before and after commit.

The first decision had cold exporter preparation608 ms, catalogue session1,195 ms and repertoire2,001 ms. Later decisions have warm repertoire costs generally36–153 ms, yet previews still stall for seconds. Consequently warming metadata alone does not solve all observed stalls.

## Player cast 4807

Request `c1ae7ec306fc44b2882be698f9e4286e` starts19:52:28.753952, finishes19:52:36.185, total7,432 ms. Its `prepare_ms` is7,403.919 ms; dispatch1.469 ms. First effect only appears19:52:35.156128: **6.402 seconds before the first effect log**. The next identical spell request `0b4ac72297b34e6092b13caf1c84958a` finishes in949.918 ms, prepare897.512 ms, dispatch30.177 ms. The first cast creates summon38; the next creates summon65.

Checkpoint pool0.228 ms, commit source validation9.531 ms, actor serialization approximately12 ms, revalidation7.590 ms and checkpoint enqueue6.286 ms cannot account for the initial6.4-second gap. `prepare_ms` is a broad scope: `local_game_server.py` wraps `COMBAT_SESSIONS.execute`; `combat_shared.execute` includes shared lock acquisition and deepcopy of fight/runtime; `prepare_server_spell` resolves casting and constructs `server_runtime`; `prepare_spell_transaction` captures source state, deepcopies again and runs `prepare_spell_cast` before effects. No logged subdivision proves which of these dominates the first call. Cold metadata, retained-graph deepcopy, and GC remain hypotheses, not established diagnoses.

## Native AI call path and safe next step

`NativeOracle._cast` resolves owned spells, descriptor and activation policy, selects `npc_runtime_catalog`, constructs a factory, then `npc_cast_condition`, native definition and `_validate_target` before `prepare_validated_npc_spell`. Failed previews can therefore consume substantial computation before raising `twE`/`twI`; skipping validation or reusing a stale failed result would weaken native authority.

Recommended minimal next investigation after the shared stability window: add wall/thread-CPU phase measurements around shared-lock admission, initial transaction copy, server-runtime construction, source snapshot, second copy, casting-rule/target preflight, and effect execution. Add the same phase evidence to native preview failure paths with spell/actor/target identity, preserving all checks. A sampled stack capture during the long individual preview would distinguish repeated metadata construction from graph copies or native criterion evaluation. No safe semantic optimization is established by these aggregate metrics alone.
