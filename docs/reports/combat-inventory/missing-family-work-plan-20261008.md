# Missing native class families: mechanism work plan

This plan records recovered identities and current ownership. It does not certify implementation or functional completion. Latest source-stable regenerated route inventory contains184 families:161 registered,23 construction-gated and zero without a static handler. Families308 and1002 now have exact gated factory routes. This work plan retains already implemented rows to track their pending integration evidence. Rebuild that inventory after implementations land; registration alone is insufficient proof.

| Families | Recovered mechanism / investigation scope | Owner | Required evidence |
| --- | --- | --- | --- |
| 308 | eYW area creation followed by copying damage characteristics | event_closure | Native area creation, actual copied values, expiration and removal |
| 666 | eWl inserts an additional turn in the current round | event_closure | Native timeline order, actual turn/ACK progression, cleanup |
| 667 | eXf controls start/end turn suppression through fighter frN flags | event_closure | Parameter branches, retained flags, actual turn callbacks and removal |
| 668 | eWL disables turn-duration recalculation; parameter branch adds prior duration | event_closure | Native duration/clock behavior and retained lifecycle |
| 309 | eZc redirects the triggering whole spell toward its source caster cell | summon_dependencies | Live triggering runner mutation; no substitute HP-only reflection |
| 320 | eYG captures a creature into its owner's symbiote roster | summon_dependencies | Native eligibility, properties/status, slot selection and ownership |
| 446 | eXZ clears a whole native fight property | summon_dependencies | Property removal semantics, not decrement semantics |
| 859 | eWz/eWA recalls an owned symbiote creature | casting_tests (source handoff from summon_dependencies) | Controller match, native property and HP/KO transitions, roster/occupancy lifecycle |
| 1000 | eWK live source target redirection connected to actual damage/healing consumers | terrain_producer | Four bounded regressions passed; original differential and class-cast integration pending; unsupported recalculation remains guarded |
| 933 | eWG temporarily replaces the actor spellbook with a profile ability book | terrain_producer | Scoped profile5900 dependencies, native levels, restoration only after execution |
| 316 | eZF removes the owning aura runners from families314/338; implementation registered | collision_resources | Full factory integration and retained removal; unit selection/preflight/lifecycle passed |
| 338 | eYJ creates a target-owned faN aura from actual target properties and direction | collision_resources | Exact constructor, packet/manager order, target identity and removal |
| 813 | eYU retained area with post-creation adjacent direction or native far-direction fallback; integrated | cast_delivery | Actual class cast and area lifecycle; directional units passed |
| 1030 | eYV signed-byte native affiliation replacement/restoration; integrated | cast_delivery | Actual cast/lifecycle; preserve immutable fight teams; unit reversal passed |
| 808 | eWq AP-to-MP conversion with live resource current/maximum notification listener | cast_delivery | Shared resource notification producer and native ordering; no static-buff substitute |
| 923 | eXm consumes actual caster AP/MP through native synthetic cost runners | summon_casting | Native amount/limits, current resources and delivery |
| 1002 | eZw/eZn character-copy construction plus copied actual ability levels | summon_casting | Actual character appearance/stats/book source; no fresh static-profile substitution |

The initial investigation remained offline; current integrated fixes are deployed to the single authorized world. Automated integration uses one bounded heavy process at a time and immutable source snapshots. The manual representative acceptance plan samples these mechanisms only when their automated evidence leaves a client-visible uncertainty; it does not require testing every spell/enemy combination.

## Current execution priorities

Use [the current status](current-status-20261008.md) for exact report hashes and limits.

- The complete frozen normal refresh covers635 pairs and73 legal decks:589 prepared/committed,46 legal contexts unavailable, zero final transaction rejections. Subsequent runtime fixes have targeted verification; this is not global semantic completion.
- Area308/TRAP: actual Sram owner/enemy lifecycle passes activation and central removal; the enemy probe also proves a two-cell push. Feca315 passes creation, turn damage, expiry and footprint reuse. Client acceptance remains pending.
- Cra beacon lifecycles pass all three elemental reaction/cleanup/recreation sequences; the9-pair matrix and3 critical reactions are separate evidence. Precision05 proves actual occupied-enemy wall damage with the state and twG rejection without it.
- Family859: replay13 commits the real recall branch, retires QI ownership and releases the actual captured slot. Client acceptance and broader interactions remain pending.
- Family1002 is connected to the runtime factory with source-backed constructor, appearance, raw PA and book. Raw deck representation is corrected. Actual8559 and copied-action commits, mutation/checkpoint/wire and retirement proofs are recorded in current-status; client presentation and wider variants remain pending.
- Family307: source-backed Sram visual-copy post-registration hook is connected; Pandawa registration permits the controller cell when native casting criteria allow it. Actual class replays remain pending.
- Family843: Enutrof's first replay still failed after the nullable-target correction. Post-removal phases now retain the original Qq object in a local execution scope; six focal tests pass and the second actual replay is running.
- Family933 profile5900 dependencies are imported. Actual copied-book child execution and complete transformation appearance/book interactions remain pending; state round-trip alone is insufficient.
- Family808 includes source-backed PB50 positive-AP rejection and PA notifications. Actual conditional cost/table verification remains required; no AP-to-MP payment remapping is invented.
- Family877 minimum-HP mutation now preserves hidden raw HP; four regressions pass. Other resource writers must preserve the same source-backed contract.

The route counts in the opening paragraph are the current regenerated static inventory, not a gameplay percentage. The full route JSON SHA256 is `a0855a99197e17be851013ec99b1ff6d5f34a2f8b83c5021f4601fa81516c6b5`; embedded source hashes passed the before/after check. The broadest direct class closures among provider-gated routes are1013(displacement authority,18 classes/395 effects),315(area retention,17/523),421(retention,17/341),300(displacement,17/191),843(retained area removal,16/202),422(displacement,16/161). These are structural provider dependencies, not newly observed failures: prioritize their shared parameter, callback, target-lifetime and resource integration boundaries when actual bulk traces expose a gap. See the regenerated route report for all23 dependencies. The chronological checkpoints below are historical and no longer describe missing current routes.

## Bounded regression checkpoint

Root command: `PYTHONPATH=server:server/tests /tmp/wakemu-combat-review-venv/bin/python3 -m unittest test_combat_fight_property_clear test_combat_aura_removal test_combat_affiliation_directional_area`. Result:10 tests passed in0.017 seconds. These unit results do not prove actual class casts or full client lifecycle.

Root rerun `test_combat_redirect_runner`:4 tests passed in0.110 seconds, verifying redirected damage/healing consumption and stale-source rejection. `test_combat_summon_recall`:3 passed in0.620 seconds, but native PR notification mapping is still under review; those tests do not certify the whole recall lifecycle.

Latest unregistered families:308,668,309,320,666,808,933,1002. Registration changes do not certify their neighboring registered mechanisms. Root rerun of turn suppression, capture-slot selection and source redirection:13 tests passed in0.222 seconds.

Latest regeneration now leaves308,668,1002 without handlers. Other routes still have pending source guards and integration failures; the remaining-handler count must not be presented as functional completion. The49-test resource batch had46 passes and3 issues requiring targeted triage (resource value expectation, missing fixture identity, missing owned cast context).

Newest regenerated missing routes:308 and1002 only.668 is registered under explicit Wakemu duration policy and retains pending integration requirements. Profile5900 dependency export includes three actions8588/8589/8590 and141 effects/15 states; import verification is pending its owner terminal report. Root rerun temporary-book tests:6/6 passed in0.804 seconds, including full-book grant rejection without removing a later book.
