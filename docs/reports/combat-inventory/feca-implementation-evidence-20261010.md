# Feca implementation evidence, 2026-10-10

## Scope and catalog

Offline only. No services restarted, no catalog activated, no production writes. Inventory reads active PostgreSQL revision `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095`; runtime probes explicitly pin staged revision `3472243858e1e2fc715342a7ba70396d077344847570b2109a4f37326b7dcee5` through `native_catalog.release`. This is not a live-client acceptance claim.

The complete catalog inventory and manual battery are separate adjacent reports. No executable missing definition or factory binding was identified in the reached Feca closure. Effect 11 is a criterion query operand, not an executable missing child.

## Actual pipeline qualification

`server/tests/test_feca_protection_pipeline.py` uses authoritative native QI, normal class initialization, ordinary casting, actual movement callbacks and ordinary end/ACK turn providers. Final focused run, including `test_combat_feca_start`, passed **4 tests in 27.136 seconds**.

- Gota 6972, Orbe Defensivo 6978 and Muralla 6980: self and another player recipient; native carrier and auxiliary states, unchanged HP, exact AP payment, unchanged source preview.
- Fecalistofedes 6967: empty-cell paired glyphs 1474/1477; legal actual one-MP movement into the footprint; movement does not activate damage.
- Orbe Defensivo: actual caster turn end delivers armor and removes carrier 6334. Carrier level 1519 yields 1025 armor on this fixture because its native player armor cap is 50% of 2050 maximum HP. The test checks the cap rather than assuming carrier level equals uncapped armor.
- Initial native Armadura de la Paz 7009 grant exists without injecting a grant.
- Passive 6992: actual Ready/start installs state 9315, preserves original fight and rejects duplicate start. Parent corrected the older test fixture to include authoritative QI; this was a fixture defect.

`feca-glyph-lifecycle-20261010.json` additionally records real-map legal glyph creation, enemy turn-start damage and normal paired expiry. The audit source check reports false because `server/wakfu_server/api.py` changed concurrently; its before/after evidence is retained. Combat source checks and the glyph audit tool itself were stable. Entry and post-expiry movement in that map were explicitly unqualified because actual tackle made the route unaffordable; the independent compact-arena movement test above qualifies movement without weakening tackle.

## Changes and limitations

The initial scenarios did not require gameplay changes; subsequent exhaustive passive/grant probes reproduced the shared defects documented below. Added focused tests and authoritative inventory tool. Updated the existing glyph audit path search to consider native rail and tackle costs and to report unavailable movement separately from successfully qualified turn damage/expiry. It does not grant resources or bypass movement guards.

The 20 diagnostic protection casts also exercised Inmune, Tregua, Pacificacion and Provocacion legal branches. Their diagnostic outputs are not a substitute for comprehensive semantic tests. Actual incoming-damage consumption across every shield, all 18 passive combinations, every glyph variant, all teleport/grant removal cases and graphical client behavior remain acceptance work. Feca must not be marked fully accepted from catalog completeness alone.

## Reproduction

Use the normal native test environment with `WAKFU_TEST_GRANTEDCAST=1`, `PYTHONPATH=server:server/tests:server/tools`, the read-only database connection and password-file configuration. Disable GC before native imports; patch `native_catalog.release` to the staged revision before loading the test modules, load `test_feca_protection_pipeline` and `test_combat_feca_start`, then flush output and terminate with `os._exit` using the unittest result. This avoids costly retained-catalog shutdown GC and does not activate the staged revision.

## Follow-up: complete bounded casts and two reproduced shared defects

The complete normal-deck audit (`feca-normal-casts-current-20261010.json`) reached all 21 owned actives in legal deck chunks. Nineteen prepared and committed through actual ordinary transactions; Egida 6986 and Magnetismo 6987 required an ally/owned-shield context absent from the one-player baseline. Separate actual allied scenarios qualify both: Egida installs native state 6365 and costs 2 AP/1 WP; Gota followed by Magnetismo targets the caster-owned allied shield and moves the Feca to (-10,-7,-1). A positive test retains these exact contexts.

All 18 legal class passives were equipped individually at level 200 before an actual allied Gota cast. This found a real Maestro de Escudos 6991 failure, rather than an absent catalog record: 6352 level 1 installs child 304540, whose passive branch 304040/304041 applies +2 to the same additive state. Native state 6352 is additive, maximum 3, refresh false and replace false. Native `eWu.fMY` (recovered bytecode offsets 141–257 in the local native-state-application oracle) accepts the level-1→3 replacement and rejects a further application at its cap. Existing state application planning already implements that contract. The shared dispatcher incorrectly rejected child 304540 when invoked by the distinct replacement carrier UID.

The correction keys immediate recursion by `(effect reference, state UID)` while keeping reference ancestry for diagnostics and the existing global depth 128. Same-instance and unbound immediate cycles still reject; endlessly changing state UIDs still hit the depth limit. New generic regressions cover all four cases, and the real 6991 regression asserts one final 6352 carrier at level 3. No native state flags or cap semantics were changed.

A real NPC attack against Orbe armor also exposed missing multiplayer authority forwarding in `prepare_npc_spell`: it constructed a runtime from one character although the native fight contained three registered players. Added optional `player_characters`/`deck_blobs` forwarding, preserving existing default behavior and concurrent NPC activation changes. The legacy `NativeProvider` accepts and forwards the same maps; its context hash includes all player decks so another player's deck change invalidates cached previews. The modern AI native oracle already owns its own full characters/decks registry; it does not instantiate this legacy provider. The regression uses actual Ready, Orbe cast, end/ACK, the registered NPC turn and `NativeProvider.preview` of owned Wonejo 7962 against the armored Feca. It does not remove other players or weaken roster validation.

The direct NPC-transaction variant and full seven-test Feca suite passed in 54.862 seconds. Independent Luna validation then passed 13/13: Feca six tests plus start one, four recursion tests and two provider-context tests, including the actual legacy-provider NPC preview. Each test may contain several positive/negative branch subcases.


## Follow-up: three-turn Peace Armor grant expiry

A native 7009 cast installs state 6364 and grants Teletransportacion 7052 at level 1. The latter really teleports onto a legal empty cell adjacent to an enemy and costs 0 AP/1 WP. Advancing actual turn-end/ACK/start providers across three Feca starts exposed another shared defect: a turn-triggered dispel cloned from a spell-owned retained listener emits a source cost descriptor under a lifecycle runtime plan, which has no original spell ID/level. The exact PL snapshot was already captured and validated by replay; the cost emitter incorrectly read only the generic runtime plan.

`source_cost_descriptor` now uses the retained PL's exact spell ID/level when present and type 11. It validates presence, spell/protection flags, packed identity and identity agreement with the resolved container. It does not infer levels from children, does not reinterpret state/area containers as spells and does not fall back to an unrelated plan when retained authority is malformed. Ordinary non-retained plans retain their existing path.

The new `test_feca_grant_pipeline` verifies actual initial grant, 7009 costs, state 6364, exact 7052 grant level, legal teleport and its costs, then twelve real turn boundaries (three Feca starts): state 6364 and grant 7052 disappear; grant 7009 and the active fight remain. This and the malformed/retained cost-source unit test passed 2/2 in 22.449 seconds. Independent final replay/turn/cost verification is delegated on frozen source.

## Final independent verification

Luna completed the final frozen-source gates: 75/75 focused replay, turn and cost tests; 17/17 dispatcher tests; and 173/173 broad regressions. The synthetic fresh-listener test now checks registration and recursion identity directly instead of calling `_execute` on an unconstructed dispatcher; actual execution and cycle rejection remain covered by the dispatcher pipeline tests. Parent confirmed stable source for these gates. No service restart, deployment or catalog activation was performed by this workstream. Any subsequent NPC catalog merge requires the coordinated complete-build validation described by the parent workstream; these results do not certify later changes or replace manual acceptance.
