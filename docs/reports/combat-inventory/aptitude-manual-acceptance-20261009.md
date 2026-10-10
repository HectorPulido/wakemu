# Complete aptitude manual acceptance

Build-cap validation, atomic partial saves, tackle and execution counts are deployed in r54. Barrier first-hit/exhaustion is verified; per-turn renewal remains pending. Await its owner confirmation before accepting renewal. This plan covers all 31 native attribute identities; it does not assert those pending features already work. No restart is part of the test.

## Preparation and persistence

1. Outside combat, use a test account authorized for the console and enter `!nivel 250` in chat. This supported command raises the character level; it cannot lower it. Enter `!ayuda` to see supported commands. There is **no implemented aptitude respec/reset console command**: the dispatch table only supports `!ayuda`, `!pos`, `!nivel`, `!tp`, `!item`, `!mob`, `!equip` and `!unequip`. Do not use invented reset commands. Keep equipment, pets, food and temporary effects unchanged.
2. Keep default build 0 as the baseline. In build management create a new non-default test build with empty aptitude allocations. Select it and record its effective level and all current statistics. Allocate exactly one point to the row under test, save, close/reopen panels, then reconnect. The saved point and statistic must remain identical.
3. After recording that row, leave combat, select the default build, and delete the disposable non-default test build through build management. Create a fresh empty test build for the next row. The server supports owned non-default build deletion outside combat; default build 0 cannot be deleted. This tests all 31 rows without depending on an unimplemented reset command or exceeding the 24 non-permanent build capacity. If build creation/deletion is not exposed by the current client UI, record that as an acceptance blocker rather than substituting SQL or a guessed command.
4. For each capped row, additionally allocate up to the listed cap and attempt one more point. The extra point must be unavailable/rejected; reconnect must retain the last valid sheet. Spend the last available point of a category and try another point in it: the server must reject even if a different category has spare points.
5. Create/select a legitimately level-capped owned build. At level 20 it must have Intelligence 5 / Strength 5 / Agility 5 / Luck 4 / Major 0. The higher real level must not supply extra points. Switch back and verify the original build's allocations/statistics. Repeat the saved capped-sheet test with a partial save that changes its level: retained allocations exceeding the new budget must reject atomically, while a simultaneously empty/reset aptitude sheet may succeed.

## One-point expectations

|Category|Attribute|Expected one-point producer difference|
|---|---|---|
|Intelligence|HP percent|+4% to flat maximum HP; compare after flat HP additions|
|Intelligence|Elemental resistance|+10 resistance; cap 10|
|Intelligence|Barrier|One additional permitted reactive reduction; reduction half actor level; cap 10; first-hit/exhaustion proven in actual PvP, per-turn renewal still pending|
|Intelligence|Healing received|+6% via state 3205 level 6; qualifying other allied healer; self/original-owner exclusions must apply; cap 5|
|Intelligence|HP as armor|4% per point of maximum HP plus maximum virtual HP; 0.4% when current HP is 80000 or above; no summon application; cap 10|
|Strength|Elemental mastery|+5|
|Strength|Melee mastery|+8; cap 40|
|Strength|Distance mastery|+8; cap 40|
|Strength|Flat HP|+20 before HP percentage|
|Agility|Lock|+6; snapshot and actual disengagement are separate checks|
|Agility|Dodge|+6; actual disengagement requires movement fix|
|Agility|Initiative|+4; cap 20; next fight uses updated turn ordering|
|Agility|Lock and dodge|+4 each|
|Agility|Willpower|+1; cap 20; actual AP/MP removal must consume live stat86|
|Luck|Critical chance|+1 percentage point; cap 20; does not guarantee next attack critical|
|Luck|Block|+1 percentage point; cap 20; does not guarantee next attack block|
|Luck|Critical mastery|+4; only qualifying critical damage/heal paths|
|Luck|Rear mastery|+6; facing must be rear|
|Luck|Berserk mastery|+8; native HP qualification required|
|Luck|Healing mastery|+6|
|Luck|Rear resistance|+4; cap 20|
|Luck|Critical resistance|+4; cap 20|
|Major|AP|+1 maximum AP; cap 1|
|Major|MP and mastery|+1 maximum MP and+20 mastery; cap 1|
|Major|Range and mastery|+1 adjustable range and+40 mastery; cap 1; fixed-range spells remain fixed|
|Major|WP|+2 maximum WP; cap 1|
|Major|Armor given|+20%; cap 1|
|Major|Damage inflicted|+10%; cap 1|
|Major|Elemental resistance|+50; cap 1|
|Major|Healing performed|+10%; cap 1|
|Major|Indirect damage and mastery|+10 indirect stat 101 and+40 mastery; cap 1|

Major points unlock at 25 / 75 / 125 / 175 / 225. No missing/dormant historical bonus 24 / 25 / 32 / 33 may be allocated. Current native identities are pinned in `aptitude-all-attributes-audit-20261009.json`.

## Combat consequences

Enter a fresh ordinary PvE fight after each allocation change; do not expect changing builds during combat to reinitialize already-retained effects. Verify AP/MP/WP maximum/current values, turn initiative, adjustable spell range and client/server agreement. Use the same legal spell, level, positions/facing and target for mastery/resistance comparisons; record critical/block outcomes so random variants are not confused with allocation failures. Crit/block use percentage rolls, so the one-point observation is the displayed/stat snapshot delta and correctly classified outcomes, not an exact success frequency in a short sample.

For received healing, compare other allied healer versus self-heal controls. For HP armor, record actual armor after fresh initialization. For barrier, take repeated qualifying incoming direct hits and verify the allocated count, reduction and renewal boundary against the source-backed owner test; do not assume every indirect hit qualifies. For lock/dodge, attempt an actual legal move adjacent to an enemy, record path and AP/MP payment, and repeat after the combined attribute change; movement is deployed in r54; verify the live client/server AP and MP payment agrees.

Repeat build save/reconnect/start-of-fight checks on all 18 classes to identify breed-specific snapshot composition failures; shared arithmetic proof does not substitute for this acceptance pass. A failure report should include class, real/build level, attribute ID, allocation, before/after statistics, spell/target and whether reconnect or combat start changed the result.
