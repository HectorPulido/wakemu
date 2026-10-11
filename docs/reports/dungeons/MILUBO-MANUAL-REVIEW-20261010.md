# Milubo: four-room manual review

Status: native four-stage topology identified; mixed-flow implementation and automated integration validation in progress. This document is a review and acceptance plan, not evidence of deployment or a completed graphical run. The previous one-encounter fallback is rejected as an implementation of the dungeon.

## Evidence reviewed

- Native definition 47 explicitly has type `DUNGEON_4_ROOMS`, interior map 1266, exterior map 1264, entry object 32240 and destination 4159.
- [MethodWakfu's Mulou guide](https://methodwakfu.com/pvm/autel-de-la-lune/) describes four rooms for six players with no key requirement. Its archived four room screenshots were inspected individually: wooden platform, cave, grassy clearing, and final moon altar. The guide is secondary evidence; its historical combat mechanics are not certified against the installed client version.
- The installed native dungeon species are Minilubo 5113, Milubo 5111, Miluba 5112 and final boss Luna Gigante 5114. Ordinary summoned moons are not initial encounter actors.
- [Literal mixed topology and directed path witnesses](MILUBO-MIXED-NATIVE-FLOW-20261010.json) retain physical gates, internal teleports, layered terrain and both exterior exits.

## Root cause

The transport extractor removed physical door cells when finding terrain components but did not reintroduce physical door transitions into its transport graph. The entry component consequently appeared isolated. The fallback incorrectly treated this as a single usable arena.

Milubo has four large combat areas and three small transit components. Neither every walk component nor every teleport destination is a separate combat room. Two physical gates and a transport between the second and third stages determine victory progression; other teleports are travel within a stage.

## Intended encounters

These initial quantities come from the reviewed guide, rather than the former generated family roster. Native minimum levels are deterministic under the existing configuration level policy. The level-sum column is a composition progression check, not proof that boss mechanics or fight difficulty are fully implemented.

| Room | Visual reference | Minilubo 5113 | Milubo 5111 | Miluba 5112 | Luna Gigante 5114 | Initial actors | Actual level sum |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Wooden platform | 2 | 2 | 2 | 0 | 6 | 424 |
| 2 | Cave | 2 | 3 | 2 | 0 | 7 | 494 |
| 3 | Grassy clearing | 3 | 3 | 2 | 0 | 8 | 562 |
| 4 | Moon altar | 3 | 2 | 2 | 1 | 8 | 575 |

Native role metadata must exclude dominant and archmonster properties. Only the selected boss appears in room four, once.

## Connections to verify

| Step | Native interaction | Expected result |
| --- | --- | --- |
| Entry | Exterior 1264, object 32240 | Arrive at interior 1266 `(0, 0, 0)` in room one; its encounter is reachable. |
| Room 1 to room 2 | Physical door 32205 at `(13, 1, 0)`, followed by teleport 32206 | Door blocked before victory; opens after victory; travel reaches the cave encounter. The teleport is a room-two transit, not another victory requirement. |
| Room 2 to room 3 | Teleport 32215 at `(2, -86, 0)` | Blocked before room-two victory; afterwards reaches the native transit leading through 32208 and 32209 to the grassy clearing. |
| Room-three transit | Teleports 32208 and 32209 | Travel within the unlocked third stage works before defeating its encounter; it does not advance the room counter or grant rewards. |
| Room 3 to room 4 | Physical door 32212 at `(36, 117, 0)` | Blocked before room-three victory; opens after victory and reaches the moon altar. |
| Final exit | Teleport 32211 at `(-5, 106, 18)` | After final victory, returns to exterior 1264 `(61, -35, 0)`. |

## Complete graphical acceptance, after deployment verification

1. Use two accounts in one group, ideally with heroes filling the available six places. Start outside any existing dungeon instance. For each independent player, use `!teleport 1264 61 -36 0` to reach the entrance, then enter through the actual entrance interaction. Do not teleport directly to interior room anchors.
2. Confirm all intended participants share the instance, can see each other, and see six initial enemies in the wooden-platform room. Confirm the first door is visibly closed and cannot be crossed before victory.
3. Fight normally at least once to verify placement, initiative, turn changes and combat completion. For a traversal-only repeat, `!winfight` may complete an active fight; this does not certify enemy or boss mechanics.
4. After room-one victory, confirm the first door visibly opens. Follow its native transit into the cave. Confirm seven enemies, reachable from the actual arrival; no boss appears here.
5. Before cave victory, try its forward transport and confirm rejection without changing map, room or party membership. Win the cave fight and follow the transport and subsequent passage into the grassy clearing. Confirm eight ordinary enemies.
6. Confirm all room-three transit links work, but the final physical gate remains closed until the third victory. Defeat the third encounter and cross the opened gate into the altar room.
7. Confirm exactly eight initial actors in the final encounter, including one Luna Gigante. Finish the fight, confirm rewards are delivered once, then use the native final exit. All participants must return outside without a black screen or stranded hero.
8. Re-enter as a group. Confirm a fresh run starts in room one, with doors closed and no inherited completion. In this second run, surrender with `!losefight`; confirm it does not unlock the next room. Use `!exitdungeon` and confirm clean exit and subsequent re-entry.
9. In a further run, reconnect between rooms two and three. Confirm retained progression, correct gate state, no duplicated groups, no repeated rewards, and successful completion from the retained stage.

Record the first failed step, character name, `!position` output and whether the other account has the same failure. This isolates a concrete connection or publication failure without replacing the full acceptance run with arbitrary coordinate jumps.

## Deployment and limits

The complete mixed-flow server source must be built and validated before this configuration is enabled. A database-only change on a server that lacks mixed traversal and same-stage transport support is insufficient. Preserve the shared combat and spell implementation during that build. Exact graphical gate state, party/hero transport and final exit remain manual acceptance requirements until observed.
