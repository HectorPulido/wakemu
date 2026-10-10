# Osamodas complete manual test battery — 2026-10-10

This is a test plan, not a claim that Osamodas has passed. Inventory is complete; class-level implementation acceptance remains pending. No service or character changes were performed to prepare this document. Commands were checked against current test-console code and the published captured-profile catalog; commands here are for Hector to execute.

## Preparation

Use an Osamodas test character, outside combat and outside a haven bag/dungeon. Enter `!pos`; if in a dungeon, use `!exitdungeon` first. On a test character below250, enter `!nivel 250`, then return to character selection and reconnect to refresh spells and points. This is a permanent level increase; the command cannot lower level. It is optional for the low-level capture checks, but enables every class passive/active for the full battery.

Start without passives and with a known equipment/build configuration. Rotate legal decks outside combat; never attempt to equip all actions or passives at once. Use a second player ally for support and ownership checks. Record AP/MP/WP, HP/armor, state levels, turn and selected captured slot before and after each action. Numerical assertions must use the tooltip at the actual spell level/build, including conditional targeting and form; inventory nominal level200 costs are not universal level250 expectations.

`!mob PROFILE LEVEL COUNT` creates a world group; it does not put a creature into the Symbiot. Each command must be entered separately in exploration. Finish one fight before creating the next group.

## A. Capture and persistence

1. Enter `!mob 4 8 1`, attack the new group and press Ready. Invocation7348 and Dragon7349 must appear through their legitimate combat grants.
2. On your turn, cast Invocation on the living enemy BEFORE any lethal attack. Without modifiers, previously verified mark payment is1AP/0MP/0WP. Capture state7128 should be present; the creature must not appear in the roster yet.
3. Kill the marked creature with a normal spell, for example Tormenta de Arena. Without modifiers its previously verified payment is4AP/0MP/1WP; follow the current tooltip if the build changes it. Exactly one entry is added after death, the first empty slot is used, and combat ends normally. No command kill/HP editing.
4. Reconnect. The entry must remain exactly once with the same selected slot. Capture a second species using `!mob 41 10 1` and repeat. The first entry must remain intact and a second slot must be filled.
5. Optional duplicate-profile test: capture another profile4 in a separate fight. Current native descriptor semantics permit separate same-profile entries; expected one additional slot per actual capture, not duplication from a single death. Do not fill all ten slots until core tests finish.

## B. Summon, control, death, recall and reuse

1. Enter `!mob 4 8 3`. Ready, select the first captured entry, and cast Invocation on a legal empty cell. One allied summon appears; only its slot becomes unavailable, the descriptor stays present, and payment occurs once according to the tooltip. Other slots remain unchanged.
2. End your turn. On the creature's actual timeline turn, move one cell and use each legal own action against its permitted target. Profile4 has native book549/7359/7360/7361; names/visible eligible actions are authoritative. The owner retains the owner's bar; the creature uses its own AP/MP/WP. A target-specific action being disabled is not automatically a defect.
3. End the creature's turn. Both owner and enemies continue, with no0-second deadlock or switched actor identity. Repeat two rounds and change selected roster slot once during an owner turn; selection must not transfer control or modify an already deployed actor's identity.
4. Use the Invocation recall branch on the owned deployed creature when the tooltip permits. It must be removed through the legitimate lifecycle, free its occupied cell/LOS, release only its bound slot and preserve the descriptor. Resummon from that slot on a later legal turn; no duplicate timeline entry.
5. In another fight allow enemies to kill the summon naturally. Keep an enemy alive while checking released slot and cell reuse, then resummon if legal. Death animation must belong to that summon, not a different monster/player. If low enemies cannot kill it, use an appropriate higher-level group from the appendix; do not replace this with administrative killing.
6. Finish a fight with a living summon. Reconnect, start another fight and summon the same entry. All descriptors remain, deployed slots are available again, and no ghost actor/count survives.
7. Negative controls: occupied cell, insufficient resources, deploying an unavailable slot and foreign-owner summon target when disallowed. Each rejection spends nothing and creates no partial actor. Check legitimate summon-count/cooldown restrictions rather than assuming two summons are always allowed.

## C. Every elemental action, natural and dragon forms

Deck1: Cuervo Incendiario7307, Látigo Flamígero7308, Tornado de Llamas7309, Atizamiento7310, Soplido del Dragón7311, Tormenta de Arena7312, Pesante7313, Empalamiento7314, Brinco7315, Golpe del Crujidor7316, Látigo7317, Desplume7318.

Deck2: retain selected controls and add Transferencia7319, Soplido Repulsivo7320, Tornado de Plumas7321 plus the six utilities in sectionD. Respect actual slot capacity.

For EACH of the15 elemental actions:

1. Read current normal-form tooltip; use a legal enemy target and record actual damage/element, resources and any state/displacement/orientation.
2. If its tooltip offers an ally/owned-summon/empty-cell branch, exercise that branch separately with a valid target; compare the stated result, not an assumed damage branch.
3. Enter Dragon7349 by targeting yourself. Unmodified historical entry costs2AP/0MP/0WP and adds7123. Repeat each elemental action against its legal target using the transformed tooltip; verify changed effects/targeting and absence of stale normal-form outcomes. For Pesante7313 in Dragon, target yourself or your own deployed invocation (state7134 from this owner); that actor is the area center. Without Trascendencia Dracónica7333, place the enemy one orthogonal cell from that center to test the native ring1 area. Direct targeting of an enemy player is correctly rejected in this form, even within range.
4. When eligible, return using7349. Unmodified historical return is free and removes7123. Model, book and state must agree; owner and creature still get valid turns.
5. Observe normal and critical outcomes where they occur; damage and any additional critical effect must match the current tooltip and target mitigation. Do not demand an arbitrary raw-damage number independent of gear/resistance.

Focus on Desplume's stated orientation effect: compare the target's facing before/after, then move it on a later turn to detect a merely stale graphic. Test area spells with two valid enemies and one ally/summon in/at the edge/outside their stated area. Only intended recipients change, once per effect.

### Repeated form transitions and visual restoration

In one ongoing fight, repeat at least three complete cycles using the granted action7349: natural form → Dragon → natural form. Wait for each action to finish before the next; use later turns when the action's current conditions require it. At each transition record the model, height, state7123, action bar and time. Both directions must update the visible model without movement or reconnection. Returning must restore the original model and height, remove7123 and restore normal targeting; transforming again must apply the Dragon model and targeting anew. Move one cell and cast a legal action after each transition: neither operation may undo the current appearance. Repeat with each sex on available test characters, and with a controlled invocation deployed. A packet-level pass does not establish that the visible model changed correctly.

If either direction fails visually, keep that fight open for the read-only client inspection and report which transition failed. Do not reconnect first, since that destroys the original renderer state needed to diagnose the intermittent failure.

## D. Six utility actions

Test one at a time without passives, using the legal target identified in its current tooltip:

|Action|Checks|
|---|---|
|Último Aliento7322|Apply its specified state to an eligible target; verify stated benefit and any terminal consequence at the stated boundary. Follow through death/cleanup if produced.|
|Chute Motivador7323|Check summon bonus and exact WP payment; observe duration/expiry, resource caps and repeated-cast restriction.|
|Celeridad7324|Check the stated movement bonus, target eligibility, cost and expiry; rejected blocked movement creates no partial move.|
|Grito Debilitador7325|Check the stated debuff on a legal target and its removal at the stated boundary; unaffected recipients retain stats.|
|Relevo7326|Check stated exchange/movement and any state; origin/destination occupancy, LOS and actor orientation remain consistent. Test an illegal destination without resource loss.|
|Vínculo Animal7327|Check the actual link/transfer branch with an owned summon; verify both HP/state changes and cost, then death/recall cleanup with no surviving stale link.|

Repeat applicable utility branches with Dragon active and a foreign summon present. A foreign target must be rejected whenever the tooltip requires ownership.

## E. Jamajam and auxiliary actions

1. In a fresh fight with an enemy alive, invoke Jamajam7350 through its legitimate grant. Check model, owner, timeline/control and coexistence rules with the captured summon; do not assume it consumes the same count/slot.
2. On the actor to which the native book grants the action, test Intercambio Astral7351, Aura lunar7352, Aura Solar7353, Motivación Estrellada7354 and Nova7355. Check their current target/cost/shape/duration and stated effect.
3. For each aura, position eligible owner/ally/summon inside, on the boundary and outside. Move in/out, end a round, reapply when legal, then remove/kill Jamajam. Effects apply only to eligible recipients, do not stack beyond the tooltip and do not remain after their actual removal boundary.
4. Finish/reconnect and verify no orphan aura, auxiliary player-bar grant or ghost Jamajam remains.

## F. All17 passives

First establish the matching action/result WITHOUT the passive. Equip only the passive under test, repeat with the same build/target conditions, and compare its exact current tooltip benefit AND drawback. Observe at least one qualifying and one nonqualifying event, subsequent turns, expiry and finish. Installation icon alone is not a pass.

Test each: Rabia de Milubo7328; Don Animal7329; Vista de Cuerbok7330; Guerrero Invocador7331; Invocador Solitario7332; Trascendencia Dracónica7333; Espíritu de Fénix7334; Fuerza de Toro7335; Sinergia Animal7336; Simbiosis7337; Potencia Dracónica7338; Estrella de Sur7339; Sacrificio Animal7340; Estrella del Este7341; Devoción Animal7342; Arte del Adiestramiento7343; Reparto Animal7344.

Use the actual tooltip's trigger, rather than inferring mechanics from names: summon creation/action, owner attack, natural/dragon state, summon count, damage/healing/armor, death/sacrifice or aura as applicable. Phoenix/death-related mechanics need an ongoing fight with an enemy alive, not merely the last lethal hit. Repeat representative legal combinations after single-passive cases pass; changes must be attributable to the equipped passives.

## G. Shared map, multiplayer and prior-class regression

1. Two-player PvM: both Ready, complete first turns, owner and summon move/cast, kill one enemy and target/step behind its former cell. No corpse LOS/occupancy rejection. Move/push near an obstacle and map edge; no out-of-map destination.
2. Disconnect/reconnect while the second player remains in combat; both see the same living actors, current turn and correct personal/controlled books. Turns continue, resources and captured slot are preserved.
3. Separate fights: surrender, normal victory and defeat. Both clients return to exploration, clear combat bars/party swords, can start another fight, and retain captured descriptors. In a dungeon, victory advances correctly; surrender/defeat must not silently consume the required undefeated group.
4. Friendly PvP: Ready both clients, first turns, summons, normal end/surrender; no participant-authority error or disconnect.
5. Cra control: own fire beacon reacts to a legal fire hit and damages the intended enemy; Desbalizaje works with its actual prerequisites. Iop control: Ráfaga→Ráfaga→Bofetada pushes2 legal cells. Sacrier and Aniripsa: repeat their accepted displacement/link and ally-healing/Cunejo cases; exact full regression cards remain in the inventory folder. These representative client probes complement, not replace, the automated four-class gate.

## H. Full roster and captured-profile coverage

There are ten slots. Test the full-slot negative only AFTER other checks, using a disposable roster/character if needed. Capture one marked creature per actual death until all ten slots are occupied. An eleventh capture cannot overwrite, duplicate or corrupt entries; it must handle the failed insertion according to the actual capture branch without crashing. Do not invent a roster-deletion command; the UI release/rename route has not been certified by this inventory.

The33 catalog profiles below have capture property40 and no prohibition28. Commands use the published minimum level and one enemy; this is native catalog eligibility, not a claim that every species' complete book has already passed. Capture each normally, then test its own book in a later multi-enemy fight. Cover the full domain across separate test rosters if needed; do not overwrite ten slots to fit33 entries.

|Profile|Published minimum level|World spawn command|Native ability references|
|---:|---:|---|---|
|5347|1|`!mob 5347 1 1`|7356, 7357, 7358|
|4|8|`!mob 4 8 1`|549, 7359, 7360, 7361|
|41|10|`!mob 41 10 1`|5770, 5771, 7362, 7363, 7364|
|4079|19|`!mob 4079 19 1`|5808, 5809, 7377, 7378, 7379|
|87|22|`!mob 87 22 1`|1374, 543, 5815, 7392, 7393, 7394|
|4757|40|`!mob 4757 40 1`|6531, 6532, 6526, 6530, 7434, 7435, 7436|
|4510|44|`!mob 4510 44 1`|6195, 7374, 7375, 7376|
|4238|59|`!mob 4238 59 1`|5970, 5969, 5968, 7380, 7381, 7382|
|4728|59|`!mob 4728 59 1`|6423, 6430, 6431, 7398, 7399, 7400|
|1152|69|`!mob 1152 69 1`|1522, 3558, 1525, 7365, 7366, 7367|
|5112|74|`!mob 5112 74 1`|6867, 7386, 7387, 7388|
|4247|85|`!mob 4247 85 1`|6002, 6000, 5999, 6013, 7383, 7384, 7385|
|4741|93|`!mob 4741 93 1`|6508, 6509, 6507, 6502, 7390, 7389, 7391|
|2076|100|`!mob 2076 100 1`|3027, 3028, 3033, 3032, 7425, 7426, 7427|
|2367|104|`!mob 2367 104 1`|3509, 3507, 3508, 7401, 7402, 7403|
|4723|115|`!mob 4723 115 1`|6449, 6450, 6448, 7416, 7417, 7418|
|4229|119|`!mob 4229 119 1`|5953, 5954, 7428, 7429, 7430|
|2988|134|`!mob 2988 134 1`|4252, 4253, 7437, 7438, 7439|
|4886|134|`!mob 4886 134 1`|6659, 6660, 7431, 7432, 7433|
|2577|149|`!mob 2577 149 1`|7395, 7396, 7397, 8003, 8004, 8005|
|3079|149|`!mob 3079 149 1`|4495, 4496, 4497, 7404, 7405, 7406|
|3393|160|`!mob 3393 160 1`|4648, 4649, 4650, 7407, 7408, 7409|
|4922|164|`!mob 4922 164 1`|6749, 6751, 6750, 7410, 7411, 7412|
|5129|175|`!mob 5129 175 1`|6881, 6882, 7419, 7420, 7421|
|3861|179|`!mob 3861 179 1`|5640, 5641, 5642, 7413, 7414, 7415|
|4210|190|`!mob 4210 190 1`|5904, 5905, 5906, 5907, 7440, 7441, 7442|
|5136|190|`!mob 5136 190 1`|6873, 6872, 7422, 7423, 7424|
|5181|205|`!mob 5181 205 1`|7033, 7034, 7368, 7369, 7370|
|5186|205|`!mob 5186 205 1`|7039, 7040, 7041, 7443, 7444, 7445|
|5294|218|`!mob 5294 218 1`|7254, 7446, 7447, 7448|
|5281|220|`!mob 5281 220 1`|7239, 7238, 7371, 7372, 7373|
|5637|233|`!mob 5637 233 1`|8345, 8344, 8354, 8355, 8356|
|5631|239|`!mob 5631 239 1`|8308, 8309, 8357, 8358, 8359|

## Result recording

Report the first failing section/step, time and combat ID if available; exact spell/passive/profile/slot, current form and target; HP/AP/MP/WP/state before and after; screenshot of timeline/action bar/message; whether reconnect repaired or preserved the failure. If one subsystem fails, continue independent sections in a fresh fight rather than treating a partial pass as full acceptance.

Catalog command authority: `combat_captured_profiles.native_captured_profiles`; command parsing/level semantics: `maps/test_console.py`. Historical verified mark/dragon costs and profile4 book: `manual-osamodas-system-20261008.md`. Complete structural register: `osamodas-spells-states-inventory-20261009.md` andJSON. Current bounded regression evidence: `osamodas-runtime-risk-inventory-20261009.md`.
