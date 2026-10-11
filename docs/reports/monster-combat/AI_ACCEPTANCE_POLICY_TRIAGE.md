# Low-level monster acceptance: planning policy review

This read-only investigation follows manual observations: first-turn Wonejo/Bebetofu inactivity, Tofu remaining adjacent after attacking, black monsters entering glyphs unnecessarily, Miaumiau selecting summons, and a white monster removing AP but apparently spitting at an empty cell. No production policy or original test expectation has been changed for this investigation.

## Confirmed generic policy behavior

`wakfu_ai/planning/query_search.py::_metrics` assigns every active actor a position utility of negative distance to the nearest living enemy multiplied by 0.25. It uses directed native topology when available and otherwise the legacy XY heuristic. Its immediate threat metric is zero. This generic utility rewards approach, independently of whether a monster's capabilities suggest melee or hit-and-run behavior. Movement enumeration similarly promotes routes toward nearby enemies. This is a policy limitation, not evidence that retreat movement is illegal.

`planning/scoring.py::evaluate` gives equal HP-damage and kill utility to enemy players and summons. Target iteration prioritizes enemies with lower HP before distance. No summon-owner priority appears in those rules. A summon kill can therefore dominate a smaller hit against its owner under the current utility. Team focus provides a small explicit focus bonus; it does not establish a universal player preference.

Outcome features affect decisions only with configured feature weights. Without a native hazard feature and its weight, future glyph exposure has no independent penalty. Actual immediate HP loss is already penalized through friendly HP deltas. Rival projection can penalize forecast harm, but its operation, coverage and incomplete-risk evidence must be checked in the actual replay before concluding it ran. A synthetic hazard label alone is neither a native glyph proof nor a safe movement legality filter.

Search starts with the empty plan at score zero and updates it only on strictly greater utility. Spending AP/MP without any observed damage, control, healing, position or other benefit can therefore favor passing. This is only a possible explanation of first-turn inactivity. The live replay must establish candidate enumeration, rejected casts, forecast budget, timing and actual spell outcomes. It does not establish a turn-counter bug.

## Offline characterization

New independent tests in `server/ai-service/tests/test_acceptance_policy_characterization.py` call the actual metrics and scoring functions without catalogs or mocked combat results. They characterize three current behaviors: proximity defeats retreat after equal damage; equal damage to a player and summon has equal utility without focus; an unweighted outcome hazard feature does not affect utility. These tests preserve all existing expectations and do not assert that those behaviors are the desired final design.

Command:

```
PYTHONPATH=server/ai-service:server/ai-service/tests .runtime/local/verification-venv/bin/python -m unittest test_acceptance_policy_characterization
```

Result: 3 tests passed in 0.001 seconds. No database or service interaction.

## General implementation proposal, pending live replay evidence

Use native capability and existing profile authority to select useful engagement distance rather than forcing every actor toward the closest enemy. Evaluate retreat through the same legal native movement previews and rival projection; retain its HP, resource and positional costs. Measure hazardous outcomes from actual native glyph/trap execution or forecast authority, then expose explicit weighted features with completeness evidence. A configurable target preference may reward pressure on owners while retaining summons as legal and sometimes optimal targets. Avoid species-specific movement exceptions, excluding summons from candidate enumeration, or inventing hazard blockers.

Before changing production, inspect the manual replay's source-bound states and rejected/accepted casts for the first-pass and white-monster spit cases. An empty target coordinate can be valid for an area spell; animation alone cannot prove an empty semantic outcome. Distinguish actual AP-removal/control utility from an additional no-effect cast and from a preview/commit mismatch.

## Equal-outcome occupied/empty target reproduction

A fourth independent test runs the real query-search coroutine with two candidate casts whose synthetic area outcome is identical. Swapping enumeration order swaps the selected action: an empty coordinate wins when enumerated first, while the occupied target wins when enumerated first. This is a deterministic tie-order observation, not proof that the observed white monster's native spit had that outcome. The test changes no original assertions and loads no native catalog.

The immediate selector updates `best` only when `score > best['score']`. It has no explicit occupied-target tiebreak. A narrowly scoped proposal is to prefer a source-state living occupied target among equal-utility, equal-length plans with semantically equivalent authoritative outcomes. Compare actual HP/resources/armor/states/features/positions, retain empty-area casts as legal candidates, and never replace a stronger empty-area outcome with a weaker occupied hit. Keep shortlist/rival-risk ranking consistent with the same tie rule. Production changes remain pending native replay evidence and review.

Updated characterization result: 4 tests passed in 0.038 seconds. Root independently identified first-turn inactivity as a source-immutability guard rejection after repertoire generation; this supersedes the initial possible score-zero explanation for that specific observation. A separate agent is tracing that guard.

## Native target authority and live-plan correction

No occupied-target tiebreak was retained in production. Public outcome metrics do not expose complete state ledgers, usage and cooldowns; equal visible HP/score cannot prove exact semantic equivalence. Complete runtime fingerprints can safely prove equality but may differ for bookkeeping, making a cosmetic tiebreak inapplicable. A tentative conservative helper was removed before deployment after review; the four original characterization tests remain.

Spell 5768's exported roots 182657/183261 (class 4) and 182618/183262 (class 55) have `fcE(mask=1)` with point `anD` geometry. `free_cell=false` must not be interpreted as requiring an occupied cell: it means no free-cell requirement. Casting target resolution explicitly resets the target to None for each request, resolves QI actors at that cell, and the oracle rejects mismatches between the requested target ID and native plan target ID. Static inspection found no previous-target fallback there.

Point-area selection with a native selector includes the target PV's physical radius, so a non-centroid coordinate can legitimately intersect a large actor. This must be checked against actual actor authority instead of adding an invented centroid-only guard.

Root's live replay evidence changes the diagnosis further: fight 177 turn 7 selected a two-cast plan starting at empty `[-20,-13,-1]`, with total damage utility 6; the subsequent occupied cast at `[-19,-9,-1]` targeting actor 10 produced damage utility 5. The first plan's recorded damage evidence references effect 182657 against actor 10 from an intermediate state, not the empty cast directly. Therefore the two casts have not been shown to have equivalent outcomes. A one-point passive/glyph/resource-spend side effect or a multi-action aggregate is still possible. Reproduction must preserve the actual Feca glyphs, states, positions and event sequence; a bare-fighter test cannot establish that cause. No fallback or illegal empty target is claimed from this observation.

## Complete live graphs: the empty cast does no damage

Read-only copies of the three actual gzip-encoded JSON graphs were obtained from the AI context store, without native object deserialization or PostgreSQL access:

- Root: `022db610a65cb3d8aceab2ab0195eb72ac67a844abb5e0a5afe558dfef504784`.
- After empty cast: `bd636e239ff2d51d4f2bfb99d96fe15092c3b4e687329411e42dee7c1da16d9b`.
- After occupied cast: `78944852a8b57f4f06816193d17a59a3c5b59baf0897c0aa3a8e021c70216248`.

Private raw copies, safe structural-view code and expanded actor/event data are in `.runtime/monster-local-unit-20261010/live-*`. The views traverse JSON fields and preserve cycle markers; they never instantiate serialized classes.

Root to empty adds exactly one event: sequence 54, `npc_cast`, spell 5768, target null. Player 10 remains at HP 111 and all of its native actor fields are unchanged. The other NPC is also unchanged. Only caster AP (6 to 3), raw AP, corresponding effect stat and direction (3 to 5) change. At fight level the changed fields are actors, native spell usage, sequence and events. State ledgers, glyph data and all other fight fields are unchanged. All three actors have native physical radius zero.

Empty to occupied adds damage event 55 against actor 10, amount 6, HP 111 to 105, followed by the occupied NPC cast event. Caster AP changes 3 to zero and direction returns 5 to 3. Thus the empty cast itself neither hit a previous target nor caused glyph/passive damage. All six damage points belong to the following occupied cast. This supersedes the earlier possible one-point empty-cast side-effect explanation.

## Forecast sample exploitation and safe scope

`NativeOracle._rng` seeds each forecast from the entire `state_key(fight)` and action. Spending AP, changing direction, usage and event sequence therefore changes the subsequent damage sample. Native damage arithmetic uses random fractional rounding. This supplies a concrete mechanism by which a useless cast prefix can make the next occupied cast appear one point stronger, even though it costs three additional AP. Direct occupied damage five versus prefixed occupied damage six still requires the direct graph/arithmetic trace to prove the exact draw; the complete graphs already prove that the extra damage is not an empty-cell impact.

A fifth independent characterization test runs actual query search with synthetic authoritative outcomes: empty cast does zero damage and costs three AP; the subsequent occupied sample deals six, while a direct occupied sample deals five. Search selects the empty prefix because the one-point sample gain exceeds its 0.3 resource penalty. All five characterization tests pass (0.079 seconds). This test proves the planner mechanism; it does not replace a native rounding trace.

The general preferred repair is common forecast randomness bound to stable encounter/turn/caster/spell/target authority, rather than irrelevant state changes in a no-effect prefix. Legitimate buffs, target states, facing, resource gates and native effect execution still change arithmetic and eligibility. Repeated identical actions would share forecast samples, a correlation that must be documented and regression-tested; real commit randomness must remain separate.

An exhaustive damage/control point-root closure alone is insufficient to prune empty casts: AP spending or spell launch can trigger other native effects, and facing itself can be consequential. Full native snapshot inequality also cannot distinguish harmless bookkeeping from meaningful effects without an audited contract. Do not add a broad ground-target ban, weaken source guards, or hide class preparation actions. No production repair was applied during this investigation.

## Implemented narrow NPC forecast sampling repair

After review, `NativeOracle._rng` now uses common samples only for NPC cast forecasts. The exact seed fields are schema `npc-cast-common-randomness-v1`, fight ID, fight turn ID, caster ID, caster turn count, spell ID, evaluation level, target actor ID and same-target cast ordinal. The ordinal counts authoritative `npc_cast` events matching that fight turn, caster, spell and target. Native usage tables cannot supply a universal counter: per-turn and per-target counts are recorded only when their corresponding limits apply.

For ground casts, target identity is null and the seed additionally includes target XYZ. Their ordinal counts matching null-target cast events, since existing events do not record coordinates. Empty ground casts cannot change the occupied actor-target stream. Repeated occupied attacks and later turns receive different samples. HP, AP/MP, facing, movement, sequence and unrelated spell/target events do not reseed that stream, while all those facts still affect the native eligibility/formula normally.

Player forecasts, movement and start/end boundaries retain the previous complete-state seed. Real commit execution (`forecast=False`) retains its independent `random.Random()` construction. No class engine arithmetic, spell rules, target filtering, source guard or existing expectation changed.

Focused read-only validation through the existing NoRedis runner passed 64 tests in 0.876 seconds: seven new common-randomness regressions, five acceptance characterizations and the existing 52 query-search tests. The new tests verify deterministic repeated samples, source immutability, empty-prefix/movement/facing/resource invariance, independent target/spell/event ordinals, repeated attacks, turn boundaries, ground repetitions, unchanged player/movement/boundary seeds and real native damage formula sensitivity to mastery despite identical RNG samples. Receipt: `.runtime/monster-local-unit-20261010/npc-common-randomness-focused.log`. Actual native transaction/commit replay remains a separate validation step; this focused result does not claim those paths were rerun.

## Real native padding/transaction verification

A new integration test constructs actual reference 39 at native level 4 through the validator's ordinary map-1134/QI fixture, with caster `(-8,-7,-1)`, enemy `(-5,-7,-1)` and empty target `(-9,-8,-1)`. It uses the real oracle and native eligibility/LOS rather than mocked targeting. Both native casts are legal. The empty preview spends three AP, produces no damage and leaves enemy HP unchanged. The following occupied attack produces exactly the same positive damage as the direct occupied preview. Target events are correct; snapshots of the original source and intermediate empty-preview source remain unchanged.

A read-only, NoRedis run combined that new regression with three existing native oracle transaction tests. Four tests executed in 19.617 seconds: the new reference-39 regression passed, the existing oracle/native-preview equivalence passed, and existing commit/late-serialization rollback passed. The lethal-commit test errored because its injured-target fixture assigns effective HP=1 without updating raw HP authority, violating `hp_raw_current` validation. Its assertions were not changed and the error is recorded separately; this run is not reported as four passing tests. Full log: `.runtime/monster-local-unit-20261010/npc-common-randomness-native.log`.

The lethal-commit case is a newly added regression from this work, rather than an original baseline test. Its fixture was subsequently corrected by another agent to use the authoritative `set_hp_raw_current` producer; no expectation changed. After confirming that correction without overwriting it, the authorized final native run passed all four tests in 20.141 seconds. Before/after SHA-256 hashes of NativeOracle and both involved test files match exactly. Receipt: `.runtime/monster-local-unit-20261010/npc-common-randomness-native-v2.json`; complete output: `npc-common-randomness-native-v2.log`. This closes native padding, existing native preview equivalence, commit/serialization rollback, and new lethal delivery/rollback validation for the RNG repair. No deployment or service restart was performed by this agent.

## Rival forecast budget scheduling

The query search now treats `rivalSearchReserveMs` as a configurable part of the existing decision wall slice. It defaults to 500 ms, accepts integers from 0 through 10,000, and reserves at most 25% of the known decision slice when `project_turn` is available. Own-action exploration stops at the earlier search cutoff; rival projection may then use the remaining reserved time, still bounded by the total decision deadline and the owner deadline minus `commitReserveMs`. The reservation does not extend the owner turn or reduce the commit reserve.

If no root action was certified, or a slow root preview consumes the total deadline/commit reserve, rival projection remains skipped. Setting `rivalSearchReserveMs` to 0 preserves legacy shared-slice behavior: projection uses only time left after own search. `searchBudgetEvidence` reports reserved and used milliseconds. The additive fake-clock regression verifies the reserved path, zero-reserve legacy path, and rejection of boolean/negative/over-limit reserve values. These tests use synthetic query responses; they do not validate native projection coverage or operational latency.

Glyph exposure remains unresolved as a native forecast input. Current native area movement tests show that entering an empty glyph does not itself trigger damage; turn-start area activation is an emulated policy whose event producer is not recovered from native server code, and area callbacks are separately gated. Do not score glyph occupancy or infer delayed damage from cell labels. A future hazard penalty requires verified native event authority and a source-bound forecast that measures actual actor deltas with explicit completeness. This scheduling change does not establish or claim that hit-and-run behavior is fixed.

## Soft preference for registered summons

The native query-search policy accepts `registeredSummonValue` from 0 through 1 and defaults to `0.25`. It scales hostile registered-summon HP damage, armor changes, and control value; allied healing and other allied outcomes are unchanged. A discounted summon kill receives no separate strategic finish bonus because its scaled HP damage already rewards the outcome. The default score API value remains `1` for callers that do not opt in, preserving their previous scoring. Target selection uses the same scaled hostile damage, so equal damage favors a non-summon enemy. Summons remain legal candidates and can still be selected when their certified outcome is useful and no better action is available.

When native topology is available, search keeps the complete nearest-hostile `topologyDistances` and adds `primaryTopologyDistances` for nearest living hostile actors not explicitly marked `registeredSummon: true`. Pursuit uses the primary distance when that actor has a primary target; otherwise it falls back to the complete field. Occupied cells, including constructs and summons, remain blocked unless they are the selected distance field's goal. This is a soft AI heuristic, not a native combat rule or a claim about summon ownership. It depends on the native registration flag being present and accurate; unknown/missing flags retain legacy target treatment. The `0.25` default is a tuning starting point, not calibrated balance data. Synthetic regressions cover equal damage, low-HP summon-kill competition, summon-only fallback, malformed policy values, and a blocked construct. Native encounter replay and broader behavior tuning remain open.
