# Exploration artifact native authority

The installed `aNp` / binary table 133 defines eleven secrets. The reproducible
native exporter is `sniffer/java/ExportExplorationSecrets.java`.

| Secret | Level | Item reference |
| --- | --- | --- |
| 6 | 10 | 18722 |
| 9 | 45 | 20784 |
| 4 | 50 | 18384 |
| 8 | 65 | 19434 |
| 10 | 80 | 21598 |
| 11 | 90 | 21599 |
| 1 | 115 | 18103 |
| 3 | 120 | 18385 |
| 5 | 140 | 18591 |
| 7 | 170 | 19113 |
| 12 | 185 | 22087 |

`bOO.eH("isComplete")` checks `flX.aj(localPlayer.cBt(), itemReference)` first,
then character QUEST inventory. Every listed artifact has native item property
21, `ACCOUNT_QUEST`; none has passive item effects (`aLO.cku()` is empty).

This distinction is functional: `fmB.a` deliberately skips ACCOUNT_QUEST items
when restoring character QUEST inventory. Filling character `INVENTORIES/vh`
therefore fails to unlock these artifacts. The correct account authority is
`eDS.INVENTORY`, ordinal 4, implemented by `flY` and read through `flX`.

Native account snapshot opcode 13873 carries an i32 section count, i32 section
ordinal 4, i32 protobuf length, then `cY`: repeated field 1 entries with uint32
field 1 item reference and uint32 field 2 quantity. `flY.a` clears the existing
map before restoring it, so this is an absolute snapshot, not a grant delta.
Preserve any other account quest items when constructing the snapshot.

`VerifyExplorationSecrets.java` decodes a generated full section-4 snapshot,
restores it through native `flY`, registers it in `eDP`, and verifies all eleven
through the same `flX.aj` authority as the menu. Restoring twice passes without
quantity inflation. No catalog modification, service restart or deployment was
performed.

Traversal powers are separate native world properties: 85 RELIC_SPECIAL_JUMP,
105 RELIC_SPECIAL_CLIMB, 117 RELIC_SPECIAL_CLOUD, 118 RELIC_SPECIAL_SWIM.
Installed `beS.dgu/dgv/dgw/dgx` read those capabilities for movement; item
presence alone does not supply them through passive effects. Native movement
research is maintained by the dungeon geometry investigation.
