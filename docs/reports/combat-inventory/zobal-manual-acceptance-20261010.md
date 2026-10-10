# Zobal complete manual acceptance battery — 2026-10-10

This is a client-side test plan, not a claim that Zobal is accepted. The active roster, source dependencies, runtime audit and current limits are recorded in the [class inventory](remaining-classes-20261010/14-review.md) and [current audit](zobal-current-audit-20261010.md). No client session, service, or character state was changed while preparing this battery.

## Preparation

Use a disposable Zobal character outside combat and outside a dungeon or haven bag. The test-console command is `!nivel <level>`; `!level <level>` is an alias. Use `!nivel 100` for the complete battery: this covers all 19 class passive unlocks (the highest is 95), as well as the mask variant. It raises a character below level 100 to 100. This is permanent and cannot lower the character's level. Reconnect after leveling so the spell and passive book refresh. Do not use a command to add states, resources, summons, or combat actors.

Use current spell tooltips for costs and target rules. Record the character level/build, AP/MP/WP, HP and armor, mask states and levels, action bar, turn actor, target/cell, and before/after values. A spell being granted or visible in the bar is not proof that its effects work. Arrange at least one ally and several enemies so area, ally, enemy, collision, and non-target cases can be tested without ending the fight prematurely. For a repeatable ordinary enemy group, enter `!mob 4 50 3` outside combat, then start the fight normally. The syntax is `!mob PROFILE LEVEL COUNT`. Keep another allied player nearby for mask bonuses and resurrection; use a separate fight for each deck comparison.

## 1. Innate grants and mask branches

At level 100 with no passive 7104 equipped, start a fight and press Ready. Verify the innate Zobal state is present and the granted bar contains Máscara Sáikopat 7081, Máscara Eskérdikat 7082, Máscara Zobal 7083, and Espíritu Enmascarado 8559. Confirm these granted actions are not inserted into the owned spell deck.

On legal targets, cast 7081, 7082, and 7083 in sequence. For each, verify the current tooltip's payment, the primary state (6611, 6612, or 6613), and its level/duration. At the next natural turn boundary, check the primary states' remaining duration and the corresponding charge states Saikocarga 9247, Eskerdicarga 9248, and Clasicarga 9249. Repeat with the same state present and with a different primary mask already active; compare actual state removal/retention against the native tooltip and the [mask tree evidence](zobal-current-audit-20261010.md#innate-masks-and-grantbook-lifecycle). Do not assume primary masks are mutually exclusive.

Repeat with passive Erosión 7104 equipped. Ready must grant Máscara Sáikopat II 7226 in the first mask slot instead of 7081, while 7082 and 7083 remain available. Cast 7226 and verify its primary state 6888, then cast the other masks. Remove 7104 outside combat, reconnect, and verify the base 7081 grant returns. Check that changing passive decks does not leave a stale granted action or duplicate UID.

The bonus states are separate branches: 7081/7226 → 6614, 7082 → 6615, 7083 → 6616, with the other bonus states removed on a switch. The native mask selector is an ally area of radius four and excludes the caster; its `IsChallenger("target")` criterion means a player-character/companion actor, not a PvP challenger. Put another player or companion inside the radius to verify the bonus state, and use a second player just outside the radius, an enemy NPC inside, and the caster itself as negative controls. Record whether switching masks removes only the competing bonus states from eligible nearby allies. Do not require a PvP duel for this branch.

## 2. Owned active spell deck

The Zobal has 21 owned actives. Use legal decks sized to the character's available slots; perform each spell at its actual unlock level or at a higher level. For every action, test one legal enemy/ally/cell target, record its resource delta and exact effect, then test one invalid target or boundary case and confirm rejection spends nothing and leaves no partial state or movement.

| Spell | ID | Main acceptance observations |
|---|---:|---|
| Patada Azotada | 7066 | Damage and any target-dependent branch at range 1–3. |
| Hendidura | 7067 | Close-range area/line recipients; compare ally, enemy and adjacent cells. |
| Perturbación | 7068 | Self/cell-target behavior, affected cells and state changes. |
| Neurosis | 7069 | Damage and conditional/resource branch at legal range. |
| Cabriola | 7070 | No-LOS line targeting, destination, occupancy and movement result. |
| Señales | 7071 | Legal no-LOS target, marked effect and duration. |
| Armazón | 7072 | Ally/enemy target branch, armor/stat delta and duration. |
| Salvamento | 7073 | Targeted effect and any conditional removal/transfer. |
| Ensañamiento | 7074 | Damage and any target state/criterion branch. |
| Zarabanda | 7075 | Legal line target, damage/secondary effect and WP payment. |
| Fuga | 7076 | Movement, final cell, orientation and obstacle/edge rejection. |
| Persecución | 7077 | MP payment, legal adjacent target and actual movement/attack branch. |
| Brinco | 7078 | No-LOS line destination, occupancy and resource/payment outcome. |
| Cabalgata | 7079 | Adjacent legal target, movement/state result and occupied-cell rejection. |
| Disyunción | 7080 | Range, target and WP payment; state or displacement branch. |
| Entrechoque | 7084 | Legal short-range/WP action; exact collision or recipient conditions. |
| Danza Motivadora | 7085 | Ally/enemy target branch, state 6610 and expiry. |
| Danza Macabra | 7086 | Let an actual allied player die; cast on the registered corpse. HP must become positive, state 1144 must appear, and the ally must return to the timeline. No second ally may be revived accidentally. |
| Acrobatismo | 7087 | Target an empty legal cell exactly six cells away with an eligible adjacent enemy; verify relocation. Compare range five/seven, occupied destination and map edge rejections. |
| Aura de Brutalidad | 7088 | Self-centered area recipients, state 6618 and exit/expiry behavior. |
| Solidez | 7089 | Legal line/range case, defense change, WP payment and duration. |

For area actions, put an eligible ally and enemy inside, exactly on the boundary, and outside. For push/movement actions, verify both actor identity and every traversed/final cell; try a blocked route and a map edge. For damage/healing/armor, use actual before/after values rather than floating text alone. Repeat actions that depend on a mask in natural form and with each applicable mask active.

## 3. Espíritu Enmascarado copy lifecycle

Cast 8559 only when its current native prerequisites are satisfied. Verify that the created copy is owned by this Zobal, appears once in the timeline, has the expected copied action book/stats and state 3813, and follows the correct controller. Try one legal copy action on the copy's turn. Test an invalid target and insufficient-resource case without partial creation.

If recast is available, verify the prior copy is removed before/with replacement according to the live native rule; otherwise record the exact native rejection. Also test natural copy death, owner death, end of fight, and reconnect. No dead copy may remain in the timeline or action book, and the owner must not retain a stale state or duplicate copy. See the source and lifecycle limits in the [current Zobal audit](zobal-current-audit-20261010.md#espiritu-enmascarado-8559-copy-lifecycle); do not infer recast semantics from spell names alone.

## 4. All 19 passives

For each passive, first establish the matching action/result without it, then equip only that passive and repeat the same controlled scenario. Keep the same character build, targets and turn position. Verify both its stated benefit and drawback, qualifying and nonqualifying events, state/effect duration and cleanup. Passive readiness during combat initialization alone is not acceptance.

| ID | Passive | Suggested trigger to compare |
|---:|---|---|
| 7093 | Juego de Piernas | Movement/evasion and the stated qualifying turn or contact event. |
| 7094 | Fuera Máscaras | Mask-state presence/absence and its stated transition. |
| 7095 | Empujes Violentos | Zobal push against a legal target; displacement, collision and resulting damage. |
| 7096 | Arte de la Venganza | Receive damage, then perform the qualifying response before/after its boundary. |
| 7097 | Máscara de Vida | Apply the relevant mask and compare the exact HP/healing branch. |
| 7098 | Carnaval | Use the listed mask/ally interaction and check recipients and expiry. |
| 7099 | Armadura Única | Gain armor from a matching source, then compare the passive's condition. |
| 7100 | Ancla | Apply its stated movement/position condition and attempt a displacement. |
| 7101 | Bruto | Compare damage under the stated mask, summon and target conditions. |
| 7102 | Protector Apartado | Trigger the protective branch with an eligible ally and inspect retained effect/removal. |
| 7103 | Colisiones de Apoyo | Cause an actual collision and verify the support effect on the eligible ally. |
| 7104 | Erosión | Check replacement of 7081 with 7226 at Ready, then its mask-specific effects. |
| 7105 | Giro | Trigger the stated movement/turn condition and verify exact state/stat changes. |
| 7106 | Colisiones Regenerativas | Cause a real collision and measure healing on the eligible recipient. |
| 7107 | Espejos | Trigger its reflection condition; check source, target, amount and duplicate prevention. |
| 7108 | En Contacto | Compare the qualifying adjacent/contact case with a nonadjacent control. |
| 7111 | Arte de la Huida | Attempt to disengage from an adjacent enemy; check movement/tackle result. |
| 7112 | Mirada Enmascarada | Compare its qualifying mask/target condition with a negative case. |
| 7113 | Empujes de Traba | Push an eligible target, then compare the stated immobilization/lock consequence. |

**Published-source limitation:** push/collision event roots for 7095, 7103, 7106 and 7113 carry literal `False` criteria in the reviewed native catalog. They are intentionally not enabled by inventing mechanics from their names. The scenarios above are diagnostic comparisons, not promises of an active collision/push benefit. Record these event branches as source-inert pending a verified native definition update; independent stat roots on those passives still execute and should be compared normally.

For 7095, 7103, 7106 and 7113, use a map with enough free cells to distinguish displacement from collision and healing/support effects. Keep an enemy alive after the trigger so the result and cleanup can be inspected. Do not substitute a manually injected state for the collision event.

## 5. Fight, reconnect and multiplayer lifecycle

With another player present, test an ally-target action, an area action and a mask grant while both clients are in the fight. Confirm each client sees the same actor positions, states, turn owner, granted bar and resource values. Disconnect/reconnect during a later turn and verify no mask or passive is duplicated, no state is silently reset, and the next legal action still resolves for the correct actor.

Complete separate fights by victory, surrender and defeat where available. Start a fresh fight after each; old mask states, copied actors, aura/area effects and granted actions must not leak into the next encounter. Repeat one short scenario with a blocked movement cell and a dead actor in the line to verify occupancy/LOS and actor selection.

## Result record

For each failure, record time, fight ID, spell/passive ID, form/mask, current turn actor, target or selected cell, resource/state/HP/armor before and after, action-bar ownership, client message and screenshot. Preserve a separate result for each context. An unexercised native condition, an inaccessible target, or a test-console setup failure is inconclusive rather than a gameplay pass.
