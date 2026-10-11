# Exhaustive classic PositionTrigger cut audit V2

Coverage: all 109 classic definitions / 107 names, 109 native maps, zero missing exploration geometry. No component-size threshold is used. Every definition retains its audited configuration scopes, including definitions without a prepared configuration.

| Result | Maps |
| --- | ---: |
| No native PositionTrigger objects | 104 |
| Native triggers, no literal separator proved | 4 |
| Directed literal separator candidates | 1 |

La Pischina is the only positive result: 31447 and 31448 are single-cell frontiers, while nonadjacent 31449/31450 form a parallel frontier. Each bundle includes exact XYZ, adjacent regions, an actual directed open path, and a closed-path counterexample check. Single-cut checks show why both parallel triggers are required.

Plantiguardias (166), Riktus de Élite (139), Torre Mineral (133), and Necrópelis de Morbax (150) each contain one native PositionTrigger but do not produce a literal separator under this analysis. These results do not establish that their triggers are irrelevant: activation footprints and payload-defined activation cells have not been decoded. The report distinguishes literal walkable object coordinates from that unsupported authority and never snaps an object to nearby terrain.

The analysis cuts exact Door cells and all literal trigger cells, groups triggers by identical adjacent region sets, and tests directed paths with each complete bundle opened or closed. This discovers single and parallel separator candidates, including nonadjacent members. More complex heterogeneous bundles, scripted conditions, teleports and native activation footprints require the separate hybrid review. No automatic candidate is certified as a recovered dungeon; `recovered_dungeons` remains zero.

Reproduce with `python3 server/tools/audit_native_position_trigger_cuts.py`. Focused regression command: `PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_native_position_trigger_cut_audit.py` (three passing tests). Source hashes and per-map geometry hashes are recorded in the JSON. This audit does not modify runtime, database, client or sniffer files.
