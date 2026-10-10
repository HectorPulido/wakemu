# Duel arena and team placement policy

The duel runtime previously disabled NPC relocation and thereby selected the radius-89 bounded arena policy. This coupled player-coordinate preservation to an unnecessarily large terrain crop. Duel setup now independently requests compact selection with a 30 by 30 minimum, a 2,500-cell rectangle budget, and preservation of both exterior positions as durable return authority. Combat actors automatically start on opposite native interior sides. Native reachable components smaller than the requested minimum remain valid; no terrain is invented. Exterior separation exceeding the compact selection budget is rejected; combat-only placement never updates the exterior character rows.

Ordinary PvE keeps the existing randomized 5 to 7 minimum dimensions. Its initial NPC formation now chooses the distant native interior and distributes subsequent opponents across that side, rather than retaining adjacent world positions or aiming for six path steps.

Placement zones for both modes use two opposite native-distance anchors. Candidates prefer their respective side and maximize spacing among that team's already selected slots. Every actor's combat starting coordinate remains selectable, and the two duelists automatically use separated starts. Candidates are native-reachable and never overlap. Perimeter avoidance remains preferred, with existing small-component capacity behavior intact.

The implementation computes a fixed number of native BFS distance fields and performs slot-bounded coordinate scoring (12 slots per team); it does not run a path search for every candidate cell.

Validation: `test_friendly_duel_compact_arena.py` (5 passed), `test_combat_arena_selection.py` (14 passed). Host placement suite passed six fixture tests; its installed-map integration requires the PostgreSQL/catalog environment and was delegated for validation.

Manual acceptance: challenge another character while adjacent on an open map. The duel should offer approximately 30 by 30 terrain rather than the radius-89 crop, with selectable cells spread across opposite sides. Both players initially appear on opposite native interior sides and can move within their placement cells; ending the fight restores the captured exterior coordinates. In a PvE encounter, NPCs should start on the distant side and multiple NPCs should occupy distributed native cells. Narrow maps must still use their actual available terrain; collision, heights, movement and spell targeting remain native.

## Automatic duel starts

The user subsequently requested automatic initial separation. Duel actors now start at opposite native interior positions selected from the authoritative frozen placement regions. Two native BFS fields select the starts, and snapshot-owned character copies use matching coordinates. Original character dictionaries, durable exterior character positions, and invitation return authority remain unchanged. Starts are recomputed after placement freeze so retries respect the committed layout. Both clients receive the same initial placement packet batch. The durable placement producer now forwards compact spreading and perimeter avoidance when regenerating zones; previously that producer discarded both options.

Focused validation now includes six arena and formation tests, including adjacent duelists starting more than 30 coordinate steps apart on open native terrain. PostgreSQL runtime/snapshot/return validation was delegated.

## Final runtime verification

Thirty focused tests passed, including an isolated PostgreSQL end-to-end duel
on installed map 527. It verifies initial combat separation greater than 30
Manhattan steps, placement membership, native physical snapshots, identical
13652 position packets for both viewers, untouched exterior rows during combat,
surrender restoring full HP and original exterior positions, and a repeat duel.
Map 1134 only provides 45 mutually reachable cells and cannot meet the wide-arena
contract; its terrain must not be expanded with invented cells.

The running shared image `wakemu-world:titles-ownership-fix-20261010` was compared
with the complete r67 build: all 687 source/migration hashes matched. World
started at 06:35:35 UTC, after the mounted AI ordering change at 06:26 UTC.
The continuous profiler was reattached to the current process and reports no
error. Live user acceptance remains pending. Subsequent unrelated workspace
edits are not implicitly certified by this snapshot verification.
