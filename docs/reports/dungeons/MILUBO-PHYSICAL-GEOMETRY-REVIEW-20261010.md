# Milubo: four-arena native geometry review — 2026-10-10

The singleton teleport-extraction result is incomplete. Milubo's entry region has no internal teleport reachable until physical Door 32205 is crossed. The old transport-only extractor ignores that walking gate, stops in its initial region, and labels the result `transports_within_same_physical_region`. This does not prove that the dungeon has only one encounter room.

Native definition 47 explicitly has type `DUNGEON_4_ROOMS` and asset map 1266. Exact exploration geometry contains 1,334 walkable XYZ cells and 4,494 directed edges. Removing the two exact Door cells separates four large arena candidates and three transit regions. Additional isolated cells remain in the native geometry and are not invented combat rooms.

| Proposed stage | Closed region | Native cells | Native formation anchor | Eight enemies + six players |
| --- | ---: | ---: | --- | --- |
| Entry arena | 9 | 196 | `(5, 7, 0)` | Valid |
| Second arena | 0 | 251 | `(-10, -89, 0)` | Valid |
| Third arena | 16 | 352 | `(46, 122, -2)` | Valid |
| Fourth arena | 6 | 356 | `(6, 116, 16)` | Valid |

The arena order is a proposed local interpretation of exact native connectivity; the independent combined gate/transport audit must verify it against entry, exit and literal teleport links. Native type and geometry agree on four large arenas, but neither alone certifies official victory triggers or boss mechanics.

## Physical gate evidence

Door **32205**, at `(13, 1, 0)`, separates entry region 9 from transit region 13. A directed path from native arrival `(0, 0, 0)` to the next transport center `(17, -11, -8)` has 39 cells with this gate open and does not exist with the gate closed.

Door **32212**, at `(36, 117, 0)`, separates third-arena region 16 from fourth-arena region 6. A directed native path from `(46, 122, -2)` to `(6, 116, 16)` has 47 cells with this gate open and does not exist with the gate closed. The final arena's elevated native terrain is therefore connected by actual stairs/height transitions, not a guessed teleport.

Transit regions are 13 (36 cells), 15 (24 cells) and 14 (107 cells). Their exact teleport centers and destination positions require the combined graph; proximity does not establish progression order.

## Layered terrain audit

Twenty-nine XY positions have more than one native Z layer, notably the overlapping `z=-8` and `z=-27` corridors. The geometry stores full XYZ vertices. No directed edge moves more than one horizontal tile; the largest vertical change is four units, matching the extraction actor's native jump-capacity profile. There is no evidence that the singleton result arose from flattening floors or joining distant cells.

## Evidence and visual artifact

- `MILUBO-PHYSICAL-GEOMETRY-REVIEW-20261010.json`: native hashes, region sizes/bounds, exact gate topology, full directed gate witnesses and all layered XY positions.
- `MILUBO-FOUR-ARENA-FORMATIONS-20261010.json`: three valid native formation anchors per arena, with eight enemy positions and six-player capacity checked by the existing formation algorithm.
- `MILUBO-NATIVE-GEOMETRY-ANNOTATED-20261010.svg`: standalone vector map showing all three map clusters, four colored arena regions, gray transit terrain, exact gate IDs and teleport IDs/Z coordinates.

No client assets, sniffer hooks, runtime state, combat logic or spells were changed. This investigation does not activate the dungeon.
