# La Pischina: independent native geometry review

Native map 912 contains 1,173 walkable XYZ cells. Blocking only exact Door object coordinates incorrectly merges four encounter arenas into one 908-cell region: the mandatory separators are native PositionTrigger objects, not Door centers.

| Stage | Native region | Cells | Validated anchor | Boundary after this stage |
| --- | --- | --- | --- | --- |
| 1 | 3 | 220 | `(27,26,0)` | 31447 at `(24,15,1)` |
| 2 | 2 | 183 | `(25,6,-5)` | 31448 at `(33,6,1)` |
| 3 | 9 | 231 | `(43,4,-9)` | Both 31449 `(52,-4,1)` and 31450 `(53,-4,1)` |
| 4 | 0 | 270 | `(36,-23,0)` | Native exterior transporter 24197 |

The parallel third frontier requires both PositionTrigger cells: using one boundary leaves its parallel path available. These are graph separators; their actual native trigger mechanism and runtime representation are investigated separately. No inferred Door packet semantics are asserted here.

All four regions independently support formations of six players and eight enemies using published native combat cells and edges. Three valid anchors per arena are recorded in `PISCHINA-NATIVE-ARENA-GEOMETRY-20261010.json`. This proves placement capacity, not encounter execution or official monster counts.

Door 31487 `(54,-3,0)` separates the third arena from a 254-cell optional annex containing chest 26428. Doors 24202/24203 and 31444/31445 are at z=-4, while the sole native walkable cells at their XY positions are z=-5. Projecting these four objects onto those cells splits the annex into regions of 63, 163 and 24 cells without changing any mandatory arena. This is a clearly labeled footprint hypothesis; the native collision footprint has not been independently decoded. Do not silently replace object Z with terrain Z in generic extraction.

Transporter 24196 belongs to the entry arena; 24197 belongs to the boss arena. The standalone `PISCHINA-NATIVE-GEOMETRY-ANNOTATED-20261010.svg` colors all four arenas and distinguishes native gates, triggers, exteriors and the annex chest. XYZ remains authoritative; the visualization projects XY only.

## Reproduction

Run `server/tools/render_pischina_native_geometry.py` from the repository root with read-only native catalog access. It writes only report artifacts. Geometry source: `.runtime/local/all-native-dungeon-exploration/exploration-912.json`; object source: native143 in `docs/reports/dungeons/inventory.json`.

The lesson is general: physical room extraction must consider actual native trigger separator sets, parallel gate widths, and door elevation footprints. Type-only Door extraction is insufficient. Preserve optional annex terrain independently of mandatory room count. No runtime or client changes were made by this review.
