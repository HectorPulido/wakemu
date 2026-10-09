# Four installed class-system acceptance cards

Use the existing account owning Npers. Four new, unequipped level200 characters were created without changing any previous character, account or password. Prueba Osamodas13 remains intact. Private creation evidence: `.runtime/combat-review-20261008/four-class-manual-character-setup.txt`.

|Character|ID|Legal normal deck|Passives|
|---|---:|---|---|
|Prueba Feca|14|6967–6978|None|
|Prueba Sram|15|4579,4581,4583–4590,4592,4593|None|
|Prueba Sacro|16|5028–5039|None|
|Prueba Pandawa|17|4702–4713|None|

All start on map1134,(-12,-8,-1). Choose the indicated character from selection. Stay outside dungeons/merkasaco; use `!exitdungeon` if necessary. For each card, in exploration enter `!mob 5574 133 1`, attack the new group, and complete placement/Ready. This native enemy has4500HP and survives the representative sequences. Granted combat actions are obtained from actual Ready/state transitions, not inserted into the deck. Stop a card at the first failure, then test an independent character.

## Pandawa: carry, follow, throw, atomic rejection

1. Select **Prueba Pandawa**. After Ready, find **Karcham6847**. Stand one cell from the legal target highlighted by the client, excluding stabilized/uncarriable targets. Cast Karcham: base cost **1AP,0MP,0WP**; conditional native state9335 can reduce AP to0, so use this clean build and record any such state. The target should be carried at the owner position; **Chamrak6848** is granted by the carried-state lifecycle.
2. Move one legal cell. Movement costs its normal MP; the carried target must follow, with no ghost blocking its former cell.
3. Use Chamrak on an empty legal destination in its indicated range. Base cost **1AP,0MP,0WP**; native carrying/drunk/deck conditions can alter range/cost. The target appears exactly once at that destination, is targetable there, and the reciprocal carry relation clears.
4. Attempt Chamrak without a carried target: reject with no payment or movement. Carry again, try an occupied throw destination: reject atomically; then throw onto a valid empty cell.
5. Finish normally and enter a new fight. No old carry relation, target ghost or stale granted throw remains.

Source: original casting6847/6848 from `native-class-spell-level-zero.json`; actual owned6847→6848 regression `carry-6847-02.json`,3/3 PASS. The source target predicate is `IsCharacter(target) or IsOwnSummon(3794)`, with native stabilization/uncarriable guards. A target outside that predicate is a legal rejection, not permission to carry arbitrary scenery.

## Sacrier: actual self-damage, stored damage, healing and armor

1. Select **Prueba Sacro**. After Ready note combat current/maxHP, armor and grants **Corazón Sanguíneo6065** and **Corte8586**. The saved exploration maxHP2050 is not an assumed combat maximum: native innate modifiers can change it.
2. Stand adjacent to the enemy and use **Sangre a Sangre5028** once. Expect **3AP,0MP,0WP**, actual enemy damage, owner self-damage and stored state4840. The verified clean branch stores level5 and uses `floor(combat_maxHP ×0.01×5)` for self-damage. Example: combat maximum2850 gives142; do not compare against the old level20 fixture’s16.
3. On the same owner turn, target yourself with **Corazón Sanguíneo6065**. Expect **1AP,0MP,1WP**, healing from stored damage, positive armor and consumption of4840/9312. The retained heal uses the same stored level5/maxHP formula; it must not repeatedly heal from a consumed record. Armor depends on actual current/missingHP and native child-level rounding; the old level20 value47 is not a promised value for this L200 character.
4. Finish turns normally and complete the fight. A subsequent encounter starts without the old stored damage or armor.
5. Optional complete transformation continuation in a separate fresh fight: cast5028 up to twice per owner turn until native9322 makes **Venganza8587** legal. Cast it on yourself: **2AP+1WP**. Expect temporary actions8588/8589/8590. Use8588 against a highlighted legal target: **0AP/0MP/0WP**, then original book restoration and rejection of the expired temporary shortcut. Do not force the prerequisite or treat ordinary enemy damage as a fixed number of setup casts.

Evidence: `heart-blood-02.json` actual blood→stored heal/consumption PASS; `class-morph933-lifecycle-05.json` parent and independent temporary children commit with restoration. Live presentation and complete fight cleanup remain the purpose of this card.

## Feca: glyph creation, turn activation, expiration and cell reuse

1. Select **Prueba Feca**. Place yourself so an empty target cell at native distance2–3 has the enemy on one cardinal neighboring cell. Use **Fecalistófedes6967** on that empty center. The installed clean deck excludes6988/6994/6999. Expect exactly a five-cell cross and owned paired areas1474/1477; cost **5AP,0MP,2WP** total. The ordinary cast charges5AP; the native glyph branch separately consumes2WP. The character must actually have at least2WP.
2. If needed, move yourself through then outside the cross normally. This glyph does not damage on creation or movement entry. Record the enemy HP immediately before its next turn.
3. End the Feca turn with the enemy still inside the cross. At enemy turn start, the verified clean L200/5574L133 branch deals **45HP**:4500→4455 if no other damage has occurred. If the enemy moves away before its turn, this does not test the intended branch.
4. End the enemy turn. At the next Feca turn start both glyph areas disappear. Later movement/turns in the old footprint cause no glyph damage or obstruction. Reuse the old center when resources and normal cast limits permit.
5. Finish and start another encounter. No stale glyph ownership or timers remain.

Verified offline positions: owner(-23,-143,70), enemy(-22,-143,70), center(-22,-142,70). These are a geometry example, not a forced live placement. Preserve equivalent relative distances using actual highlighted cells. Evidence `feca-glyph-manual-03.json`: complete creation→activation→expiration/reuse PASS. Turn-start10000 delivery is an explicit documented Wakemu policy.

## Sram: trap placement, one activation, removal

1. Select **Prueba Sram**. After Ready find **Trampa de Repulsión5182**, the actual temporary granted action. Cast it on a highlighted empty center at native distance1–6, away from another owned trap. Expect **2AP,0MP,1WP**, a five-cell cross and one activation charge.
2. Move one cell from outside into that cross on your turn. Expect normal **1MP** movement payment and one activation. The verified owner-entry case remains on its entry cell; this card does not promise that the owner is pushed two cells.
3. The exhausted trap disappears. Leave and enter the old footprint again: no second activation, no ghost blockage. For the enemy-trigger variant, only count a pass if the actual enemy enters while on its real turn; do not direct an NPC through a console or alter AI.
4. Finish normally, reconnect, and repeat placement in a new fight. No exhausted spatial trap survives.

Verified offline geometry: owner(-23,-143,70), center(-24,-142,70), entry(-23,-142,70). Independent NPC entry caused the original child409841 two-cell push; no HP damage is promised for this trap. Evidence `sram-trap-manual-02.json` and `sram-trap-enemy-01.json`. Exhausted Qq cleanup is the documented Wakemu successful-activation policy.

## What to report

For each character send the first failing numbered step, target/position, AP/MP/WP before and after, timeline/action bar and visible state/area. Successful placement alone is not a complete system pass: include activation, cleanup and the next-fight/reconnect check.
