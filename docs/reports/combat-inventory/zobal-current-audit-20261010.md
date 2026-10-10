# Zobal current combat audit — 2026-10-10

Read-only source and catalog review for native class 14 (Zobal/Masqueraider). No runtime, client, service, or database state was changed. The purpose is to separate published-record presence and runtime route support from full mechanic acceptance.

## Current catalog authority

PostgreSQL's active native catalog is the authority. The checked reconciliation pins complete revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38` (7,483 documents; activated 2026-10-09 18:16:18 UTC). Its Zobal row reconciles 40 owned spells (21 active, 19 passive), five extras, and innate seeds 3769 and 4464 against the local inventory, with no ID/kind/unlock/name deltas and no missing published grant-effect definitions. The five extras each have both a published granted tree and casting record. Their grants all originate from innate state 3769:

| Granted action | Grant effect | Catalog status |
|---|---:|---|
| 7081 Máscara Sáikopat | 308275 | grant tree and cast record present |
| 7082 Máscara Eskérdikat | 308276 | grant tree and cast record present |
| 7083 Máscara Zobal | 308277 | grant tree and cast record present |
| 7226 Máscara Sáikopat II | 316972 | grant tree and cast record present |
| 8559 Espíritu Enmascarado | 413347 | grant tree and cast record present |

The exact active-release summary and document hashes are in [published-catalog-reconciliation.json](remaining-classes-20261010/published-catalog-reconciliation.json). Relevant active document hashes include `breed-innate-definitions.json` `99d83aa956797dfdb8746e485dbe267574ef606bf23c71416244e7393558c25d`, `native-class-spell-grant-closure.json` `14f511d4e86436584f7a4376f0421b74c0ac94dc16773bad83cbd74d3741b6e2`, and `granted-spell-effect-trees.json` `2d07839bdf094a23cd6cba02da6853766bc21f82244b59a1d2fcdc3bfb903477`. The local proof is a previously executed direct read-only PostgreSQL reconciliation; it proves current source record presence, not gameplay execution.

The detailed typed roots, criteria, parameters, and state fields cited below are from the pinned Oct. 7 native graph, not a newly dumped copy of every active PostgreSQL document. The current Oct. 10 runtime route matrix was regenerated against current source. This distinction matters: matching current roster/grant records does not refresh every detailed edge in the historical graph.

## Innate masks and grant/book lifecycle

Current code loads breed innates from `breed-innate-definitions.json`. `combat_class_initialization.plan()` validates the owned deck and creates passive invocations only from its passive slots. `initialize_transaction()` applies the actor's innate states first, then dispatches the selected passive roots in their native spell/effect context. This is shared machinery, not a Zobal-specific behavior implementation; see [combat_class_initialization.py](../../server/wakfu_server/combat/combat_class_initialization.py#L55) and [combat_effect_runtime.py](../../server/wakfu_server/combat/combat_effect_runtime.py#L236).

The Oct. 7 native state 3769 definition has selected roots `[164045, 307822, 308188, 412925, 413071]`. Root 307822 is an ordered group containing the five native spell grants above. Its `eWn` grant children select bar 2, slot 0 for 7081 or conditional replacement 7226, slot 1 for 7082, slot 2 for 7083, and slot 3 for 8559; their level operand is `-1` (native effective-level sentinel). The 308275 child grants 7081 when passive 7104 is absent; child 316972 instead grants 7226 when 7104 is in the deck. This is a native conditional grant substitution, not a missing action. The grant service keeps action-object identity by spell reference, emits its evaluated-application packet, and removes the book object by UID/reference on native effect removal; see [combat_spell_grant.py](../../server/wakfu_server/combat/combat_spell_grant.py#L17) and [combat_spell_grant_book.py](../../server/wakfu_server/combat/combat_spell_grant_book.py#L1).

The three base mask actions apply their primary mask states (6611/6612/6613). Their native trees do not remove the other primary mask states; the explicit removals address only the competing bonus states 6614/6615/6616. The corresponding bonus-state application is a separate branch. Its selector is `fcE` mask `1125899906842753` (ally-only relation plus the audited high-bit actor guard) over a radius-four circle centered on the cast cell, followed by `IsChallenger("target")`. In this runtime, ally relation excludes the caster. `IsChallenger` means native PLAYER_CHARACTER or COMPANION membership, not PvP challenger/duel status. Therefore a nearby allied player character or companion can receive the bonus in PvE; the caster cannot receive it through this branch. The native graph supports primary states coexisting during their native duration while the bonus states are switched exclusively; it does not encode “exactly one primary state.”

| Action | Primary state | Challenger-guarded bonus state | Other bonus states explicitly removed |
|---|---:|---:|---|
| 7081 Sáikopat | 6611 | 6614 | 6615, 6616 |
| 7082 Eskérdikat | 6612 | 6615 | 6614, 6616 |
| 7083 Zobal | 6613 | 6616 | 6614, 6615 |
| 7226 Sáikopat II | 6888 | 6614 | 6615, 6616 |

Those state application/removal families are routed through the shared state handlers (families 304 and 321), and their route is currently registered. The Oct. 10 route matrix shows no unregistered family binding in its scope. The new controlled production-entry fixture `.runtime/zobal-review-20261010/mask-sequence-ready.json` recorded same-fight casts 7081 → 7082 → 7083 and ledger states 6611, 6612, and 6613 simultaneously, each at duration 2. This is consistent with the native trees: no primary-state removal is encoded, and each primary state definition has duration 2. The fixture was `ready_started` with `gameplay_verified:false` and did not validate the client display, so this establishes server-ledger behavior only. This fixture contains only the owned Zobal and an enemy, so there is no eligible allied PLAYER_CHARACTER/COMPANION target in the bonus branch area; the absence of bonus states here is expected and does not demonstrate a PvE failure. Verify bonus delivery with another allied player or companion within four cells of the cast center. No state/effect reference 13560 occurs in this class graph, so its relation to mask switching is not established by this evidence. The graph establishes the mask transitions encoded in source; it does not prove exact client appearance/HMI, stat values, packet order, or visual behavior.

### Passives

All 19 passive roster entries are available to the shared deck-driven initialization plan, but none is individually marked complete in the Zobal inventory. The direct passives whose dependency closures include construction-gated routes are:

| Passive | Gated family in current route matrix | Construction condition |
|---|---:|---|
| 7102 Protector Apartado | 421 (`eXe` dispel) | retained-effect registry must be present |
| 7103 Colisiones de Apoyo | 421 (`eXe` dispel) | retained-effect registry must be present |
| 7106 Colisiones Regenerativas | 421 (`eXe` dispel) | retained-effect registry must be present |
| 7107 Espejos | 422 (`eXk` displacement) | displacement authority must be present |

These are route guards, not absent handlers. Normal spell plans construct retained-runtime context; the factory also installs displacement handlers only when displacement authority is supplied. Full passive verification must still prove the specific Zobal event source, passive ownership change, applied amount, state/effect duration and removal. The remaining passive names/roots are listed in the [class inventory](remaining-classes-20261010/14-review.md#passives).

## Espíritu Enmascarado (8559) copy lifecycle

The active reconciliation proves that spell 8559 has a published grant tree and casting record. The pinned Oct. 7 graph provides the detailed route lead: roots `[413396, 413075, 413076, 413105]` in order.

1. `413396` is family 28 (`eXc`) and has criterion `IsOwnSummon(2382, "target")`; if selected and reached, it zeros HP on an own copy-profile summon before the later creation roots execute.
2. `413075` is family 1002 (`eZw`) and constructs the fresh character copy using constructor profile 2382.
3. `413076` is family 330 (`eYg`), gated by `IsBreedId("target", 2382)`, and applies the native ordered follow-up children to that copied actor.
4. `413105` is family 304 (`eWu`), guarded by `not HasState(3813, "target")`, and applies state 3813 to the resulting copy.

A separate native casting predicate is attached to 8559: `IsBreedId("caster", 14) and ((GetOwnTeamStateCountInRange(-1, "caster", 3813) <= 1 and HasState(3813, "caster")) or (GetOwnTeamStateCountInRange(-1, "caster", 3813) <= 0))`. This is preserved from the Oct. 7 casting export; it is not yet verified against live `GetOwnTeamStateCountInRange` semantics. In particular, do not infer that an ordinary Zobal can recast to replace an existing copy just because the effect roots list a kill before creation: the owner branch requires team count `<= 0`, while a caster already carrying state 3813 uses the other branch. Whether copy casters can satisfy that branch, and how the native selector/source team are counted, remain unverified.

The copy profile is positive source evidence, not an absent definition: the original profile 2382 has an empty base ability book and no initial states. The current eZw path augments this constructor using the source owner's actual raw deck and granted actions, computes copied stats/appearance/equipment from actor authority, installs the copied book, registers the actor under profile 2382, and emits an owned character-copy packet. The implementation is in [combat_character_copy_handler.py](../../server/wakfu_server/combat/combat_character_copy_handler.py#L42) and [combat_character_copy_runtime_book.py](../../server/wakfu_server/combat/combat_character_copy_runtime_book.py#L25). Family 1002 is registered when summon authority exists; that path also requires retained-container authority. The production cast factory wraps actor authority with `RegisteredSummonAuthority` and supplies that actor provider as both `summon_authority` and `displacement_authority` ([combat_server_spell.py](../../server/wakfu_server/combat/combat_server_spell.py#L139)). It constructs retained runtime for a spell transaction in [combat_effect_runtime.py](../../server/wakfu_server/combat/combat_effect_runtime.py#L236). These code facts satisfy the generic family-1002 constructor guards in this path; they do not prove the Zobal-specific descriptor, copied-book packet, or lifecycle succeeds end to end.

There are specific limitations in the current code path worth preserving in the test plan:

- `NativeCharacterCopyHandler.__call__` rejects a retained eZw descriptor. The 413075 native record is an immediate fresh creation route in the pinned graph; it is not evidence that persistent eZw subscription/retained cloning is supported.
- Copy creation requires a real owned class source record, raw deck, actor authority, copy profile data, character-copy appearance authority, and a valid copy-book metadata set. Missing any dependency fails closed rather than synthesizing a class copy.
- `413396` conditionally kills a selected own profile-2382 summon through family 28 if this effect branch is reached. Verify when the cast predicate admits the original owner versus an existing copy, the kill-to-create ordering, summon/QI retirement, duplicate attempts, and failed-copy rollback in a complete cast. The runtime contains general kill and summon-retirement machinery; no Zobal-specific replacement-cycle test was found.
- The copied class book starts with profile 2382's empty base actions and adds the current source deck/grants subject to native availability and level limits. Confirm whether the resulting client-visible book contains each Zobal extra and whether it permits or rejects recursive Espíritu Enmascarado casts according to native rules.

The old [copy-profile evidence](class-copy1002-constructor-profile-20261008.md) and its machine record establish the profile-2382 empty-base result. Current lifecycle evidence now proves the owned 8559 path reaches eZw but is rejected by copied-book action metadata before successful copy construction; client behavior remains unverified. They must not be read as proof that the Zobal spell is accepted.

## Current runtime route coverage and evidence gaps

The Oct. 10 route matrix (`class-effect-route-inventory-20261010.json`, SHA-256 `90776e182beda6754b36111604990bdf7bb5f5ec1e523d8eac35d19670cf88a6`) reports 161 registered families and 23 construction-gated families globally, with no unregistered families in the matrix scope. A graph walk from 8559's historical roots reaches 40-plus effect families; of special relevance, family 28 is registered, family 330 is registered, family 304 is registered, family 649 is registered, and family 1002 is registered but gated on summon authority. The matrix itself warns that registration does not verify parameters, guards, retention, delivery or lifecycle.

The Zobal inventory's mechanic requirement rows that touch 8559/413075/413347/3769 remain `unverified` in the dated requirement artifact. They include spell-8559 casting conditions (`GetOwnTeamStateCountInRange`, `HasState`, `IsBreedId`), family 649 and 1002 semantics, state-3769 application/initialization/delivery/removal, and `fcE` target-selector behavior. This is a coverage status, not proof that the corresponding production code is absent. The current test tree has shared copy book, appearance/equipment and constructor tests. A current owned-Zobal 8559 lifecycle fixture now exists, but its result is rejected at 413075 for the copied-book metadata gap above; it is not an accepted lifecycle.

### Proven missing behavior versus unverified behavior

- **No current catalog gap shown:** roster/innate IDs reconcile; all five extra grant and casting records are present; no grant effect definition is missing.
- **No absent runtime family shown:** the relevant grant, state, kill and eZw routes are registered; family 1002 has a documented summon-authority construction guard.
- **Proven copied-book metadata gap:** [native-class-copy-book-flags.json](../../.runtime/zobal-copy-metadata-20261010/native-class-copy-book-flags.json) contains 821 source-authored action references versus 813 in the previously consumed snapshot; the eight additions are 4956, 4957, 4958, 5144, 5145, 5146, 5237, and 5621. The source export marks these SUPPORT (`native_element: 9`) with `native_elemental_copy: false` and `native_neutral_copy: true`. In the actual Zobal 8559 lifecycle fixture, family 1002 fails at effect 413075 with `Missing scoped native copied-class action metadata`; the actor snapshot is preserved. This is a proven eZw integration failure, distinct from the already-complete class roster/grant catalog. The failure row does not record which action reference caused the metadata lookup, so do not attribute it to one of the eight individually without a follow-up trace.
- **Verified runtime limitation:** persistent/retained eZw descriptor handling is explicitly rejected. This matters only if native execution reaches the handler as retained; the pinned 413075 route is immediate, so this is not presently a proven defect for 8559.
- **Proven validation gap:** current evidence has no complete Zobal cast showing mask grant selection, mask replacement, passive changes, and 8559 kill/create/copy-book/state/packet lifecycle. Individual feature rows remain pending/unverified.
- **Not established as a defect:** a construction-gated route, historical `reachability: unknown`, an empty copy-profile book, or an unverified class requirement does not by itself mean that source data or a handler is missing.

## Focused acceptance sequence

Use a current owned Zobal actor with a saved deck and separately verify passive 7104 absent/present. Start a fresh fight, inspect innate state 3769 and each granted action/level/slot, then cast 7081, 7082, 7083, and the selected 7081/7226 variant in turn. After each cast, assert that its primary state is applied and that only the other bonus states are removed; do not require old primary states to be removed, because the native roots do not encode that. Assert the bonus state on an eligible allied player character/companion inside the radius-four branch area, not on the caster; change passive 7104 only through an authorized deck update/new fight and confirm grant replacement semantics rather than simply observing a second action in the book.

For 8559, first evaluate the native cast predicate with (a) the original Zobal and no team state 3813, (b) the original Zobal with its copy alive, and (c) the copied actor carrying 3813. Record the exact runtime `GetOwnTeamStateCountInRange` value and cast decision; only attempt a second cast in cases admitted by the predicate. For every admitted cast, record root order, old profile-2382 copy death/retirement, new actor identity/owner/cell/profile, state 3813, copied current/max values, appearance and client packet, and the new actor's action book compared with the source's exact owned deck plus grants. Exercise illegal target, missing slot, child/root failure, owner death and fight end; rejected transactions must leave resources, actors, states, grants and packets unchanged. Finally change/remove the passive deck and reconnect or start a new fight to confirm cleanup and no stale grants/copies.

## Provenance

- Current roster/grants/innates: [published-catalog-reconciliation.json](remaining-classes-20261010/published-catalog-reconciliation.json), active release revision above.
- Current class inventory: [14-inventory.json](remaining-classes-20261010/14-inventory.json), SHA-256 `46be40aebfa0a0a1bcb412d4a88da88d93595d1faaec4bf4db6a95d650bac988`.
- Detailed native structures used for exact IDs/criteria/parameters: [class-native-mechanic-graph-20261007.json](class-native-mechanic-graph-20261007.json), SHA-256 `eb234d95103b48090ab752f8c9d88eb4d02dea5773234401a20f977888a3416e`; historical structure only.
- Current runtime routes: [class-effect-route-inventory-20261010.json](class-effect-route-inventory-20261010.json), SHA-256 `90776e182beda6754b36111604990bdf7bb5f5ec1e523d8eac35d19670cf88a6`.

## Additional offline runtime checkpoint

The active PostgreSQL catalog was re-read on Oct. 10 at revision `a3272ec3b722c5923cdfb619041bab41a14c85d9838364440e5f71b9b2254095`. A positive test in [test_combat_hud_producers.py](../../server/tests/test_combat_hud_producers.py) casts owned spell 7087 through `prepare_server_spell` on map 1134. It uses native terrain and QI masks, an empty floor cell exactly six cells from the Zobal, and an enemy adjacent to that destination; the accepted effect moves the caster to the selected cell. The focused test passed. This proves one legal server-side Acrobatismo path, not its failed range/adjacency cases or client presentation.

Spell 7086 remains unverified in an accepted cast. Its active predicate requires an off-play, non-enemy target without fight property 66; a positive case must first register the ally's death through a real damage/death producer. HP zero or a manually assigned off-play flag is not sufficient evidence. Passive reactions 7095, 7103, 7106, and 7113 remain source-inert at the listed reaction roots where the active catalog criteria contain literal `False`; this is preserved native behavior, not a runtime defect to repair. Supported branches on passive 7097 (facestabbed healing for trigger values `<= 30000` and `> 30000`) and passive 7099 (armor `<= 0` or `>= 1`) still lack positive owned-passive cast evidence and remain unverified. Roster or route registration alone does not establish functional coverage.
