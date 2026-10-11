# AI native combat failure triage

## Evidence and scope

The initial read-only AI discovery ran 531 tests in 61.465 seconds, reporting two failures and seven errors. This investigation reads that log and traces producers before changing behavior. Production modules, catalogs, databases, and services were not modified by the investigator. The initial artifact is `.runtime/monster-local-unit-20261010/ai-service-readonly.log`.

Five affected modules were then run together after explicit fixture repairs: `test_native_oracle`, `test_query_sessions`, `test_world_entry`, `test_native_stats`, and `test_native_session_preparation_metrics`. That diagnostic ran 50 tests in 27.06 seconds: 45 passed, two failed, three errored, and none were skipped. All recorded AI/combat source hashes remained unchanged during that run. Its artifacts are `ai-triage-fixtures.json` and `ai-triage-fixtures.log` under the same private directory. This targeted run is not an activation certificate.

## Initial failure classification

| Initial symptom | Cases | Producer contract and evidence |
| --- | ---: | --- |
| `Native spell casting eligibility rejected: twI` | 3 errors | Native effective range rejects an actual source/target distance. The common Wonejo fixture allowed live arena relocation and therefore did not preserve its adjacent actors. |
| Registered creature expected an obsolete lifecycle rejection | 1 failure | The same range problem initially masked the expectation. After range repair, no exception is raised. The expected rejection string occurs only in the test, not current production code. |
| Search selects movement instead of a cast | 1 failure | The initial search receipt reports both `twI` and `Casting facing requires the actual registered preview actor`. Repairing placement exposes the latter production caller mismatch. |
| `KeyError: map_id` | 3 errors | `world_entry._prepare_npc_turn` constructs `NativeStats` from the viewer's owned encounter map. Mock viewers supplied only an ID. |
| Missing `native_fight_property_counts` | 1 error | Registered summon wire serialization requires the complete native property-counter population. A hand-built `SimpleNamespace` omitted it. |

## Arena placement and native range

`local_arena` defaults to `relocate_monsters=True`; when `compact` is unspecified it follows that value. Compact encounter selection can spread opponents to different native cells. `create_placement` deliberately uses `arena['participant_positions']` for NPC actor positions, while the player's position comes from its character authority.

`NativeOracleTests.wonejo_fixture` requests player `(-8,-7,-1)` and NPC `(-7,-7,-1)`, but previously accepted the live relocation policy. The failing query receipt shows an NPC at `(-11,-22,0)` while its player remained near the requested source. The shared casting producer correctly rejects that distance with `twI`; mocking line of sight cannot make an out-of-range cast valid.

The fixture now calls `local_arena(..., relocate_monsters=False, compact=False)` so the intended adjacent geometry survives. Native casting and line-of-sight guards remain unchanged. After that repair, all three original range errors reach the next authoritative boundary and fail on missing casting-facing context instead.

## Casting-facing and duplicate NPC execution

`mirror_cast_facing` changes direction only for a verified native casting contract. Once rotation is required, it demands an actual preview fight and object identity: `fight.actors[caster.id] is caster`. It then calls registered direction propagation. This protects QI/carrying registration and must not be weakened.

The shared server NPC transaction passes `fight=preview`. The AI's independent `NativeOracle.cast` NPC implementation calls `mirror_cast_facing(caster, plan)` without that argument. This is a production caller mismatch, not fixture metadata. The targeted run reproduces it in native search, native damage observation, and server/AI preview equivalence. Search catches rejected actions and can choose `end_turn` rather than a valid attack, explaining the remaining search failure.

Further drift exists in the duplicate AI block: it subtracts AP/MP directly instead of using the server's native raw/effective resource adjustment and notifications. Its factory unconditionally selects the expanded NPC compiled catalog, so it also bypasses the new per-monster imported-effect route. Source snapshots, active-spell scopes, event capture, and actor registration must remain aligned across both entry points.

The agreed general repair is to share the validated NPC execution block rather than relax guards or blindly replace the AI factory. A helper in `combat_npc_spell` accepts the validated plan, selected rule, native descriptor, existing effect factory, and action ID. Both entry points retain their ownership and native eligibility checks, then use the same spending, registered facing, private execution, usage, events, and packet transaction. The AI retains its factory so damage observation, registered summon authority, and timing contexts survive. The AI factory must receive the selected baseline/expanded compiled catalog; player casts remain on their player route.

The investigator does not modify that production implementation. Root owns the shared-execution change and its scope review.

## Missing map and property authority in mocks

`world_entry` passes `viewer_character['map_id']` to `NativeStats`, which needs an owned encounter map for registered actors. The world-entry orchestration and preparation-metric mocks now explicitly use map 1134. Existing forwarding, deadline, transport, and metric assertions are retained. All three initial map errors pass in the targeted run.

`registered_summon_stats` serializes `fight_property_payload(actor.native_fight_property_counts)`. That payload replaces the complete client property-counter collection; an absent field is not equivalent to an empty collection. `NativeSummonBuilder` initializes a counter dictionary and adds actual properties during construction. The hand-built wire-format fixture now supplies an explicit empty counter population, consistent with its state-free mocked actor. Its original identity/control/wire assertions remain intact, and the initial property error passes.

## Obsolete registered-summon rejection expectation

The test `test_registered_creature_ownership_wire_and_unsupported_lifecycle_are_explicit` expects `Summoned-actor lifecycle propagation remains unaudited`. Repository search finds that message only in the test assertion; current production has no matching rejection. Once the spatial fixture is repaired, the cast returns rather than raising. This establishes a stale expectation, but it does not by itself prove the lifecycle is correct.

The test also constructs `NativeStats` without a map later in its body, a subsequent missing fixture authority currently hidden by the failed assertion. A replacement must verify real registered ownership, transaction outcomes, packets, source immutability, and registration/lifecycle continuity, or demonstrate a specific remaining unsupported contract. The investigator has not weakened or removed the assertion pending that review.

## Remaining verification

After the shared execution repair settles, meaningful checks should cover server/AI transaction equivalence, native raw/effective resource snapshots, registered facing, damage-observer evidence, baseline/expanded routing, temporary ownership, registered summons, and post-turn continuity. Existing source and receipt fences must remain enabled. A successful local AI subset does not replace the separate stable NPC activation batch, per-monster delivery checks, or complete current-server build.

## Shared-execution follow-up and preserved discrepancies

Root implemented the shared validated NPC execution helper and explicit Oracle catalog selection. A second targeted diagnostic ran 51 tests in 31.47 seconds: 48 passed, two failed, one errored, and none were skipped. `combat_abandon.py` changed concurrently, so this is diagnostic evidence rather than an immutable-source certificate. Artifacts are `ai-triage-shared-execution.json` and `.log`.

The original three facing errors no longer occur. The round-trip search now selects and freshly certifies a cast; its remaining failure is a later assertion that source AP equals 3, while the rebuilt native Wonejo source has AP 6. That expectation is retained for review. The flank test sets `fixture.npc.mp = fixture.npc.effect_stats[2] = 4`: stat 2 is AP, so this mutates AP effective state without its raw snapshot and correctly fails the strengthened resource guard. This fixture mutation also remains visible pending review; the native guard was not relaxed.

A focused registered-creature diagnostic established the actual current result for spell 7988: native range 1–3 accepts the selected target, root 367989 executes, state 8030 is applied at level 50 for duration 2, characteristic 27 decreases by 50, caster AP decreases from 6 to 3, and packets include 12588, 12678, and two 12613 notifications. The source remains unchanged and its registration survives in the private result. These observations motivated an independent positive regression for state application, raw/effective AP consistency, packet identity, registration continuity, and failure after private execution.

Hector explicitly warned against changing test expectations. The original `test_registered_creature_ownership_wire_and_unsupported_lifecycle_are_explicit` was restored intact from HEAD, including its expected rejection and its discrepancy. The positive registered-creature test is separate; it does not erase the original red result or establish full summon lifecycle support. The original AP and flank expectations were likewise not rewritten to manufacture a green suite. The new positive test initially compared the builder's `SummonRegistration` dataclass with the fight's normalized dictionary; that test-only comparison was corrected to compare the actual source and preview registration dictionaries.
