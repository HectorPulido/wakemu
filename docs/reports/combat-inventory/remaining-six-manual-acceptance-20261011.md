# Remaining six classes: complete manual acceptance

Status: prepared, not released for manual acceptance. PostgreSQL and the deployed World/AI/Ecology services currently use catalog `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`; the deployment receipt reports all three healthy. The class evidence linked below remains pinned to earlier revisions, mainly `677`, and must not be relabeled as bd79 test evidence. V14 on fede6 completed 1,246 tests with 6 failures, 0 errors and 0 skips; stale catalog-literal checks were corrected without dropping behavior checks, and four supplemental selectors were integrated. The corrected full18 repeat against bd79/current sources is being prepared; Rogue robot7952 movement remains unresolved. Manual acceptance stays pending until that gate and source/image alignment review are complete. See the [current closure ledger](remaining-six-refresh-20261010/current-closure-20261011.md), [`LIVE_DEPLOYMENT.json`](../monster-combat/bulk-1297-20261011/LIVE_DEPLOYMENT.json), and [deployed core receipt](../../../.runtime/full-regression-20261011/current-deployed-core-check.json).

## Preparation

Use ordinary disposable characters and the normal spell/passive deck editor. The console and roster preflight, including command permissions and map restrictions, is documented in the [manual-guide source audit](remaining-six-manual-guide-audit-20261011.md). `!nivel 200` permanently raises level and cannot lower it; use a disposable character below level 200, then reconnect. `!mob PROFILE LEVEL COUNT` is only available when the local combat-test provider and command permission are present, outside dungeon rooms and in instance 0; it requires native profile/level data and reachable free map cells. Profile 4 level 8 is only a short opening/death check, not a durable multi-turn target. Do not inject resources, states, summons or grants. Start with a consenting second player in a friendly challenge, then repeat the complete class rotation in PvM.

## Class batteries

Run each linked battery completely, including optional passive controls, summon actions and end-of-fight cleanup:

- [Enutrof](enutrof-manual-acceptance-20261010.md): both forms, owned companion, resource reactions and passive comparisons.
- [Steamer](steamer-manual-acceptance-20261011.md): normal/Stasis modes, turret upgrades, Microbot networks, all Transition targets and ownership isolation.
- [Sadida](sadida-manual-acceptance-20261011.md): dolls and their actual controlled actions, Tree/Voodoll, seed/death lifecycle and owner-specific reactions.
- [Rogue](rogue-manual-acceptance-20261011.md): all bomb profiles, real detonation and resource consumers, robot book, movement and passive comparisons.
- [Eliotrope](remaining-six-refresh-20261010/eliotrope-manual-20261011.md): portal routing, Calm/Exalted transitions, actual allied Gift acquisition and first/following Ambush/heal consumers.
- [Xelor](xelor-manual-acceptance-20261011.md): dial/current hour, mechanisms, granted actions, paid movement, AP-loss reactions and passive comparisons.

## Shared lifecycle checks for every class

1. Ready both characters. On the first turn, both clients must agree on the current actor, countdown, movement permissions, resources and the correct actor spell book. Complete at least three normal rounds without duplicated or skipped living turns.
2. Attempt one legal attack and one rejected occupied, blocked or out-of-range action. Successful effects and payment occur once; rejection leaves HP, resources, positions and owned objects unchanged. Continue playing normally after rejection.
3. Create the class object or summon where available. Reconnect its owner while the second player remains online. Both clients must retain identical actor identities, ownership, HP, positions, turn and action book. Reconnect the second player separately; no repeated birth, damage or passive application is acceptable.
4. Kill an ordinary enemy and an owned class object. Only the correct entity performs the death animation. A final dead object must disappear and release its occupied cell; a reversible player KO must preserve its legitimate resurrection state. Try a legal cast or placement through the cleared cell.
5. Finish a fight normally and inspect both clients: no stale combat swords, portraits, timer, class grants or actor registrations. Start the next fight immediately and repeat the first-turn checks.
6. In a separate fight surrender one character while the other remains. The departing client must return coherently to exploration without disconnecting; the remaining fight must advance or terminate according to its real remaining participants. Reconnect afterward and start a fresh fight.
7. For a dungeon, complete a room with both characters online. Both must reach the same next room, with its actual enemy group visible and interactable. A failed/aborted fight must preserve a coherent retryable dungeon state.

## Shared resource-boundary acceptance (source correction integrated; deployment/manual check pending)

Use the Cra and Xelor test characters with their legitimate spell decks. This check applies to player and monster targets; do not infer success from the immediate resource popup alone.

1. Record the target's current and maximum MP. Cast Flecha Azotadora (4816) with the Cra. Record the actual MP removed and damage. End the Cra turn. At the target's next turn, its usable MP must still reflect that removal; its maximum MP must remain unchanged. After that target completes its turn, verify its following turn receives the normal budget, without restoring damage taken.
2. Repeat with Xelor Ralentizacion (775) and AP. Verify its actual WP cost immediately after casting. Xelor's native end-turn WP recovery is expected and must be distinguished from an unearned general WP reset. AP removal must constrain the target's upcoming turn.
3. Let the attacker turn expire once instead of ending it manually. The same target budget must result. A late action or repeated end request must not cause a second recovery, extra turn or duplicate passive reaction.
4. Repeat while a class effect modifies a maximum resource and while an owned companion is present. Maximum modifiers, the companion's first-turn budget and legitimate resource gains must remain coherent.
5. Resurrect a character that died with spent AP/MP before finishing its turn. Verify its first returned turn has the intended usable budget, its actual resurrection HP and native WP behavior, and that a legal paid spell succeeds exactly once.

The shared turn-boundary correction is in the deployed core: the read-only deployed-core receipt matches the qualified resource-boundary, resurrection, movement, dispatch and spell-transaction hashes. The full source image is not an exact match to the current checkout because the Systems boss-score survival hook was added afterward; preserve that distinction when reporting current-source identity. The live-client procedure remains pending the corrected full18 gate and manual run.

## Failure evidence

Record the time, both character names, class/deck, spell/passive IDs, current actor, before/after HP/resources and cells, and exact rejection text. Capture both clients for any visibility, timeline or spell-bar disagreement. Server observer command: `docker compose logs --since 10m world`. Do not publish credentials or private log contents. Report the first discrepancy before repeating a paid action, so duplicate application can be distinguished from the original fault.
