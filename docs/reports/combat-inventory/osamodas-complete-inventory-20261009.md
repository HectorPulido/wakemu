# Osamodas complete inventory — 2026-10-09

Scope: inventory, current catalog/source inspection and bounded offline regression only. No gameplay implementation, character/database mutation, service operation, deployment or restart. The user provisionally accepted Aniripsa: Cra, Iop, Sacrier and Aniripsa are **4/18**. Osamodas is the next class under review, not an accepted fifth class.

## Authoritative scope and evidence

Native breed2, published revision `a1f84ebac9f26181f558e3adced85252d7892685f6a051f2b05f6a4b8d3e9b38`.

| Scope | Current inventory |
|---|---|
| Owned actions | 21 actives and17 passives; do not assume every class has20 passives |
| Class extra actions | 8: Invocation7348, Dragon7349, Gobgob/Jamajam7350 and7351–7355 |
| Seed roots | 48, including the two innate roots separately from owned actions |
| Current class dependency closure | 983 effects,43 states,93 effect families,52 spell references,4 areas and2 statically referenced summon profiles5347/1620 |
| Current structural omissions | No missing definitions or unregistered effect-family bindings in this class closure |
| Dynamic captured dependency export | Historical source-backed export:33 capture-eligible profiles plus8 nested profiles;195 spells,178 states,21 areas,2156 effects. This domain is separate from the class closure and overlaps it; do not add the figures as disjoint totals |
| Current bounded regression | 60 tests passed,0 failures/errors/skips;0.781s. Component fixtures, not a complete class/client pass |

[Every spell, passive, grant and state](osamodas-spells-states-inventory-20261009.md), [machine-readable dependency register](osamodas-spells-states-inventory-20261009.json), [summon/source lifecycle inventory](osamodas-summons-inventory-20261009.md), and [runtime risks, exact regression command and boundaries](osamodas-runtime-risk-inventory-20261009.md) are the detailed registers. The captured-domain figures retain their historical scope until separately reconciled against the current published catalog; static closure alone cannot enumerate a selected character's captured roster.

## What is already implemented

The repository has an actual owned ten-slot Symbiot component, native codec, selected slot/availability, persistence/hydration, eligibility-guarded capture320, descriptor-based creation324, native scaling, summon-owned ability books and control transitions. Family307 handles static fresh entities separately. Family859 handles its native HP/KO/property transition; retirement, spatial removal and slot availability are separate responsibilities.

Current captured retirement calls `release_captured_slot_on_retirement` from `combat_summon_retirement.py`; the older individual-slot report's statement that integration was pending is historical. Do not implement the same reset again or release every slot when only one summon dies. Current departure handling and checkpoint/persistence paths are detailed in the summon inventory.

Existing offline evidence includes a real capture mark followed by a lethal attack, a committed324 summon with a controlled turn and three independently committed profile5347 abilities, and7349's transform/return state round trip. These are separate scoped observations; none establishes that every species, action bar, passive combination or reconnect works in the client today. The prior full-book fixture even selected an owner as an ability target: that is evidence of that bounded branch, not enemy-damage acceptance.

The class is therefore not a blank implementation. The work remaining is primarily class-semantic reconciliation and integrated validation, with fixes only where a current failing path is established.

## Prioritized unresolved work

Each item is a validation gap unless explicitly identified as a source capability limitation. Missing acceptance is not automatically missing code.

| ID | Priority | Area and required closure |
|---|---|---|
| OSA-01 | P1 | Capture and roster: legal living mark followed by actual death; ineligible target, repeated same-profile captures versus duplicate death delivery, full ten slots, selected occupied/empty slot, exact cost once, rollback and persisted reconnect without duplication. |
| OSA-02 | P1 | Complete invocation lifecycle: selected owned descriptor→324 creation→correct owner/controller/team/level/QI/count→actual own turn and book→natural death/recall/finish→exact slot release→resummon. Verify all transitions together. |
| OSA-03 | P1 | All captured species and nested dependencies: native ability UID, level selection/scaling, characteristics, initial states/properties, legal target rules, nested entity ownership and cleanup. A successful profile4 or5347 is not all33 captured profiles. |
| OSA-04 | P1 | Jamajam7350, static profiles and7351–7355 auxiliary actions: actual grants and recipient books, auras/areas, exchange, motivation and Nova; prerequisites, lifetime and cleanup. Never add conditional grants to a fabricated ordinary player deck. |
| OSA-05 | P1 | Dragon7349/state7123: entry/return, transformed spell branches, damage/healing/mastery, interaction with existing summons, book refresh, cooldown, finish/death/reconnect. Existing state round trip is not full form acceptance. |
| OSA-06 | P1 | All21 owned actives: normal/critical, owner/ally/enemy/summon/empty-cell branches as legal, actual damage/support/displacement/transfer and numerical outcomes. Specifically replay historical7317/7318 condition/orientation leads against current code before calling them bugs. |
| OSA-07 | P1 | All17 passives and43 class-closure states: actual positive and negative triggers, caster versus summon source, thresholds, caps, durations, removal, consumed bonuses, scaling and legal combinations. Ready installation does not establish passive behavior. |
| OSA-08 | P1 | Shared combat/map correctness: corpse occupancy/LOS, movement, blocked destinations, height, map boundary/4900-cell cap, count registration, recursive reactions, stale retained managers and packet actor identity. Reuse shared contracts without changing Cra/Iop/Sacrier/Aniripsa semantics. |
| OSA-09 | P1 | Multiplayer/recovery: two players and controlled summon, first turn, ACK, disconnect/reconnect, surrender, normal victory/defeat and dungeon progression. No stuck turns, disconnected second character, ghost combat flags or lost enemy group. |
| OSA-10 | P2 | Explicit handler limits: retained324 creation and retained859 removal are rejected as unaudited in current source. Determine whether an actual reachable class/captured graph requests those variants; do not bypass legitimate authority checks. |
| OSA-11 | P2 | Presentation: model/animation, correct death recipient, summon action bar, transformation, slot availability, reconnection snapshots and return-to-world UI; packets or HP deltas alone do not certify these. |

## Shared work to reuse and protect

Cra's summon recognition/count correction is a mandatory regression boundary: native `dTE`, direct controller, in-play/death status and property103 must agree after creation, stat updates, moves, turn changes, reconnect and retirement. This explicitly preserves Hector's request to carry the Desbalizaje lesson into Osamodas and every invocation route.

Cra area enumeration, Sacrier relationship selectors, and Aniripsa explicit healing recipients and owned-area bit64 selection apply through the common dispatcher when their native selectors match. Aniripsa protected ephemeral-summon replacement and criteria-before-recursion guard are relevant to replacement/nested reactions. They are shared infrastructure, not a reason to copy another class's IDs or invent Osamodas formulas. Preserve initial fresh307 event2130 versus captured324 event0.

Prepare/commit isolation, RNG rollback, exact source identity, plain checkpoints, owned book authority, state removal and settled-death spatial cleanup must remain general. Existing regressions from all four provisionally accepted classes should accompany any future shared-engine fix.

## Complete acceptance plan after implementation

The existing [capture-to-reuse test card](manual-osamodas-system-20261008.md) supplies exact commands and legal profile4 setup. Its Prueba Osamodas character13/account setup is historical and must be checked before using it; this inventory did not create, level or change a character.

The full acceptance must additionally rotate legal decks through all21 actives and17 passives, test natural/dragon and Jamajam branches, and exercise captured creature actions rather than only the owner's attacks. Use a player ally and enemies to cover support/hostile branches. Include full/empty roster and foreign-owner negatives, blocked cells and LOS, natural death/recall/slot reuse, nested summons, failed-child rollback, then two-client PvP/PvM and dungeon/reconnect/finish. Record combat ID, exact action/passive/profile/slot, source and target, resource/state/HP before and after, timeline/book and logs.

No overall gameplay percentage is assigned. The structural class closure is complete for its measured scope; semantic and live-client coverage is not yet complete. The inventory is ready to guide implementation and acceptance without labeling every untested item a reproduced defect.
