# Factor Trool, Ciudad Prohibida and Negraspora: actual endpoint review

This independent review resolves native entries directly from each route's destination ID. An earlier read observed Factor Trool's entry for the other definitions; a subsequent full crosscheck of the shared flow artifact found zero mismatches across139records. No current flow-entry defect is asserted. Direct destination-ID resolution remains the authoritative reproduction method.

| Definition | Actual native entry | Native arena evidence |
| --- | --- | --- |
| Factor Trool13 | map483 `(-60,-74,0)`, destination1167 | One418-cell region supports6players/8enemies at `(-79,-83,1)` |
| Ciudad Prohibida155 | map1256 `(0,3,0)`, destination4033 | Tiny entry lobby connects through three parallel doors to347-cell arena;6/8anchor `(-13,-13,0)` |
| Negraspora84 | map806 `(-38,1,0)`, destination1502 | Two233/321-cell arenas,6/8anchors `(-62,-2,0)` and `(-91,0,12)` |

Directed native entry-to-anchor walking witnesses exist for all these anchors with gates open. Closed-stage admission and full lifecycle remain candidate/runtime validation responsibilities.

Ciudad's Doors33363/33364/33365 all join the lobby and main arena. A first-encounter policy must admit traversal before attempting formation placement in the main arena. The lobby itself is too small for a six-player formation. The current [MethodWakfu guide](https://methodwakfu.com/pvm/donjons/cite-interdite/) explicitly describes one room for three players; native assets may represent an older six-player format, so external current format is context rather than automatic geometry authority.

Negraspora's Door21699 separates its two main regions. Doors21697/21698 remain same-region native objects and must not invent another encounter. Exit21700 is usable at the entry end. Boss-end exit21701 is located at `(-83,-10,9)`, while its sole same-XY native surface is `(-83,-10,8)`. The one-unit height offset needs the native approach/collision height contract; this review does not silently snap it. The [current dungeon index](https://methodwakfu.com/donjons/) describes two rooms.

Factor Trool's418-cell arena has native exits18806 and18813. Five legacy internal destinations point to XY positions having no exported native surfaces at any height. They cannot be used as valid room arrivals. The [Wakfu.Guide Academy Trool section](https://wakfu.guide/donjons/81-95/) identifies a three-player boss format. A one-encounter policy is plausible but must be explicitly reviewed; missing legacy activity destinations are not fabricated.

Reproduce using `server/tools/review_three_blocked_native_formations.py` with read-only native catalog access. Frozen evidence: `THREE-BLOCKED-NATIVE-FORMATIONS-V1-20261010.json`, including complete native graphs, six/three-player formation attempts, and directed walking witnesses. No client, runtime or database changes.

## Prepared source candidates

`THREE-NATIVE-REVIEW-CANDIDATES-V1-20261010.json` records three offline-prepared configurations under `.runtime/local/three-native-reviewed-candidates-v1-20261010/`. Factor Trool and Ciudad use one actual accessible encounter; Ciudad's three lobby doors remain native objects with stage1→stage1 bindings, opening before the first encounter. Negraspora uses two arenas separated by21699 and a literal directed return walk to entry exit21700 after final victory. No unsupported height projection is needed.

Each candidate retains all native exploration cells and edges, filters generated family actors by native role eligibility, keeps the identified family boss only in the last encounter, and uses progressive quantity/threat where multiple encounters exist. Six-player/eight-enemy placement and offline complete physical sequence validation passed. PostgreSQL lifecycle validation and activation are separate; this report does not claim either. Reproduce with `server/tools/prepare_three_native_review_candidates.py`.
