# Corpse seed extraction: server-only correction

## Root cause

Jalató has **three**, not two, native collection actions:

| Action | Item | Native criterion | Corpse behavior |
| --- | --- | --- | --- |
| 3722 | 2731 | `IsDead("target")` | Hand resource harvest |
| 3723 | 2246 | `not IsDead("target")` | Living-only action, hidden on a corpse |
| 3724 | 7361 | Empty | Unrestricted seed extraction, previously disabled by the server |

The unchanged installed Spanish translation identifies item7361 as `semilla de jalato` (`content.15.7361`). Its native action has profession74, required level0, duration3000ms and GUI action44. The living-only action uses GUI action45. The earlier criterion-only probes omitted empty expressions, thereby omitting the seed button Hector reported.

`world_actor(dead=True)` previously put empty-criterion actions into native disabled-action section `sR`, while `Harvests.begin` and `complete` only admitted exact dead-only criteria. Empty criteria are valid unrestricted native actions: the installed native menu keeps them visible, but the server disabled their availability and authorization. This combination explains a visible disabled seed extraction action without requiring any client change.

## Server change

The corpse encoder now leaves native empty-criterion collection actions enabled. Corpse harvesting accepts empty or exact `IsDead("target")` criteria, while all existing profession, output-stack, reachability, lease, map, expiry, inventory and ownership checks remain in force. Unsupported complex criteria remain disabled/rejected. Living-only actions remain unavailable on corpses.

A corpse seed action uses the same durable transactional consumption as hand harvesting. The winner receives its native seed output once and removes the corpse; subsequent seed or hand attempts cannot duplicate rewards. Quantity remains `settings.monster_harvest.quantity`; no new loot table, XP formula or SQL migration is introduced. The general rule covers375 native empty-criterion actions:374 in profession74 and one in profession82.

No client, assets, capture agent, combat or spell files changed. No service was restarted by this worker. One-hour expiry is already accepted by Hector.

## Offline native verification

`sniffer/java/VerifyCorpseMenuVisibility.java` reads current server appearance bytes, decodes `ctE/eHj`, applies actual native `eGv` DEAD19 **and `bjh/sR` collection availability**, loads actual binary breed actions, and calls actual `cXc.bxQ()`. It checks unrestricted resource availability with `bje.Ds()`, and reverses DEAD19 as a living-target control.

Result: **334 dead-only actions visible,332 living-only actions hidden,375 unrestricted actions visible and available**. Jalató3724/item7361 is now included. The native radial menu `cVP.dJZ()` filters both rendering branches by `bxQ()` before `fMw.a()` draws an icon.

The offline player deliberately has no profession sheet; enabled placeholder labels isolate menu visibility from subscription/profession gates. Availability means the real target's native resource-enabled set, not a certification of all account rights. Native identities and predicates come from installed binary breed data. The appearance fixture uses current source with a frozen breed statistics catalog and freshly exported native collection catalog; it is not a live deployment capture.

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/corpse-menu-review sniffer/java/VerifyCorpseMenuVisibility.java
java -Djava.awt.headless=true -cp '.runtime/local/corpse-menu-review:client/lib/*' VerifyCorpseMenuVisibility .runtime/local/corpse-menu-review/corpse.bin -1
```

Regression coverage adds a real PostgreSQL seed harvest: grant7361, consume corpse, replay no-op, reject subsequent hand harvest, exactly one inventory reward and one action3724 receipt. Existing hand, concurrency, expiry and rollback coverage must also pass in the coordinated validation gate.

## Manual acceptance after complete current server deployment

1. Log in with the unchanged client and a character knowing Peletero. Defeat an ordinary Jalató in the world.
2. Open the corpse's contextual menu. Its native corpse seed extraction action must be enabled, alongside the hand resource action. The separate living-only action must remain hidden.
3. Choose seed extraction, wait for its normal3-second occupation and check inventory: receive `Semilla de jalato` item7361 according to the configured harvest quantity. The corpse must disappear immediately.
4. Reopen the old position and reconnect: no second harvest or second reward may occur.
5. Defeat another Jalató and choose the hand action. Receive its ordinary native corpse resource once; the corpse disappears as before.
6. Extract from a living Jalató. Normal living harvesting and cooldown must still work.

Keep issue40 pending live acceptance until the enabled seed action is confirmed on the complete deployment. The earlier two-criterion probe alone was insufficient; do not describe the screenshot as stale without evidence.
