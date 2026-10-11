# Base Susurro: four native arenas recovered from an activation-set cut

Native ZoneTrigger16538 contains nine exact activation positions decoded from the native bEH content frame into Re.bkT. Native Re.h(aBn) checks exact set membership. These positions are activation cells, not polygon vertices or an independently decoded physical collision footprint.

Blocking those nine cells together with the four native Door cells separates the mandatory directed route into four actual regions:

| Stage | Region size | Anchor | Next native frontier |
| --- | ---: | --- | --- |
| 1 | 438 | `(0,-13,8)` | Doors16262 and16508 |
| 2 | 63 | `(0,-32,8)` | ZoneTrigger16538 activation set |
| 3 | 333 | `(-1,-52,8)` | Doors16263 and16509 |
| 4 | 374 | `(-1,-85,8)` | Exterior16259 |

All four arenas, including the63-cell second arena, support six-player/eight-enemy formations. The actual order is438→63→333→374; size sorting would incorrectly exchange stages2/3.

The V22 candidate uses explicit local victory movement authorization over this decoded frontier. It does not synthesize Door state packets for ZoneTrigger16538 or claim to execute its native script. Multiple bindings share source16538 while identifying different exact activation points. All native cells and directed edges are retained; tiny regions cut off inside the activation set remain owned by the destination stage rather than becoming extra fights.

Generated ordinary family encounters increase from2to4to6to8actors, with the identified native family boss only in the final encounter. Dominant/arch/unknown roles are excluded from generated family composition. Native movement-frontier, engagement, formation and exterior sequence checks pass offline. PostgreSQL lifecycle verification and activation are separate.

Artifacts: `BASE-SUSURRO-ZONE-CANDIDATE-V22-20261010.json`, config `.runtime/local/base-susurro-zone-v22-20261010/native_dungeon_53.json`, and standalone `BASE-SUSURRO-NATIVE-GEOMETRY-ANNOTATED-V22-20261010.svg`. Reproduce with `server/tools/prepare_base_susurro_zone_configuration.py`; renderer `server/tools/render_base_susurro_zone_geometry.py`. No client, runtime or database writes are performed.
