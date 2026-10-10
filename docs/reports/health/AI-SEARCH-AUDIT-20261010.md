# AI search and native query performance audit

Date: 2026-10-10. Scope: native AI planning, owner-thread queries, runtime previews, identity checks, metadata publication, and cooperative deadlines. This audit did not restart services or modify gameplay code.

## Confirmed incident at 02:10 local

The unique failed decision for fight 150, turn 1, actor -1125899906844032 completed at 07:10:53 UTC. Its request ID was `19a59e68f7a5419ab31abd0db77055f6`. Two tactical-action records describe the same decision before and after fallback commit; they must not be summed as independent turns.

| Measurement | Wall time | Thread CPU | Interpretation |
| --- | ---: | ---: | --- |
| Entire decision before fallback | 16,416 ms | Not separately recorded | Exceeded the 10,000 ms owner budget |
| Search | 15,821 ms | Not separately recorded | Inclusive of world query work |
| Repertoire query | 15,703 ms | 15,548 ms | One failed query; principal measured bottleneck |
| Casting prerequisites | 1,068 ms | 932 ms | Included in repertoire, not additional |
| Source guards, 3 calls | 7.8 ms | 7.3 ms | Previous source-hash stall was not repeated here |
| Catalogue/session initialization | 504 ms | Not separately recorded | Included 436 ms catalogue transfer stage |
| Exporter inventory | 167 ms | Not separately recorded | Included in session preparation |
| HTTP requests, 7 | 357 ms | Not separately recorded | Cannot explain 15 seconds of CPU |

At 07:12:05 UTC the same monster's next recorded decision in fight 150 took 848 ms, with repertoire 10.5 ms and prerequisites 0.21 ms. Fight 151 subsequently took 545 ms for movement, then completed end-turn within 933 ms cumulative turn time. This is a strong cold/warm difference, not evidence of uniformly expensive tactical branching.

Raw evidence: `.runtime/local/logs/game-server.jsonl`, event `combat_monster_tactical_action`. See also `LIVE-SLOW-COMBAT-20261010-0710.md` for profiler samples and incident reconstruction.

## Prioritized findings

### P0: repertoire preparation can overrun a cooperative deadline

Location: `server/ai-service/wakfu_ai/bridge/world_bridge.py`, `_query_unmeasured`, repertoire branch around lines 1310–1387; `native/native_turn.py` around lines 145–210; `native/native_deadline.py`.

The owner thread constructs native casting/class metadata, evaluates prerequisites, and encodes the complete metadata graph before returning the query. The failed call consumed 15.55 seconds of thread CPU despite a 10-second owner budget. No preview was completed in that decision. Range-envelope computation was skipped because native prerequisite evidence marked all owned spells unavailable.

Cooperative checks cannot interrupt an individual Python garbage collection or another indivisible operation. A deadline check before and after that operation protects future work but does not bound the operation itself. Reducing search nodes would therefore not resolve this incident.

An isolated read-only benchmark loaded actual catalogues and encoded metadata for spells 5773, 5776, and 5777 at level 14. Six `encode_bytes` calls took **11.74, 7.42, 8.25, 7.50, 7.31, 7.97 ms**, yielding **155,966 bytes**. GC callbacks recorded no collection during these six calls. Loading the casting and effect-tree catalogues beforehand took 3,277 ms, including PostgreSQL transfer and decoding of 34,394,282 and 57,514,368 bytes respectively. This benchmark used a separate local Python process and read-only production catalogue reads; it did not mutate the world or run a second server.

Conclusion: the metadata's inherent traversal size does not reproduce the live 15-second stall. Allocation-triggered GC is a plausible explanation, but remains unproven without collection timing from the affected process. The root task is adding bounded GC pause telemetry to distinguish this from other CPU work. Do not claim GC is the established cause yet, disable GC globally, or truncate metadata fields as a workaround.

### P1: complete preparation is repeated for each committed action

Location: `native/native_turn.py` around lines 145–157; `bridge/world_bridge.py`, `NativeSession.__init__`, around lines 930–970.

Each selected action starts a new native session, refreshes the source hash, registers the complete runtime graph, and obtains a new root identity. Catalogue transfer is already reused within the turn through `catalog_manifest`; it must not be counted as a full retransmission on every action. However, runtime encoding remains fresh, correctly reflecting the previous committed action.

Observed warm decisions still spend roughly 53–55 ms encoding a root graph, 12–16 ms publishing it, and 3–5 ms on identity. This is measurable fixed overhead before tactical previews. The correct optimization opportunity is verified immutable graph partitioning and reuse, not caching mutable state by fight ID. Existing opt-in native graph parts and immutable terrain fragments already provide the appropriate design direction.

### P1: preview cost multiplies full cloning, publication, and validation

Location: `native/native_oracle.py`, `fork` around line 215 and `preview` around line 730; `bridge/world_bridge.py`, preview branch around lines 1260–1305; `planning/query_search.py` around lines 1045–1048.

Every candidate preview forks the complete runtime, executes authoritative gameplay, then registers and describes the resulting state. Search rejects previously visited state identities **after** this publication. Distinct paths can therefore pay the full cost before deduplication. Default own-search limits are depth 4, beam 12, and 96 probes. A warm movement preview in fight 150 took 110 ms maximum inclusive query time; native execution alone peaked at 46 ms. Publication and description are meaningful costs alongside gameplay execution.

Safe next steps: record separate fork/encoding/publication/description timings per preview, and evaluate session-local reuse only for an exact immutable source state, normalized action, flags, and deterministic forecast seed. The cache must preserve transition evidence and every native field. Do not reuse outcomes across changed source authority, actual live randomness, or commits. Do not replace authoritative previews with heuristic legality tests.

### P2: source guards multiply with native queries, but currently remain small

Location: `bridge/world_bridge.py`, `query` around lines 1202–1225 and `guard` around line 982.

Each normal query performs a source guard before and after execution, plus the turn's final guard before commit. Failed supported queries also run an after-query guard. Fight 150's warm decision recorded 13 guards, totaling 39 ms; fight 151's movement decision recorded 10 guards, totaling 31 ms. This is a linear per-query cost, but it is not the current 15-second bottleneck.

Preserve source integrity. Only a proven immutable catalogue/terrain fragment can reuse a verified digest; mutable runtime and authority changes must remain detectable. The previous lazy dictionary traversal fix is supported by current low guard timings.

### P2: tactical work budget is not a wall-clock promise

Location: `planning/query_search.py` around lines 737, 850–912, 1015–1047, and 1177–1187.

Default `budgetMs=250` counts planner exploration work while native query waits and geometry preparation extend that work deadline. Separate decision-wall and owner-turn budgets constrain total work, with a commit reserve. This distinction is intentional, but reporting only “250 ms search budget” would mislead users. First-root-action guarantees can also permit an initial certified movement attempt after mandatory preparation consumed the decision slice; the absolute owner budget remains the safety boundary.

Keep wall, planner work, owner-native query, and geometry-preparation metrics separate. Retain existing first-action guarantees so slow mandatory metadata does not cause AI to skip otherwise legal turns.

### P2: rival forecasting scales by alternatives and rival count

Location: `planning/query_search.py` around lines 1120–1208; `planning/query_threat.py`, `forecast` around lines 20–150.

Defaults allow six alternatives, each considering every surviving rival with up to 12 nodes, depth 2, and beam 4. This is potentially multiplicative work. A single shared 500 ms risk deadline is narrowed by decision and owner deadlines; it is **not** a separate 500 ms budget per rival or alternative. Forecasting is skipped when own-action work has exhausted its slice. The failed 02:10 decision never reached this phase, so rival forecasting did not cause that incident.

Future optimization: reuse exact immutable projected states within one decision and measure projection/fork/boundary work separately. Unknown or skipped rival risk must remain unknown, rather than silently becoming zero danger.

### P3: graph loading and candidate geometry have allocation costs

Location: `context/native_graph_parts.py`, `load_graph` around line 161; `context/context_store.py`, `json` around line 219; `planning/query_search.py`, `candidates` around lines 154–235.

Ordinary complete snapshots are decoded and validated when loaded. Verified terrain fragments already have a bounded cache. Candidate generation sorts legal geometry by target priority and filters certified distance bounds for each spell; unknown bounds conservatively retain all cells. These operations scale with arena size and repertoire, and create temporary lists. Current recursive geometry and encoder helpers explicitly break self-referencing local closures before returning, reducing retention until cyclic GC.

No current live evidence ranks candidate sorting above repertoire preparation. Preserve all unknown-bound candidates and exact directed XYZ topology. A future bounded decoded-graph cache should be keyed by verified content digest and return immutable/private views so caller mutation cannot corrupt later requests.

## Acceptance and observability criteria

1. Repeat the original monster species immediately after a world restart, then again warm; report separate catalogue, repertoire, prerequisite, metadata encoding/publication, GC, and preview timings.
2. Run a multi-monster fight and a larger arena, retaining movement, range, placement, effects, and legal target behavior.
3. Run a fight with summons and a late spectator; performance changes must not omit summoned actors or transition effects from complete snapshots.
4. Confirm owner deadline fallback completes without granting extra gameplay actions and does not leave pending presentation or a frozen turn.
5. Compare per-decision CPU and wall times without summing nested metrics or duplicate pre/post-commit tactical events.

The audit establishes the expensive live stage and several structural amplification paths. It does not establish a complete GC root cause, certify all gameplay features, or justify removing native authority validation.
