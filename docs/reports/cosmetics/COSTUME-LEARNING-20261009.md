# Native costume learning and selection

Status: Hector confirmed costume appearances work on r63. The costume flow is
manually accepted. Follow-up sprint/aura support remains source-only pending
automated verification and a later deployment; this follow-up performs no world
restart, client launch or runtime database write.

## Screenshot findings

Both reported items use the native `bIt` learning action, rather than the furniture
`bIx` action. They differ in rarity and binding, but share the same missing server
route. The old `13220/cqd` dispatcher sent every item learning request to furniture
learning and rejected these requests before consuming anything.

| Item | Reference | Action | Native category |
| --- | ---: | ---: | --- |
| Traje de guarda | 9727 | 7692 | 3, PLAYER_COSTUME |
| Traje de ninja | 12202 | 5716 | 3, PLAYER_COSTUME |

The installed client provides 1,234 `bIt` learning actions, including 562 costume
items. `ExportNativeCosmeticActions.java` exports the native category through
`bIt.dzN().getNumber()`; migration 092 imports this immutable metadata and records
the source client SHA256. All 1,234 currently have no native item-use criterion.
No display-name matching, rarity exception or per-item workaround is used.

## Behavior

The shared `13220` request now selects the cosmetic or furniture handler using
native action metadata. Cosmetic learning validates the account session, item
ownership, action and equipment state. It consumes exactly one inventory item,
persists account ownership and an idempotent receipt in the same transaction.
Replaying the same source UID does not consume a second unit. Learning an already
owned cosmetic from a different item is rejected without consuming that item.
Bound items remain learnable by their owner; learning does not transfer items to
another account.

Account inventory and preset components `8/eST` and `9/eSX` are sent through
`13873`. The native preset receives a character-owned selection target on first
learning. Existing finisher presets and selections are preserved. Native `13765`
category 3 requests select, replace or remove an owned costume; `12455` activation
controls both the costume and finishers in that preset.

The native actor `pq.Tb/tF/tG` section contains the costume reference in its first
32-bit integer. `bmA.zm` applies this directly through `bjo.Du`. Appearance refresh
`13046`, format 30, is sent to the player and other players in the same world
scope. Reconnect uses the same persisted actor component. The native costume
oracle decodes this component using the installed client classes.

Selection remains limited to existing character-owned presets. Costume and
finisher selection are manually accepted. Follow-up source implements native
sprint (category 4) and aura (category 6) selection through the existing first-party
actor fields; mount/pet/equipment appearance selection remains under review.
Arbitrary preset creation/copy/delete remains separate work.

## Complete manual acceptance after deployment

1. Use two clients on the same map. With an account that does not own these
   costumes, run `!item 9727 2` and `!item 12202 1` in general chat.
2. Learn the guard costume using its hand/use action. Confirm one guard item
   remains, the collection contains the guard costume and no furniture error
   appears. Learn the ninja costume and confirm its physical item disappears.
3. Open the costume collection/preset. Select guard, then ninja. Both clients
   should see the corresponding appearance immediately. Any selected finisher
   must remain selected.
4. Remove the costume and select it again. Disable and enable the preset. The
   appearance should clear and restore on both clients.
5. Reconnect the costume wearer. The selected appearance and both learned
   collection entries must persist.
6. Try to learn the remaining guard item. It should report already learned and
   preserve the item. Check that character stats and combat spells are unchanged.

Automated gate: 27 tests passed (28.686 seconds), including 6 new pure costume
regressions, 5 isolated PostgreSQL tests and 16 existing finisher, cosmetic
condition and furniture regressions. Python source compilation passed.

Automated evidence: `test_owned_costume_cosmetics.py`,
`test_cosmetic_learning_postgres.py`, existing owned finisher and furniture
regressions, and `VerifyCostumeActorComponent.java`. The native actor oracle also passed the installed client decoder.

Command (with the isolated PostgreSQL test DSN and read-only published catalog
connection configured):

```sh
PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest test_owned_costume_cosmetics test_cosmetic_learning_postgres test_owned_finisher_cosmetics test_combat_cosmetic_conditions test_haven_bag_furniture_knowledge
```
