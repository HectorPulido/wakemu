# Vid Vil: complete manual acceptance after deployment

This is a source-only four-room replacement for the earlier incomplete three-room proposal. No deployment or restart is implied. [Native geometry and annotated map](VID-VIL-NATIVE-GEOMETRY-REVIEW-20261010.md) and [frozen candidate](VID-VIL-NATIVE-HUB-CANDIDATE-V11-20261010.json) preserve literal native paths, arrivals and exits.

The [isolated PostgreSQL lifecycle](VID-VIL-NATIVE-HUB-PG-LIFECYCLE-V11-20261010.json) passed with six players and four room victories. It verifies rejection before room three and also rejection when its victory receipt is hidden despite frontier four and the room-two receipt; both native returns, repeated forward travel, atomic group outbox, receipt replay and final native exit pass. Milubo and Pischina lifecycle regressions also passed against the updated shared implementation. These tests do not simulate combat or certify original boss mechanics.

## Expected complete route

Four encounters have 2, 4, 6 and 8 initial actors, using an explicitly local increasing family composition. The final group includes native bosses Suma sacerdotisa Sydonia (4060) and Copampino (4061), once each. Quantity and native-minimum level progression do not certify original boss scripts or encounter difficulty.

Native travel follows entrance → room one → central room two → branch room three → central room two again → boss room four. The return to room two must not regenerate its encounter or reduce the committed progression frontier. Boss access from that central room requires the third-room victory, rather than the central room's earlier victory.

## Steps

1. Use a group with two independently controlled accounts and, if available, heroes up to six places. Move each independently controlled player outside using `!teleport 323 58 -69 0`, then interact with the real entrance. All participants must arrive in the same private instance; do not teleport to interior anchors.
2. Engage and defeat the two enemies in the first arena. Before victory, its next-room transport must remain unavailable. Afterwards, use native transport 26745 to reach the central arena.
3. Defeat the four enemies in the central arena. There are two outgoing branches: transport 26751 must now lead to room three, while boss transport 26747 must remain unavailable. Try the boss branch before completing room three and verify it cannot skip that encounter.
4. Use 26751 and defeat the six enemies in room three. Use return transport 26750 to go back to the central arena. The central room must stay cleared and all group members must return together.
5. Use the now-available boss transport 26747. All participants must arrive in the final arena, whose eight actors include exactly one of each native boss. Placement must leave room for all six participants.
6. Before victory, verify the final exterior exit 26749 cannot finish the run. If testing the optional native return 26748 to the center, confirm it preserves progress and does not create another encounter or victory; return to the boss arena through 26747.
7. Finish the final fight and use native exit 26749. Participants must return to exterior map 323 near `(59,-69,0)` without stale combat or dungeon membership.
8. Re-enter together. Verify fresh room-one enemies and locked later branches. Surrender in this fresh run; it must not unlock the next encounter. Use `!exitdungeon`, then confirm the party can enter again.

## General mechanism

The explicit mixed-native binding field `progression_gate_room` permits a reviewed nonadjacent route only when it equals the higher endpoint minus one. Both Vid Vil bindings 2→4 and 4→2 declare gate 3. Runtime still verifies exact catalog source/destination, native approaches and committed unlocked endpoints. Forward transport checks the destination-minus-one victory receipt; reverse transport preserves progress. Existing adjacent and same-stage contracts remain unchanged.

This support is reusable for hub layouts and returns, but does not automatically certify other branched or cyclic dungeons. Their encounter assignment, arrivals, native exits and complete route witnesses must still be proved.

The updated [all-classic structural audit](POST-VID-VIL-ALL-CLASSIC-STRUCTURE-AUDIT-20261010.json) selects Vid Vil's four-room replacement and reports no findings for that route. Source coverage becomes 95/107 distinct ordinary main routes prepared, with 12 structurally pending. Deployment coverage is unchanged.
