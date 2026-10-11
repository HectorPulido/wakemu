# Aniripsa and monster integration inventory — 2026-10-10

## Current authority and review

Review uses published PostgreSQL release `c97c921c35f4b1f808f0bc84970cba2aa09652763394440429a85e9f7f0fee46`. The monster workstream deployed complete shared images; see [deployment evidence](../monster-combat/DEPLOYMENT_20261010.md). This follow-up performed offline validation and changed tests/audit tooling only; it did not restart or deploy services.

Cunejo ability 5459 had a real shared resolver defect. A transmitted explicit recipient with mask zero was expanded into two actor bindings. The upgraded Cunejo damaged the injured player twice before healing and correctly hit the corpse guard. Native Qe.a with non-null PV and aZX=false uses Qe.g singleton selection. The other agent's narrow resolver correction restores one binding: the existing level-200 assertion ends at 69 HP (100 minus 63 plus 32), without bypassing corpse guards. See [native trace and bytecode](../monster-combat/ANIRIPSA_5459_TRIAGE.md).

The historical resolver assertion expected the conflicting fanout. This review explicitly corrects that expectation with the independently recovered native contract and adds recalculation=true, absent registered recipient and caster-override boundaries. This is a documented behavioral expectation correction, not an unchanged-test claim.

A repeated Cunejo death-area test exposed a separate audit helper error: controlled end-turn messages used the actor counter rather than current_wire_turn. Summon insertion/removal makes these counters diverge. The offline helper now sends the same authoritative round as production clients. Gameplay assertions and production turn validation remain unchanged.

## Aniripsa inventory

The class has 21 owned actives, 20 passives, three granted actions (7977 Contra Natura, 7978 Cunejo, 7979 Repulsion), two innate seeds, four summon profiles and five unique summon actions. The original full register is in [complete inventory](aniripsa-complete-review-20261009.md); its early missing-evidence entries are superseded by [implementation evidence](aniripsa-implementation-review-20261009.md) and [passive consequences](aniripsa-passive-source-pipelines-20261009.md).

| System | Available evidence | Remaining acceptance |
| --- | --- | --- |
| Direct damage and healing | Allied/self/enemy, normal/critical branches, caps and rejected casts | Equipped builds, all numeric/map permutations |
| Contra Natura | Natural grants, toggle, costs, elemental branch matrix | Live book/rendering and reconnect combinations |
| Five marks | Actual consequence, consumption and death reactions | Cross-owner and simultaneous nested deaths |
| Twenty passives | Scoped positive semantic tests, not merely installation | All build/radius/level combinations |
| Resurrection | Actual KO, revival, QI/timeline restoration and second death | Restored live-client action and reconnect |
| Cunejo profiles | 182 base, 1775 upgraded, 5528 dark, 5533 upgraded dark; actual ownership, book and actions | Visual upgrade, multiplayer/hero switching |
| Summon actions | 986, 5457, 5458, 5459, 7988 across native profile books | Remaining spatial/build permutations |
| Cunejo death area 1814 | Owner healing, guard renewal, subsequent death replaces old area | Two distinct owners' overlapping areas and client presentation |
| Other retained effects/areas | Movement releases deferred healing; Fuente expiry; enemy turn damage | Disconnect and alternate timing combinations |
| Shared combat lifecycle | Automated transaction/turn/summon protections | Complete two-client PvP/PvM, surrender, reconnect, dungeon finish |

Cunejo profiles are `inventory_only` in the ordinary-monster activation report. That report controls newly expanded ordinary NPC spells; it does not mean existing class-controlled summon actions are disabled. The actual class transaction tests are the relevant evidence for those actions.

## Monster inventory and outstanding work

The extraction contains 2,874 monster references, 3,091 distinct owned spells, 4,143 casting definitions, 6,129 states and 1,436 areas. Of 69 candidates whose entire native level range is below 10, 30 are activated and 39 remain pending. The other 2,805 references are inventory-only. These are monster references, not numbers of working spell effects.

Twenty-one pending low-level references lack supported ordinary-NPC initial-state construction. Other pending cases involve casting authority, condition/resistance semantics, encounter scenarios or resources. Higher-level/epic activation, additional NPC resource-payment event completeness, copied-book metadata repair and disputed broad-suite expectations remain separate work. See [complete machine inventory](../monster-combat/ACTIVATION_STATUS.json) and [failure progress](../monster-combat/FAILURE_FIX_PROGRESS.md).

## Fresh verification

- Aniripsa full suite: 54 executed; initial run had 53 passes and one death-area helper error. After the authoritative-round helper correction the same death-area test passed independently. Do not describe the initial run as all green.
- Cunejo final focused gate: 3/3 passed (four profiles/books, all owned actions and death-area lifecycle). The full 54-test suite was not repeated after the helper correction.
- Resolver/direct-target: 22 unique tests passed, including explicit singleton, null target enumeration, aZX recalculation and invalid recipient boundaries.
- Cra beacon, Feca protection/grant and Sram focused modules: 11 tests passed against the current active revision. This does not certify every Sram trap scenario.
- No class acceptance count is increased by this review; user-provisional acceptance remains 6/18.

A complete manual acceptance remains in [Aniripsa manual battery](aniripsa-manual-acceptance-20261009.md). Prioritize four Cunejo variants, sacrifice 5459 on an injured owner, summon death/reinvocation, overlapping owner areas and complete two-client fight completion. Record fight ID, deck and before/after HP for any discrepancy.

## Follow-up: turn-end death and replacement-aware regression

A later complete-suite run exposed a shared runtime error: turn-end reactions could kill the current controlled summon, settle its death and advance the timeline, after which `RuntimeMessages.end_turn` attempted to end the old actor again. Owned and server paths now reuse the existing defeated-turn synchronization only after a verified dead/out-of-play actor and exactly one advance; unsupported alive/reentrant transitions reject atomically. The two new regression methods and nine existing runtime-message tests passed.

The four-profile area regression also conflated transformation with death. Native dark state8029 has event1001 listener368090, whose children withdraw via368091 and recreate profile5533 via368093, then install3892 via368095. The previous test stopped at the retired original UID although its replacement remained alive. The revised bounded legal-cast/turn loop follows the actual living owned replacement and accepts completion only when the tracked actor has original KO1010/death1013 delivery evidence. Area1814, owner7, exact corpse cell and affiliation0 assertions remain unchanged. The final focused four-profile rerun passed; this fixture correction is not a claim that withdrawal produces death events.

The replacement-aware rerun passed the baseline and three of the four Nature profiles. Normal upgraded Cunejo still reached its unconditional native end1002 listener371814→371815/family332 before a lethal hit. This is protected withdrawal, not a missing death notification. The remaining positive fixture now selects a lawful fresh aptitude sheet before snapshot construction: Strength26×40 plus23×10, Luck13×49, Major2×1. Resources are derived through `combat_resources`; no live HP, resource, state or event is injected. This qualifies a stronger melee/berserk hit before protected expiry; the final focused verification passed with actual KO/death and area assertions. Default fixture allocations remain empty.


The bounded observer established why the first strong-build trial still expired: Intelligence HP allocation raised caster maximum7350 and upgraded summon maximum3308, while its actual630 hit dealt1347. Native168335/family913 reads source maximumHP and transmits30%;168336/family16 assigns1.5HP per transmitted level. Removing only the HP allocation preserves the native damage build and original caster maximum2450, so upgraded HP is1103. The original injured caster remains below half without HP inflation. The final focused run passed the lawful lethal path before end1002; it did not change runtime death or withdrawal semantics. The1103 figure is the source arithmetic prediction, rather than a separately captured final-run measurement.

Final fresh verification: the complete profile method passed all subcases after the legal native budget and HP-build corrections. The separate protected-expiry negative also passed: real end1002→332 retires the summon without KO1010/death1013 or area1814. The positive method preserves actual death-delivery, corpse-cell, owner, affiliation and area assertions; it does not substitute a protected withdrawal for a kill. No production death/area semantic change was needed. The shared pre-end synchronization remains the independently verified runtime correction described above.
