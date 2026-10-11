# Low-level monster activation acceptance

Run this only after the deployment receipt confirms the enabled references. A pending reference in the inventory is not an activated monster.

## Complete client test

1. Reconnect the client after deployment. Select an existing character with a normal equipped deck. Leave any dungeon with `!exitdungeon`, then enter `!tp 1134 -8 -7 -1` in local chat.
2. Enter `!mob 5525 1 2` (Wonejo). Attack the group, use a normal class spell, and end your turn. Let the monsters act before killing them. Expect native attacks, visible HP changes, and a complete next player turn.
3. After finishing the fight, enter `!mob 2616 4 2` (Miaumiau). Stay adjacent and end your turn. Expect a legal native attack with animation and damage. Conditional support abilities need not trigger every turn.
4. Finish that fight and enter `!mob 6 4 2` (Baby Tofu). Leave an enemy alive within reachable range and end your turn. Expect movement and its native attack without a stalled turn.
5. Repeat with `!mob 2 4 2`, then `!mob 39 4 2` (Jalatins). Expect native attacks at legal range. Successful resource loss must update AP/MP according to the native resistance rules.
6. Across the sequence, use class damage and support/state spells, finish a victory, and start a fresh fight. Expect correct costs, HP/state updates, turn order, and no effects carried from the previous fight.
7. Repeat one fight with Huppermage, Sram and Feca if those characters are available. Use their normal spell decks and one class mechanic already used before this release. Expect the same behavior as before deployment.

For each problem, record the character/class, monster reference, spell used, turn and visible result. Do not change level or equipment halfway through a fight. Stop the fight if combat stalls; report the exact last action.

## Operator checks

```sh
docker compose ps
curl --fail http://127.0.0.1:18081/health
docker compose logs --since 10m world ai
```

Expected: world and AI healthy, world health returns `ok: true`, and the complete sequence produces no new combat exceptions. Health alone does not demonstrate spell execution; the client sequence and automated per-reference receipts provide that evidence.
