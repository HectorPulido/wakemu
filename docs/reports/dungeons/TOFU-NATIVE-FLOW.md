# Tofu: native exploration flow proved automatically

The earlier unresolved entrance component was a movement-profile mismatch, not evidence of a missing teleporter. The published combat geometry uses `Sm(3,0,2,true)`. The installed player exploration profile is `Sm(6,0,4,true)`: `biB → bjo → big → eGj` inherits `bcK() = 6`, `bcL() = 0`, and `bvz() = 4`; `faz.fSR()` configures native `Sm` from those actor methods. Both native breed implementations also use height 6. Combat geometry remains untouched.

Native stair transitions connect `(15..17,-31,-2)` to `(15..17,-32,-6)`. Their height difference of four exceeds the published combat export's jump capacity of two, but the actual player profile accepts the transitions. All eight native topology chunks were decoded, without a guessed bounding box or invented edges.

The directed native physical route is:

1. Enter at `(14,-25,0)` and descend the native stairs into the first encounter area.
2. Cross Door **26874**, `(23,-35,-8)`, to the second area.
3. Cross Door **26875**, `(39,-26,-12)`, to the third area.
4. Reach exit teleporter **26872**, `(33,-5,-12)`.

The graph proof keeps both active doors blocked initially, then opens 26874, then both. The exit is unreachable in the first two states and reachable in the last. The evidence includes actual directed cell-by-cell path witnesses, not merely undirected component adjacency. Hidden Door 26873 is not a separator and is not used as a progression gate.

This proves physical traversal and gate order. It does **not** establish which fight completion changes each door's state, official group spawn anchors, or boss mechanics. Those need separate server scenario/event evidence. Door obstruction itself is native coordinate-specific collision, as documented in [the geometry report](GEOMETRY-TOPOLOGY.md).

## Reproduce offline

```sh
mkdir -p .runtime/local/tofu-native-flow/classes
javac -proc:none -classpath 'client/lib/*' -d .runtime/local/tofu-native-flow/classes sniffer/java/ExportNativeExplorationMap.java
java -cp '.runtime/local/tofu-native-flow/classes:client/lib/*' ExportNativeExplorationMap 1087 .runtime/local/tofu-native-flow/exploration-1087.json
python3 server/tools/extract_native_door_flow.py .runtime/local/tofu-native-flow/exploration-1087.json --entry 14 -25 0 --exit 33 -5 -12 --output docs/reports/dungeons/TOFU-NATIVE-FLOW.json
```

The Java exporter accepts any installed map ID and reads all native chunks. The Python proof accepts any exact entry/exit and native Door set; it refuses branching, disconnected gates, and missing directed paths rather than fabricating a route. Output hashes pin both the installed client JAR and topology archive. No runtime writes, restarts, or combat changes are involved.

## Source implementation: physical-room configuration v3

Migration `094_tofu_native_physical_rooms.sql` installs a new immutable configuration for `native_dungeon_27`. Existing pinned runs retain their prior version. New runs use three disjoint native exploration regions, the original entrance, two physical walking gates, and native entrance/final exit objects. The frozen exploration graph uses the verified player profile; published combat geometry and spell behavior remain unchanged.

The explicit DEV policy opens each gate only when durable room progression advances after victory. This implements playable ordered progression without claiming recovered official server scripts. The reusable `dungeon_physical_doors` helper emits native state 1 for closed gates and state 0 for opened gates, and validates movement against the frozen directed graph, including diagonal corner checks to prevent walking around a locked gate. Reconnect uses the committed frontier.

The three encounter anchors are `(16,-37,-8)`, `(37,-34,-9)`, and `(39,-13,-12)`. Existing combat formation selection successfully places eight enemies and reserves six player slots in each corresponding region using the original combat graph. The roster is an explicit generated policy over native species 4, 5, 6 and 704: eight regular monsters in rooms one and two, seven regular monsters plus exactly one Tofu Royal (1259) in room three. Exact official per-room quantities remain unverified; they are no longer conflated with this DEV policy.

The generated frozen configuration is [TOFU-RUNTIME-V3.json](TOFU-RUNTIME-V3.json). `server/tools/build_physical_dungeon_configuration.py` builds its topology, validates the roster/configuration hashes and generates the migration. Dispatcher integration and automated acceptance are tracked separately; no restart or deployment occurred during this implementation.

## Mandatory first encounter acceptance

The first group belongs to the same closed-gate connected region as the exact native arrival `(14,-25,0)`. Actual original-combat-graph formation places its eight actors at `(16,-40,-8)`, `(15,-40,-8)`, `(16,-41,-8)`, `(16,-39,-8)`, `(17,-40,-8)`, `(14,-40,-8)`, `(15,-41,-8)` and `(15,-39,-8)`. No Tofu Royal occurs in that group.

With **both progression gates closed** and all eight actor coordinates treated as occupied, the frozen directed player graph has a 14-step path from native arrival to `(15,-38,-8)`, adjacent at equal height to the actor at `(15,-39,-8)`. This path descends the ordinary entrance stairs and stays entirely inside room one; it requires no teleport or prior victory. The exact witness is [TOFU-FIRST-GROUP-REACHABILITY.json](TOFU-FIRST-GROUP-REACHABILITY.json), enforced by `test_first_group_can_be_engaged_from_native_arrival_with_both_doors_closed`.

## Manual acceptance on r63 and follow-up corrections

Hector confirmed the complete Tofu room progression and the native manual exit work on r63. Two remaining defects were reported: opened gates retained their closed graphic, and `!exitdungeon` did not leave the run.

The source correction synchronizes native Door visibility with collision: closed gates use state 1 and remain visible; opened gates use state 0 and hide their obstructing graphic. A headless installed-client oracle attaches a `bEy` view to the real `bBk` model and verifies the partial packet updates both loaded-view visibility and collision. This deliberately clears the closed visual; it does not claim recovery of an official opening animation.

The command previously accepted only automatic-anchor topology and required a `completion_destination` absent from immutable physical-door v3. Physical-door commands now resolve the frozen entrance exit object against the native transport catalog, preserving native destination criteria, costs and walkable altitude checks. The existing durable per-member leave transaction preserves other party members and pending delivery. No immutable configuration was rewritten. Tests cover the native exterior route, wrong map, costly/missing/ambiguous routes and a real PostgreSQL per-member exit with durable outbox.

These follow-up fixes remain source-only until a later authorized complete build and restart. The already accepted three-room progression is unchanged.

Follow-up automatic validation passed: 25 focused pure tests, three PostgreSQL first-room/run tests, nine PostgreSQL exit tests, and the installed-client model/view oracle. This evidence validates prepared source; it is not a claim that r63 contains the correction.

After the future complete build and restart, accept the two corrections in one run:

1. Enter Tofu with two party members. Verify the first group remains reachable from native arrival while both progression gates are closed.
2. Win the first encounter. Gate 26874 should stop obstructing movement **and its closed graphic should disappear**; gate 26875 should remain visible and blocked. Reconnect once and verify the same state.
3. Win the second encounter. Gate 26875 should likewise clear its closed graphic and obstruction. The final group should contain exactly one Tofu Royal.
4. Outside combat, use `!exitdungeon` on one member. That character should return outside the entrance, the other should stay in the private run, and neither should lose party membership. The Spanish alias `!salirmazmorra` uses the same handler.
5. The remaining member can finish the final encounter and leave through the previously accepted native exit. A command during combat should remain rejected.

### Party transport and reentry follow-up (2026-10-10, source prepared)

Manual testing confirmed `!exitdungeon` succeeds. A two-player entry then
exposed two independent general transition defects. Read-only runtime evidence
at 05:37–05:39 UTC showed both characters atomically moved into run
144115188075855881, but companion 4's entry event 37 remained pending while
leader 13's entry 38 and exterior return 39 were acknowledged. Worker delivery
previously required exact source coordinates, so ordinary walking within the
same source scene could prevent delivery indefinitely. Delivery now accepts the
same source map and instance, retaining authoritative destination, generation,
hydration and acknowledgement checks.

The leader's reentry was rejected with `Party already owns a different active
dungeon session`: the returned leader had been excluded from comparison with
the frozen roster while the companion retained active membership. Existing-run
entry now compares the complete frozen roster, permits a selected frozen member
to rejoin, and moves only members outside the dungeon. Companions already inside
retain their position and progress. Creating a new run still requires the party
leader; adding new members to a frozen run remains rejected.

Automated regression covers two- and three-member parties, leader and ordinary
member exterior return/reentry, and preservation of the inside companion's
position. Manual acceptance after deployment: enter together while a companion
walks near the entrance; all clients must load the same instance. One member
uses `!exitdungeon`, enters again while another remains inside, and must rejoin
the same run without moving the inside member. Repeat with the nonleader, then
exit everyone and enter again to obtain a fresh run.


### Manual acceptance update — 2026-10-10

Hector completed the Tofullero boss and exited successfully. The complete solo
room progression and exterior return are accepted. He also confirmed
`!exitdungeon` works and the opened gate disappears, allowing continuation to
the final room. These confirmations supersede the earlier command and closed
gate visual defects.

Party transport and reentry are still pending acceptance. Leaving the party
allowed reentry during the reported failure, consistent with the retained
active run/frozen roster mismatch. General source corrections preserve the
party and permit returned frozen members to rejoin the same active instance;
companions already inside keep their position. Companion transition delivery
now tolerates movement within the source map and instance. These follow-up
changes are prepared and tested, but have not been deployed or manually
accepted. No restart was performed for this update.

### Stale private-location login recovery — 2026-10-10

A companion whose durable entry remained pending subsequently left the social
party while retaining private dungeon coordinates. Login selection then rejected
`Dungeon recovery membership is not active` before the initial map bootstrap.
The individual runtime character was repaired separately by the coordinator using
the pinned validated exterior destination and explicit absence-of-combat checks.

The general source correction now returns invalid/inactive dungeon membership
to the pinned validated exterior during selection, supersedes obsolete pending
travel, and closes the run only if no active members remain. The worker reloads
the resulting exterior character before constructing its initial bootstrap.
Valid active combat recovery remains inside even if social membership was lost;
invalid membership during live combat is never forcibly transported outside.
Four isolated PostgreSQL tests pass, including missing social membership,
returned membership, completed/closed runs, and live-combat location preservation.
This general correction is prepared in source; its deployment remains separate
from the individual runtime repair.
