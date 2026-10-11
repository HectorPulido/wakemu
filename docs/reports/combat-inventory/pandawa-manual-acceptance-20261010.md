# Pandawa complete manual acceptance — 2026-10-10

This battery verifies the client and shared combat system after the automated class gates. It is not a claim of manual acceptance. Native breed12; exact costs, ranges and level-scaled values must agree with the current native tooltip. Server coverage and its limits are in [the implementation inventory](pandawa-implementation-inventory-20261010.md).

## Preparation

Use a disposable Pandawa outside combat. Enter `!nivel 200` if necessary, then return to character selection and reconnect. This command raises level permanently and cannot lower it. Equip spells and passives through the ordinary book; never add granted spells, states, HP, AP or summons with a test command.

For a short PvM fight enter `!mob 4 8 3` in exploration, engage the resulting three profile4, level8 monsters and Ready. These are weak enemies: recreate the group between tests rather than expecting it to survive a complete level200 attack rotation. Keep an allied player available; use a friendly duel through the client's normal challenge interaction for opposing-player comparisons requiring several turns. Finish or surrender the current fight before creating another group.

Rotate these legal ordinary decks between fights; the five innate actions below must appear automatically:

- A:4702,4703,4704,4705,4706,4707,4708.
- B:4709,4710,4711,4712,4713,4714,4715.
- C:4716,4717,4719,4720,4721,6844,6845.

Record a screenshot of AP/MP/WP, the current actor and the spell bar at Ready. Expect Barrel4718, Karcham6847, Chamrak6848, Toneportation8591 and Drunkenness8592 as native grants; do not put them into ordinary slots manually.

## One complete combat system pass

1. **Ownership and carry.** Summon a barrel on a highlighted free cell, carry it, move one legal cell and throw it to a highlighted destination. The barrel must follow the carrier while carried and occupy exactly the landing cell afterward. Repeat with an allied player, then an enemy in the appropriate fight. Try an occupied/invalid destination: no resources, positions or carry references may change. A different Pandawa's barrel must not satisfy an own-barrel restriction.
2. **Full active rotation.** Across decks A–C, cast every ordinary spell once in a legal context. Compare costs, target, damage/healing, displacement and state changes with its current tooltip. Test4714,6844 and8591 with an actual owned barrel; test4705 while carrying it and without carry. Test relevant linear/range/LOS restrictions and a rejected destination. No rejected action may spend resources or block subsequent legal actions.
3. **Drunk lifecycle.** Cast8592 on self and separately on an ally/enemy where legal. Inspect Drunk3300 and Tipsy6107, then finish actual turns until the inverse/cleanup transitions occur. Do not expect similarly named states to coexist beyond their native clocks. Temporary range/cost/modifier changes must disappear when their source expires.
4. **Milk Cloud.** Cast4708 on the actual owned barrel. Check the cloud belongs to this Pandawa, its eligible healing/cell behavior matches the tooltip, and it expires on real turns. Have a second player approach/use their own cloud: owners must not be exchanged. Client glyph healing and overlapping clouds are manual evidence beyond the automated creation/ownership/expiry case.
5. **Deaths during carry.** Have an opposing player kill the carried actor, then repeat killing the carrier in another fight. Carry animations/references must clear, the surviving actor must be on a coherent legal cell, and the dead actor must not block movement/LOS. Continue at least one full round afterward.
6. **Reconnect and finish.** Reconnect during an actual carry and again after a barrel is thrown. Both clients must retain the correct actors, owner bars, HP/resources, carry relationship and current turn without replaying damage. Win a two-player PvM fight, return to exploration, start another fight, then repeat surrender. No duplicate barrel, stale pair, stuck turn/ACK, missing actor or empty owned bar may remain.

## Passive comparisons

Change one passive at a time outside combat; preserve the remaining build and repeat the same eligible sequence without it. Rotate through all17 passives rather than equipping them simultaneously.

| Passive | Actual sequence and expected consequence |
| --- | --- |
|4722 Cocktail|Use8592 on self: native Drunk damage+50 changes to healing+25 with the passive.|
|4723 Master of Drunkenness|Pay the advertised extra8592 cost and verify its use interval; advance an actual turn before repeating.|
|4724 Bottomless Barrel|Leave an owned barrel adjacent and unheld at owner end: it is automatically carried with the passive; owner direction is preserved.|
|4725 Aggressive Barrel|Leave the barrel unheld with another ally and enemy around it. At owner end it is destroyed and nearby eligible actors receive Tipsy; a carried barrel is excluded.|
|4726 Milky Instinct|Inspect native9356 countdown on the actual barrel across owner starts:3→2→1, followed by its native kill. Compare a baseline barrel.|
|5148 Bambutella|Use Drunk with positive starting tackle: at level200 dodge gains400 and tackle loses400. Signed tackle can become negative; do not expect a zero clamp.|
|5149 Cyanosis|Apply Tipsy to an enemy, end the owner turn, then start the recipient: observe3690 damage and native6107/3690 cleanup.|
|5151 Pandemic|Receive an actual attack while the attacker is Tipsy and compare incoming−20. Use4704, which preserves Tipsy before damage, for the outgoing bonus comparison.4702 removes Tipsy before its damage and is not a valid positive bonus probe.|
|5152 Barrel Wisdom|Put the actual barrel between Pandawa and an otherwise visible target. With passive the barrel is transparent to LOS; without it the same barrel blocks. Walls/other actors still block.|
|6846 Tipsy|Become Drunk, carry an enemy and compare the native legal throw range against the baseline.|
|8595 Firm Step|With an owned barrel present, compare8591's native LOS/linear targeting flags and highlighted legal cells.|
|8596 Tunnel Vision|While Drunk receive matched attacks at melee and distance: final modifiers−20/+20 respectively, compared with no passive.|
|8597 Fermentation|Carry the barrel through owner end: gain native armor. A direct back hit clears it; an otherwise matched nonback hit need not fully clear it.|
|8598 Last Drop|Create a WP deficit by summoning, apply owned Tipsy to an enemy and remove it with4702: baseline restores1WP; passive replaces that with armor equal to5%maxHP.|
|8599 Cyanotic|Apply8592 to an injured ally and end the owner turn. At recipient start observe healing and6107/9366 cleanup; baseline has no conversion healing.|
|8600 Pandaperitivo|Summoning away from self already activates this passive and marks9368. Wait through its actual expiry before the throw comparison. Then carry and throw the barrel using4705 with an ally/enemy adjacent to the landing cell: eligible nearby actors get Tipsy and the barrel gets9368. Repeat carry→throw during the same legal resource/turn window: the restriction prevents the repeated passive children. The marker expires at its native boundary; do not expect permanent suppression.|
|8601 Last One|End with an aligned barrel at a legal attraction distance: owner is attracted toward it. Put an actual blocking actor in the path in a control case; no actor may pass through the blocker.|

## Failure recording and acceptance

For any mismatch record time, fight ID, character, spell/passives, target cell, current actor, starting/ending AP/MP/WP, HP/armor and visible state/message. Keep the fight available if possible. A legitimate native prerequisite rejection is not a broken spell; spending resources on rejection, incorrect recipients, desynchronized turns or a disconnected session is a failure.

Conclude with short Cra beacon/Desbalizaje and Iop combo checks, then a two-owner PvM Ready→actions→reconnect→victory and a friendly-duel surrender. This guards the shared systems alongside Pandawa. Manual acceptance remains pending until the user completes these steps.
