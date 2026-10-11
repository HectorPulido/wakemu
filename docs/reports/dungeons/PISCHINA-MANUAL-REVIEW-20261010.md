# La Pischina: native four-room review

## Scope and deployment

Native dungeon 143 uses interior map 912 and exterior map 1208. This review prepares a source-only configuration; it does not activate it, restart world, or certify the original server's trigger scripts. The four main encounter arenas are recovered from native walking geometry and literal PositionTrigger locations. Encounter quantities are explicitly local progressive family compositions, not recovered official quantities.

Candidate: [V10 configuration evidence](PISCHINA-NATIVE-TRIGGER-CANDIDATE-V10-20261010.json). Geometry: [directed boundary evidence](PISCHINA-NATIVE-ARENA-GEOMETRY-20261010.json), [annotated map](PISCHINA-NATIVE-GEOMETRY-ANNOTATED-20261010.svg).

## Main route

| Room | Native arena cells, excluding frontiers | Initial enemies | Native-minimum composition metric | Frontier into next room |
| --- | ---: | ---: | ---: | --- |
| 1 | 220 | 2 | 226 | PositionTrigger 31447 at `(24,15,1)` |
| 2 | 183 | 4 | 456 | PositionTrigger 31448 at `(33,6,1)` |
| 3 | 231 | 6 | 686 | PositionTriggers 31449 `(52,-4,1)` and 31450 `(53,-4,1)` |
| 4 | 270 | 8 | 939 | Final native exit 24197 |

The metric is sum of enemy count times actual deterministic spawn level; it demonstrates increasing composition, not complete combat difficulty or boss-mechanic fidelity. Main boss reference 4727, Zespadín Negro, appears only in room four. Main generated groups contain ordinary fish-family references 4723–4726; conditional reference 4889 is excluded.

The native entrance object is 14589 at exterior `(17,56,-36)`; its actual interior arrival is `(22,38,0)`. Entry and final exit objects 24196 and 24197 both return to native destination 543 at exterior `(17,57,-36)`.

The previous Door-only extractor merged the four arenas into one 908-cell region. Cutting the four literal PositionTrigger cells recovers all four arenas. The final boundary has two parallel cells: closing only one permits a bypass. The configuration assigns frontier cells to the destination room; existing server movement authorization blocks locked rooms without changing native walk edges or emitting fabricated Door packets.

## Optional content and limits

Door 31487 connects room three to a 254-cell optional annex. Its lower doors 24202/24203/31444/31445 have unresolved elevation/footprint semantics and are not treated as mandatory progression barriers. Palancas, optional chest interactions and conditional encounter activation are not completed by this main-route fix.

[MethodWakfu's archmonster index](https://methodwakfu.com/pvm/les-archimonstres/) identifies Léviathon as a conditional fishing encounter requiring fishing level 35; [its Mimic index](https://methodwakfu.com/bien-debuter/mimics/) lists room-three levers. These contextual references do not establish an exact native spawn coordinate or a complete puzzle implementation. Genuine optional archmonsters remain allowed by user policy when their native location and activation are implemented; they are excluded only from invented main-room groups.

## Complete manual acceptance after deployment

Automated verification passed: [isolated PostgreSQL lifecycle](PISCHINA-NATIVE-TRIGGER-PG-LIFECYCLE-V10-20261010.json) checks six real group arrivals, four spawn/victory receipts, all four trigger cells, premature bypass rejection and final native exit. The candidate preserves exactly 1173 native walking cells and 3891 directed edges. Fourteen existing extraction/structural-audit tests also passed; a separate movement regression passed 16 tests with two PostgreSQL tests skipped in that URL-free invocation. Graphical combat and optional puzzles are outside those checks.

1. Form one group with two independently controlled accounts and, if available, heroes up to six participants. Move each independent player outside using `!teleport 1208 17 56 -36`, then enter through the actual entrance interaction. Do not teleport to interior anchors.
2. Confirm the group arrives together in room one and can engage its two enemies. Before winning, attempt the passage near `(24,15,1)`; entering room two must be rejected.
3. Finish room one normally. Confirm all members can pass into room two, its four enemies are visible and combat has space for all six participants. The next passage remains blocked before victory.
4. Win room two and continue to room three with six enemies. Before winning, attempt both adjacent passages near `(52,-4,1)` and `(53,-4,1)`. Neither may reach room four.
5. Win room three. Confirm both passages now work, all members can reach the final room, and its eight initial enemies include exactly one Zespadín Negro. No Léviathon should appear in any generated main encounter.
6. Defeat the boss and use the actual final exit. Confirm the entire participating group returns outside with no stale combat or instance membership.
7. Re-enter as a group, verify a fresh room-one encounter and locked later rooms, then surrender. Surrender must not unlock room two. Use `!exitdungeon`; verify exit and subsequent re-entry work.
8. Treat the annex levers, conditional encounter and chest as separate pending optional-content tests; their absence must not prevent the four-room main route from completing.

## Transferable result

Extraction must inspect literal PositionTriggers as candidate native walk-graph separators, in addition to physical doors and transports. Confirm directed reachability, every parallel crossing, declared arena count, real arrival/exit and six-player formations before preparing a route. [Read-only inventory scan](NATIVE-POSITION-TRIGGER-CUT-SCAN-20261010.json) found no additional candidate with this exact pattern. Its 80-cell discovery threshold is a heuristic and does not prove that other maps lack scripted triggers.

The reusable `server/tools/extract_native_trigger_frontiers.py` independently reproduces La Pischina's four arenas. Seven synthetic regression tests pass for linear ordering, connected/disconnected parallel cuts, omitted-lane bypass, invalid native identities/positions, mismatched counts and cyclic/branched cuts. Run with `PYTHONPATH=server:server/tests:server/tools .runtime/local/verification-venv/bin/python -m unittest test_native_trigger_frontiers test_mixed_native_flow_extraction test_classic_dungeon_hybrid_structure_audit` (21 tests passed).

Updated source coverage is 94/107 distinct ordinary main routes prepared, with 13 structurally pending. This increment does not change deployed coverage (37 ordinary native routes plus 10 ultimate-boss arenas) and does not certify optional annex content.
