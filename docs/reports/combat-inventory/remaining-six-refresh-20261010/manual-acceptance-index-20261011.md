# Remaining six classes: coordinated manual acceptance

Status: preparation only. PostgreSQL and deployed World/AI/Ecology services are pinned to `bd79c10d0f29de7a32fa29f5d91439388de9ace3f8c2b9ed73f8314856667ae1`; see [`LIVE_DEPLOYMENT.json`](../../monster-combat/bulk-1297-20261011/LIVE_DEPLOYMENT.json). Linked class runs remain historical, mostly on `677`. The latest integrated V14 gate on fede6 completed 1,246 tests with 6 failures, 0 errors and 0 skips. Five literal-release checks have been corrected without weakening behavior assertions, four supplementary selectors are integrated, and a corrected repeat against bd79/current sources is being prepared. Rogue robot7952 movement remains unresolved. Technical/manual acceptance is not complete; catalog deployment and service health do not substitute for the current class gate.

## Release prerequisites

1. Complete every current class branch matrix and resolve enabled unqualified producers, preserving source-disabled legacy branches.
2. Apply and validate source-qualified fixture corrections only after the shared source window is released. Keep native expected behavior and negative controls.
3. Run the final full18 manifest with all native opt-ins and isolated schema tests. Require zero failures/errors/unexplained skips, stable source fingerprints and actual PostgreSQL release boundaries. Runtime-only candidate checks are supporting diagnostics, not a substitute for that gate.
4. Coordinate a complete current-checkout World→AI build through WORLD_COORDINATION.md. Verify deployed source/image identities and catalog. Preserve all concurrent monster/system changes.
5. Record the deployed revision, image identities, catalog revision, test result artifact and fight IDs before manual testing.

## Complete-system sequence

Use the same two-player group throughout. Keep one previously accepted Cra/Iop as a regression control. Change legal decks only outside combat. See the [command preflight and source audit](../remaining-six-manual-guide-audit-20261011.md) before using console helpers: `!nivel 200`/`!level 200` is permanent, and `!mob 4 8 1` is conditional on provider, permission, instance and legal map cells. Use a durable ordinary encounter for multi-turn branches, a real dungeon encounter for progression checks and a friendly challenge for allied/enemy targeting controls.

For each class, run its entire linked procedure rather than individual isolated casts. Check action bars, AP/MP/WP, states, damage/healing/armor and real owner turns. After final summon/NPC removal, reuse their cells and verify LOS/counts/turns. Distinguish a reversible player KO from final removal: KO preserves the native registered slot for resurrection; final removal must retire it. Do not infer either lifecycle solely from HP0. Repeat with a second owner to detect foreign ownership leaks.

- [Enutrof](../enutrof-manual-acceptance-20261010.md): deposits, conversions/extraction, treasure, companion, forms and contextual passives. Event74 is still producer-unqualified; it is not silently accepted.
- [Steamer](../steamer-manual-acceptance-20261011.md): forms, turrets, microbots/rails, capacities, real movement and incoming-damage reactions.
- [Sadida](../sadida-manual-acceptance-20261011.md): complete doll/seed/tree lifecycle, Voodoll, damage/healing/armor, every passive and owner isolation.
- [Rogue](../rogue-manual-acceptance-20261011.md): all elements, granted bomb actions, walls/chains/timers, robot/controller actions and bomb passives. Several automatic semantic probes remain open.
- [Eliotrope](eliotrope-manual-20261011.md): two portals, replacement, legal portal-routed casts, Calm/Exalted, gift cost/range and current passive branches. Portalivio's strict two-portal replacement passed in the pinned `677` core gate; client acceptance is still pending. The actual Gift→ally attack→giver back-attack sequence now qualifies Celada's conditional +60 branch. The retained state3671 carrier's cleanup/expiry boundary remains unqualified: cleanup targets the giver while the carrier stays on the ally. Do not require carrier deletion as an expected result.
- [Xelor](../xelor-manual-acceptance-20261011.md): dial/current-hour, AP cancellation, Regulator, Tic/Tac, resources and all passive comparisons. It remains PREPARED/NOT_READY: numerous reactive/current-hour branches lack positive-and-negative qualification, and manual client lifecycle has not run. Historical failures and source-dormant branches must remain distinct.

## Shared multiplayer completion

1. Both players join before Ready; both press Ready. The first turn must belong to the shown actor, whose own action bar/resources are usable.
2. Play several owner/NPC/summon turns with state expiry and simultaneous deaths. No unrelated actor plays a death animation or disappears. Include an actual player KO, legal ally resurrection, then a second lethal hit on that same player; each lifecycle must be delivered once. A final removed NPC/summon must leave no stale obstacle. Reversible player KO must retain its supported resurrection behavior.
3. Disconnect/reconnect one participant during a live fight. Its registered allies/enemies/summons, current actor and action bar must recover consistently. A JSON checkpoint roundtrip alone is not this graphical acceptance.
4. Finish a real dungeon room. Both players leave combat and advance together; no stale swords, orphan encounter or vanished progression mob.
5. Repeat surrender and a second fight. Both sessions remain usable, turns advance, and the dungeon can continue.
6. Run a final Cra beacon reaction and Iop combo control after all six classes to detect shared-engine regressions.

Record each discrepancy with fight ID, actor ID, spell/target, timestamp and expected versus observed outcome. Manual acceptance remains pending until the complete sequence passes.
