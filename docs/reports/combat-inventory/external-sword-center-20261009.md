# External fight swords: native center versus terrain origin

## Confirmed cause

The two observer captures for fights 104 and 105 on map 527 received opcode
13753 with QI origin `(-243, -85)`, width 52 and height 48. This matched the
initiator's world position, but did not match the native sword anchor.

The original client calls `aII.c(buG)` → `aII.d(buG)` → `QI.bdT()`.
`QI.bdT()` returns `(x + width / 2, y + height / 2, 0)` using integer division.
`aIz.a` creates both team sword actors at that position. The actual preferred
anchor was therefore `(-217, -61)`, displaced by `(26, 24)` cells. If the
preferred point is invalid or occupied by another sword, the native client
can select a fallback actor position. Packet delivery alone never established
correct placement.

The earlier `ckM`/`fbm` origin probe verified a different object: the terrain
area presentation. It did not verify the map swords. The nearby client error
about ApplyEffectAreaProperty10 on a Mimic also occurs outside marker creation
and is not established as this defect's cause.

## Correction and verification

`combat_external_markers._marker_topology` now centers the public QI rectangle
on the captured initiator cell. Its public origin is
`(starter_x - width // 2, starter_y - height // 2)`. Partition registration is
derived from that corrected rectangle. Participant arena geometry and masks
are not modified; only the external presentation envelope is translated.
Native ground-height resolution and collision fallback remain client-owned.

Regression coverage includes 52×48, 19×22, 19×19 and 1×1 rectangles, negative
coordinates, exact center, partition coverage, and unchanged private arena
bytes. The focused marker/dispatcher/wire batch passed 23 tests, no skips.

The actual captured 104/105 envelopes were regenerated with the corrected
production helper. Private `ProbeNativeSwordCenter.java` parses each using
original `cuY`, assigns native QI header fields, and calls original `QI.bdT()`.
Both corrected packets produce `(-243, -85, 0)`, zero XY displacement. This
probe verifies the native preferred anchor, not terrain-loaded rendering or
fallback behavior. Evidence is under `.runtime/local/issue16-current-marker/`.

## Deployment and manual acceptance

Source fix and offline verification are complete. This investigation has not
built or deployed a replacement world image and has not restarted services.
Do not claim the running server contains this correction.

After integration into a complete validated world build, use two accounts in
the same public map. Start a fresh PvE fight while the second player remains
outside. Both team swords should appear at the initiator's original cell
(subject to the native collision fallback), with working Join and Observe.
Repeat from a different location and in a dungeon to cover different arena
sizes. Existing basic joining, friendly challenges and interactive elements
were already confirmed by Hector; this acceptance targets marker position.

### Coordinated deployment update

Included in the complete r54 world image on2026-10-09 alongside shared combat
and aptitude changes. Image SHA256 `1aea6b9588210ada788fdd2423f8529c7a7eb5428c9a5fa2c4622c85a3b3e70b`;
production manifest626files verified, marker unit suite16/16PASS. World and AI
healthy. The earlier no-deployment statement describes the investigation
checkpoint; this update records the later coordinated release. Visual manual
acceptance remains pending.
