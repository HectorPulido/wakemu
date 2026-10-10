# Ouginak full manual acceptance — draft 2026-10-10

Pending completion of the offline implementation gate. This card is not a claim of live acceptance. Native breed15; retain tooltip values at the actual level/build as the numerical authority.

## Preparation

Use an Ouginak test character outside combat, without optional passives for the first run. To unlock the complete catalog on a test character, `!nivel 200` raises level permanently; return to character selection and reconnect. The command cannot lower level. Rotate legal decks between fights, never equip all spells/passives at once. Keep a second allied player available for support/ownership checks. Enter each command separately in exploration and finish a fight before creating another group.

## Core system

1. Enter `!mob 4 8 3`, engage and Ready. Confirm Presa6283, Wauwau6286 and Uginikántropo6855 appear through their native grants, without equipping them as ordinary deck entries. Record AP/MP/WP, the class resource and state icons.
2. Mark a living enemy with Presa. Confirm legal costs and a mark on that exact actor. Attack marked and unmarked targets and compare the tooltip's conditional effects. Try an invalid target: no resources or state should change.
3. Use ordinary elemental attacks over several turns. Confirm exact HP/armor/resource changes, durations and passive reactions. Dead targets must stop blocking cells and LOS; their animations must belong to their own actors.
4. Summon Wauwau on a legal empty cell. Confirm team/controller, one timeline actor, book6291–6294 according to native eligibility, own resources and actual turn completion. Use its legal actions, then finish a round with both owner and creature. No switched player bar or stalled turn.
5. Place allied actors within two cells of the Manada target, then cast Manada. Check positive class-resource gain (the tested five-ally context gives20). Cast the granted Uginikántropo with positive resource. Confirm state7526 persists and the advertised modifiers apply. Cast Amaine on a legal allied target to consume the resource; at zero, state7526 and its retained visual effect must disappear. Test again without resource: do not mistake immediate native zero-resource exit for a persistent-form failure. The native presentation evidence is a height modifier; a complete model replacement is not an established acceptance requirement.
6. Equip Persecución before the fight. Gain at least5 class resource through Manada, then cast Persecución on a legal target. Check the caster's Perseguidor state and the target's Perseguido mark. Attempt the granted Perseguidor on a different legal occupied target, without that caster's Perseguido mark. Compare against its current tooltip; the positive movement/effect context is still under offline verification. Below5 resource or without the caster state, the action must stay rejected without consuming anything.
7. With a second ally, use Manada in a legal group context. Confirm the ally-count condition, affected actors and class-resource gain. Compare a lone-caster negative case.
8. Kill the marked enemy, remove/lose Wauwau, finish or abandon a fight, and start another. Confirm mark/resource/grants/summon count and occupancy reset according to the native lifetime. Reconnect during an active fight and verify actors, books, appearance and remaining states are preserved without duplicates.

## Full roster and passives

Suggested legal deck rotation (eight spells each, with some shared setup spells):

- Deck A: Disturbio, Zascadilla, Barrido, Plaga, Apaleamiento, Contusión, Ruptura, Moloso.
- Deck B: Emplomado, Rayadura, Cuchillada, Tirón, Gran Can, Fracturahuesos, Bulla, Bote.
- Deck C: Cazador, Persecución, Colmillo, Amaine, Manada, Disturbio, Bote, Moloso.

For each attack, record starting AP/MP/WP, target HP/armor and displayed state; cast once and compare exact costs and deltas against the current tooltip. Repeat the conditional part on marked/unmarked targets as applicable. For Cazador, use an occupied target two to four cells away on the same row/column, with LOS and a clear landing/path context. For Colmillo, separately test a legal target behind an obstruction because the native definition does not require LOS. For movement spells, include occupied landing cells and map edges; rejection must not move actors or spend resources.

Use the [full inventory](remaining-classes-20261010/15-review.md) to rotate all21 owned actives and all19 passives through legal decks. For every passive, compare a new fight with and without it, perform its advertised trigger and a negative control, and record exact state/resource/HP/armor changes. Include both critical and normal hits, allies/enemies, front/back, empty/occupied cells, map edges and blocked LOS. Do not interpret a disabled prerequisite branch as a regression until its native conditions are met.

## Regression controls

After shared changes, repeat Cra beacon activation/desbalizaje, Iop combos/banner, Sacrier damage/sacrifice, Eniripsa ally healing and Osamodas capture/summon/dragon. Validate a two-character PvE fight from Ready to victory and a friendly duel/abandon, with no disconnect, stuck first turn, lost bar or stale fight membership.

## Known review limitations

This document does not certify that the current world image includes this checkout. Deployment is operated by another workstream. Positive Cazador/Perseguidor contexts, controlled Wauwau lifecycle and Presa team uniqueness remain under review. A generic initiative-stat synchronization defect was found during global-passive4956 validation; it is not yet marked fixed here. Start the core manual pass without optional passives, then test passives only after the relevant build is confirmed.
