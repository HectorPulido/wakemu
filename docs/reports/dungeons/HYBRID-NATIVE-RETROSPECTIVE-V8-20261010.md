# Retrospective structural recovery, version 8

This source-only batch reviews six previously prepared dungeon routes against the combined native physical/transport graph. Earlier shortened spines are not accepted as complete flows merely because a local encounter was playable. Previous V7 and other frozen evidence remain untouched. No activation or deployment was performed.

## Two complete replacement candidates

`HYBRID-NATIVE-FULL-ROOM-CANDIDATES-V8-20261010.json` contains version 8 replacement paths:

- **Castillo de Wagnar:** all three native encounter stages remain. Three native return sources (14676,14675,16172) have no incoming path from the actual selected entry. They are now explicitly disabled with full native source hashes and reasons, rather than silently omitted. Mandatory classic transport bindings remain literal; mutually exclusive Neo alternatives are not used.
- **Ratacumbas:** both native encounters are retained. Physical separator 18823 and annex gate18824 are included alongside transports26463/26464. The tiny region3 is retained in stage2 as transit/annex terrain; no extra encounter is invented there.

Both pass formation for six players, literal hybrid engagement/arrival/next-gate/native-exit witnesses, previous-frontier closure, increasing native-minimum threat and complete native state hydration. Fresh independent isolated PostgreSQL lifecycle validation passed for both configurations with six players, complete room receipts and native exit closure: [V8 evidence](HYBRID-NATIVE-FULL-ROOM-PG-LIFECYCLE-V8-20261010.json). No activation was performed.

## Four explicit structural blockers

### Vid Vil, native115: four encounter regions, but a hub must be revisited

Native regions and sizes are entry0(189), hub1(203), branch14(321) and branch28(307). The actual graph is:

- 26745:0→1; 26746:1→0.
- 26751:1→28; 26750:28→1.
- 26747:1→14; 26748:14→1.
- Exterior exits26744 in0 and26749 in14.

No simple region path can contain all four encounters. The natural four-stage proposal must revisit the hub: **0→1→28→1→14**. A static mapping gives stages0=1,1=2,28=3,14=4. Consequently source26747 is a stage2→4 transport which must remain locked until the stage3 victory receipt exists. Current general mixed support authorizes only adjacent or same-stage routes, and its forward receipt lookup uses the source stage. Supporting this case requires an explicit native nonadjacent-stage contract gated by destination-1 victory and the committed frontier. The previous three-stage spine omitted region28 and does not certify the whole dungeon.

### Palacio Zollo, native73: branched cycle returns to its entry exit

The only exterior exit34747 is in entry region105. Native branch paths form directed cycles:

- 105→90 by34741; physical34749→41; physical34750→13; transport34744→0; transport34746→105.
- 105→91 by34740; physical34751→42; physical34752→18; transport34745→0; transport34746→105.

Region0 has411cells; region105405; branch middle41/42406/404; side rooms90/91301; corridors13/18293/298. A four-stage proposal can retain the actual loop and its branch terrain, but completing it requires literal return from stage4 to the entry stage1 and a completed-run exit witness through that return. The adjacent-only runtime and simple-path extractor currently reject this cycle. The old two-stage spine omitted physical gates and large reachable areas and is explicitly incomplete. No fabricated exterior exit or walk shortcut is proposed.

### Base del Susurro, native53: metadata says four, graph currently proves three arenas

The entry region8(438cells) connects to6(407cells), then11(374cells), with literal exterior exits in8 and11. Native gate pairs16262/16508 both separate8↔6, and16509/16263 both separate6↔11. This is not four distinct sequential room transitions: each pair joins the same terrain regions. The four-room definition cannot be satisfied merely by counting gate IDs. A fourth encounter requires additional native/script evidence or explicit staged encounters within existing terrain. The previous shortened flow must remain structurally incomplete.

### Arena Danzante, native11: three encounters cannot be derived from native separators

The definition says three rooms. Only entry region1(249cells) is reachable; no internal physical gate or native transport links exist. The only exterior source18989 belongs to this arena. Other tiny disconnected regions0(48),3(4),11(21) do not supply a route. Three sequential encounters require native script/event evidence or an explicit wave controller in this arena. A singleton arena is not the original three-stage flow.

## Reproduction

`PYTHONPATH=server ... python server/tools/prepare_hybrid_native_dungeons.py --targets 115 73 49 12 53 11 --version 8`

The tool’s version/target arguments write a separate artifact directory and report; they do not overwrite V7. General extractor API: `extract_hybrid_native_dungeon_flow.extract(...)` and `main_spine(graph, required_rooms)`. Native-directed walking edges are never replaced by guessed paths.
