# Complete dungeon manual acceptance

**Installed and ready for Hector's manual acceptance (2026-10-08).**
The normal `wakemu_runtime` database contains all 87 configurations and registered
routes. The single healthy world runs `wakemu-world:complete-20261008-r27`, image
`2146341ba3b1a71f5027a32b451b9edff866994b023b68671f5a67036c1dbd72`.
The earlier 335 dungeon and three disposable-heartbeat checks passed without skips.
The current scene-hydration, regeneration, checkpoint-order and plant-growth batch passed 94 checks. Earlier
real two-player runs verified victories and automatic travel through rooms one
and two. Full TLS acceptance did not finish: the last run exceeded its one-hour
limit. Manual client acceptance remains pending; no full automated pass is claimed.
See [all installed entry commands](INSTALLED-DUNGEONS.md).
The selected all-guide bundle contains 87 configurations. Generated compositions
and accessible-anchor room ordering are explicitly local policies, not official
Wakfu encounter data. Known reviewed Jalató quantities remain **3 / 5 / 6**.
Native entry criteria remain enforced. Routes requiring unavailable trusted
quest state or unsupported item-cost handling are rejected; this procedure
does not waive quest, event, server-mode, or payment requirements.

## Setup: two separate clients

Use A and B on separate accounts. Both need the development commands below.
Keep free inventory slots. Record each character's XP, kamas, and items.
On **both** clients, in general chat outside combat, enter:

```text
!level 40
!teleport 527 -245 -89 0
!position
```

Expected: level 40, exterior map 527, instance 0, position `-245 -89 0`.
If a command is denied, record its exact response; do not substitute another
command. A invites B through the character menu; B accepts. Both must display
the same two-member party, with A as leader.

## Enter and finish all three rooms

1. A interacts with the Jalató dungeon entrance beside the prepared position and
   chooses its normal enter action. Allow normal automatic approach. B stays
   next to A; B does not create another run.
   **Expected:** both enter map 1086 together, see each other, and share the same
   positive private instance. Run `!position` on both and record that instance ID.
2. Verify the first group has **three monsters**. A attacks the group and waits
   during placement. B clicks the player-side combat swords and chooses
   **Join**. Both must appear in the same fight, in distinct placement cells.
   Both press **Ready**, take their turns, and defeat the complete group.
   **Expected:** both receive their own victory result, XP, kamas, and any rolled
   drops. Random rewards need not be identical between players.
3. Close both results and wait for automatic whole-party transfer. Run `!position`
   on both. **Expected:** room two on map 1086, same private instance, with
   **five monsters**. Both join, ready, and defeat this group using step 2.
4. Close both results and wait for the next automatic transfer. Run `!position` on
   both. **Expected:** room three, same map and private instance, with **six
   monsters**. Both join, ready, and defeat this final group.
5. Close both results and wait. **Expected:** both automatically return to the
   exterior, map 527, instance 0, position `-245 -89 0`. No fourth room or second
   copy of any fight reward appears. Both can walk and open inventory.

Exact positions for this selected manifest:

| Stage | Map | Position | Monsters | Instance |
| --- | --- | --- | --- | --- |
| Exterior / final return | 527 | `-245 -89 0` | — | 0 |
| Room one | 1086 | `147 -157 0` | 3 | Shared positive private ID |
| Room two | 1086 | `2 -161 0` | 5 | Same private ID |
| Room three | 1086 | `149 -16 0` | 6 | Same private ID |

Do not walk through scenery or search for a forward door to advance this
accessible-anchor configuration. Victory and return to exploration trigger the
transfer. An exterior player must not see these private groups or their markers.

## Reconnection, surrender, and retry in a new run

1. A uses the same entrance again with B nearby. **Expected:** both enter a new
   private run with exactly one three-monster room-one group.
2. A changes character and returns, then B does the same. Run `!position` on both.
   **Expected:** the same run and room are restored; party view and existing
   group remain, without duplicate groups or reset progression.
3. Both enter the same room-one fight as above. During active combat, A uses the
   normal surrender action. **Expected:** A returns to exploration; B remains
   in the fight and can act. B then surrenders too.
4. **Expected:** no victory rewards, no automatic advance, both still in room
   one in the same run, and exactly one available group to retry. Both can walk
   and open inventory. Do not disconnect to simulate surrender.
5. Both fight that same group again and win. **Expected:** rewards reach both,
   then both advance exactly once to room two. Repeat both-player victories in
   rooms two and three and verify the automatic exterior return again.
6. Change character and return on both clients, then restart both clients.
   **Expected:** final exterior positions, normal party/inventory controls, and
   rewards preserved without duplication or stale combat attachment.
7. Enter one more run. **Expected:** a fresh private instance and one initial
   group, proving a completed run does not block subsequent entry.

## Optional spectator check

Use a third client C. Outside combat run the same three setup commands on C,
invite C into the party, and begin a fresh party run with all three together.
A and B join the fight; C stays outside it inside the same private instance.
C clicks the combat swords and chooses **Watch**.

Expected: C sees both participants, monsters, actions, and the final result
without controlling a fighter or receiving combat XP, kamas, or drops. After
leaving spectator mode, C can walk and open inventory. Record whether C follows
the automatic party transfer; do not treat an exterior character as an
instance-authorized spectator.

## Other installed configurations and result record

Repeat the same complete entry, shared fights, automatic advances, final return,
reconnection, and retry flow against a specifically selected installed route.
Use that configuration's exact entry command, native criteria, costs, room
counts, anchors, and exterior destination. Do not reuse Jalató coordinates or
quantities for another dungeon. Root must provide those exact selected values
before asking Hector to run another case.

Record the installed bundle hash/version, date, character labels, instance IDs,
observed room counts, both-player participation and rewards, automatic transfers,
final return, reconnect persistence, and retry result. For a failure, record the
step, exact client message, and screenshot. The issue remains unconfirmed until
this complete procedure succeeds on the intended installed runtime.

## Initial hydration, passives and escape regression

1. Reconnect both clients and stay still. Existing map actors and native interactive objects must load without moving. Check the local Drago, Zaap, crafting tables and dungeon entrance.
2. Leave and re-enter the map, then reconnect once more. The same current interactive states and active fight swords must appear after loading.
3. With Npers at level 50, open the spell inventory. Common passives requiring levels 10, 15, 25 and 35 must be owned and unlocked; common passives requiring 55 and above remain locked.
4. Complete the two-player dungeon procedure above. Confirm both players can join each fight and remain connected through the victory and transfer.
5. Outside combat in a dungeon, enter `!exitdungeon`. Only the issuing player returns to the exterior; the other member retains their run. Both can walk and use inventory.
6. If a disconnection happens, record the character and approximate time. The server now records the precise session classification, combat and turn, renewal age and slow-operation timings.

Visual client acceptance remains pending. Native interactive replay is complete; permanent story NPC placement still needs a verified independent actor catalog.

## Same-map scene loading and recovery after combat

1. Outside combat, run `!teleport 527 -219 -40 0`. Wait for the Tainela Drago to appear and open its transport interaction.
2. Walk to the Gobball entrance at `-245 -89`; do not teleport for this leg. The entrance must become interactive after local scene loading. Open and close the dungeon options.
3. Walk back to the Drago, then repeat the round trip. Returning must restore the objects after their scene partitions have unloaded; short movements must receive delayed local dynamic states rather than full-map reconstruction.
4. Finish a normal battle while injured. Remain outside combat for at least ten seconds, then reconnect and wait ten seconds. HP regeneration must produce updates without disconnecting the character.

If walking still stalls, record the time and route. The movement log now contains elapsed time and separate cancellation, position, publication and ecology timings; visual smoothness is pending manual verification.

The r26 visible round trip failed; the overlapping-partition exclusion was removed in r27 for all object types. Visual acceptance remains pending. The chat must show “Guardando el estado del combate…” before checkpoint submission, after already-committed combat packets are delivered.
