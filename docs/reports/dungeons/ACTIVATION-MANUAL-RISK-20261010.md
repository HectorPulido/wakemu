# Dungeon activation manual risk review — 2026-10-10

This is a read-only evidence review, not activation evidence. The ten teleport candidates were subsequently activated by the main workstream; runtime activation evidence is tracked separately. Risk priorities are inferred from literal geometry and transport complexity; they are not observed failures. No client assets, combat implementation or runtime state were changed.

## Recommended manual order

1. **Castillo de los Cangwejos:** four transport-separated rooms and stacked heights, including repeated XY coordinates at different Z. Check correct floor and arrival after every transport, forward lock before victory, backward transport after victory, and all party members moving together.
2. **Torre Helada:** four rooms and a final exterior landing distinct from the entrance position. Check every transition, return outside and fresh reentry.
3. **Arakna, Cocodrails Delnilo, Gerbilinda and Fábrica Buhatrás:** three-room transport progression; check nonleader exit/rejoin in the middle and party preservation.
4. **Crustariscos, Trópikos, Güinos and Vandalienados:** two-room controls for the transport system. Check forward lock, final return and fresh reentry.
5. **Demorribles, Fitoformes and Vaciantes:** high-level physical-flow candidates have documented unavailable boss casting levels (233). Their route can pass while the boss remains mechanically incomplete. Do not certify boss behavior from a route-only pass.

## Exterior navigation and native entrance identification

Use the command on **every ordinary player**, outside combat. These coordinates are the validated literal native exterior return landings, not invented door-approach cells. Find and click the listed native entrance nearby; Torre Helada requires walking from the return landing to its distinct entrance. Do not teleport directly into the internal map: that would bypass entry/party validation.

| Dungeon | Rooms | Exterior landing command | Native entrance object and position | Internal map |
| --- | ---: | --- | --- | ---: |
| Castillo de los Cangwejos | 4 | `!teleport 1135 64 -72 -59` | 18015 at (63, -72, -59) | 496 |
| Mazmorra Arakna | 3 | `!teleport 1264 -114 -29 60` | 32241 at (-114, -30, 60) | 1268 |
| Mazmorra Crustariscos | 2 | `!teleport 1276 -18 -359 1` | 32601 at (-18, -359, 1) | 1282 |
| Mazmorra de los Cocodrails Delnilo | 3 | `!teleport 999 -26 3 -80` | 26364 at (-26, 2, -80) | 1054 |
| Mazmorra de los Trópikos | 2 | `!teleport 999 -70 0 -78` | 25562 at (-71, 1, -76) | 1000 |
| Mazmorra Gerbilinda | 3 | `!teleport 1264 152 121 -80` | 32342 at (152, 120, -80) | 1270 |
| Mazmorra de los Güinos | 2 | `!teleport 1297 17 -135 27` | 32775 at (17, -135, 27) | 1300 |
| Mazmorra Vandalienados | 2 | `!teleport 1285 -13 -22 8` | 32603 at (-13, -22, 8) | 1284 |
| Torre Helada | 4 | `!teleport 508 -11 -24 0` | 18036 at (5, -20, 0) | 516 |
| Fábrica Buhatrás | 3 | `!teleport 1264 0 153 0` | 32272 at (0, 154, 0) | 1271 |

## Complete acceptance sequence

1. Leave any prior dungeon run with `!exitdungeon`. Form a party with three ordinary players and place all three at the same exterior landing from the table.
2. Leader clicks the native entrance. Every member must load the same instance, see each other and see the first monster group reachable from the arrival. No encounter may start behind a locked gate.
3. Try the forward transition before victory: it must not advance the party or reveal later groups.
4. Start the room fight. Verify normal combat initiation and turn order. Win normally; if the deployed console supports `!winfight`, it may accelerate a **flow-only** check after combat has started, but does not certify NPC mechanics.
5. Use the next native transition. All active members must reach the same next room and correct height, with exactly one next group. Repeat the premature transition check in each room.
6. In a middle room, a nonleader uses `!exitdungeon`, then reenters through the native entrance. The rejoining member must recover the same run without moving or replacing members still inside.
7. Use an available backward link: it must not reset progression, duplicate groups or award rewards again. Return forward and finish the final encounter.
8. Use the final native exit. Every transported member must return outside. Reenter as the same party: a fresh instance must begin in room one, with its first group and locked later progression.
9. Repeat once with heroes only after the ordinary three-player pass. Confirm the current assigned heroes join fights, removed heroes stay out, surrender cleans up the fight and the next encounter can start. Spell-bar behavior belongs to the separate spell workstream.

Record dungeon, room number, affected player, leader/nonleader status, precise action and whether the failure concerns visible door state, collision, transition, party location, fight completion or rewards. Keep route acceptance separate from boss spell acceptance.

## Expanded physical batch: adapted room composition

These eight additions had an earlier guide/native room-count mismatch. The expanded policy binds encounters to the native physical regions and generates missing composition slots from the native species pool. This is an explicit local playable configuration, not certification of the original guide encounter order or official composition. The new batch therefore deserves a manual pass before treating it like the accepted Tofullero.

Prioritize **Fuente del Mal**, then **Cañón de los Plaguepardos** and **Volcán Or’Hodruin**: each has three physical stages despite the guide mismatch, so check that each victory reveals exactly one encounter, the final stage contains the intended boss and no region is silently skipped. Then test the five two-stage adaptations, watching for a boss appearing too early or a group beyond an already open gate. Expected stage counts are those listed below, irrespective of the archived guide.

The commands again use validated native exterior return landings. Every player should use the command, locate the listed native entrance and enter together. Apply the complete acceptance sequence above; check both visible door state and physical crossing after each victory.

| Dungeon | Expected physical stages | Exterior landing command | Native entrance object and position | Internal map |
| --- | ---: | --- | --- | ---: |
| Fuente del Mal | 3 | `!teleport 1252 51 -27 -80` | 31856 at (51, -27, -80) | 1254 |
| Cañón de los Plaguepardos | 3 | `!teleport 1252 -168 -156 -50` | 31867 at (-168, -156, -50) | 1257 |
| Volcán Or'Hodruin | 3 | `!teleport 1123 -31 -1 -58` | 28036 at (-32, -1, -58) | 1131 |
| Mazmorra Kaníbola | 2 | `!teleport 999 19 -145 -80` | 25568 at (20, -146, -80) | 1007 |
| Mazmorra de las Kanívoras | 2 | `!teleport 1053 108 -18 -20` | 26470 at (108, -19, -20) | 1006 |
| Mazmorra de los Plantiguardias | 2 | `!teleport 1295 -245 0 -80` | 32869 at (-244, -1, -80) | 1296 |
| Cresta Helada | 2 | `!teleport 1124 -49 -101 60` | 28229 at (-51, -101, 60) | 1133 |
| Tumba de Pandala | 2 | `!teleport 1252 71 -167 -72` | 31935 at (72, -167, -72) | 1255 |

Evidence: `EXPANDED-PHYSICAL-CANDIDATES.json` and its exact frozen configurations. The batch file also includes eight previously prepared physical configurations; those are not eight further new dungeons. Boss AI and special mechanics remain independently unproved.

## Inventory denominator and existing systems

The inventory union contains **156 records**, combining native definitions, legacy guide-only records, variants and special content such as rifts. It is not a count of 156 distinct ordinary current dungeons. A record rejected or unsupported by this physical/teleport dungeon extractor means that this extractor lacks the evidence needed for that controller path. It does **not** mean an existing rift implementation is broken, disabled or needs replacement. Previously accepted dimensional rift gameplay remains a separate system and acceptance result.

## Hard blockers and the evidence required to clear them

### Sliptorium — final exterior return not established

The transport extractor proves three regions on map 325: region 3 → 18 → 17. Forward links are source object 14010 / destination 693 (arrival 208, 106, 0), then source object 27552 / destination 899 (arrival 144, -54, 0). Backward links 14011 and 16126 return to earlier regions. This proves internal sequencing only. Complete configuration preparation rejects the candidate with **`No unique free native exterior exit for room 3`**.

Do not activate a full route based on `!exitdungeon` alone. Recover the final-room exit object, its literal native exterior destination and a directed walkable approach from the final arrival; validate destination terrain and absence of item/kama/mission restrictions under the open-access policy. If the correct official exit requires backtracking, document that explicit route and teach the controller that contract before activation. The current report does not prove the exit is absent; it proves the automatic validator cannot bind one unambiguously.

### Mixed physical gates and transport — possible bypasses

| Dungeon | Route | Walking door chain | Internal transport links |
| --- | --- | --- | ---: |
| Hacienda de la Balinería | native_dungeon_145 | 24178, 24179, 24180 | 2 |
| Montaña Conohos | native_dungeon_136 | 31408, 31409, 31410, 31411, 31412 | 2 |
| Neohacienda de la Balinería | native_dungeon_211 | 35310, 35309 | 2 |
| Escarantera Abandonada | native_dungeon_151 | 24171, 24172 | 1 |

These maps have a directed walking chain, but an internal native transport may cross locked physical regions. Clearing the blocker requires one combined graph with every physical gate and literal transport edge, verifying forward locks and backwards links in each committed progression state. Ignoring the transport or blocking it blindly is not a proved solution.

### Remaining inventory — independent evidence gates

The broad physical composition audit reports missing final boss identity, guide/native room-count mismatches, unresolved native monster identities, or unsupported quantities exceeding combat capacity. A topology-only candidate is not ready for activation. Guides can describe another game revision, so a mismatched room count must be reconciled against the local native map and an explicit local composition policy rather than silently dropping rooms. Teleport candidates have their own later audit; do not count a teleport route as blocked solely because the earlier physical audit could not prove it.

Boss spells and special mechanics remain independent blockers to **faithful encounter acceptance**, even where route activation is allowed. The physical readiness report documents missing owned spell roots and unavailable casting levels; this task does not invent attacks or modify the combat engine.

## Evidence

- `AUTOMATIC-TELEPORT-COMPLETE-CANDIDATES.json`: complete/offline preparation and Sliptorium rejection.
- `AUTOMATIC-TELEPORT-FLOW.json`: exact internal transport sequence and native link bindings.
- `AUTOMATIC-NATIVE-FLOW-COVERAGE.json`: mixed-flow route identities and walking chains.
- `AUTOMATIC-COMPOSITION-COVERAGE.json` and `AUTOMATIC-TELEPORT-COMPOSITION-COVERAGE.json`: independent roster gates.
- `AUTOMATIC-ACTIVATION-READINESS.md`: physical boss spell gaps.
- `.runtime/local/native-teleport-complete-candidates/*.json`: exact native exterior destinations used in this guide.
- `.runtime/local/methodwakfu-dungeons/inventory-native-snapshot/native-map-objects.json`: entrance object coordinates.
