# Mixed native door and transport blockers

The offline audit resolves literal transport endpoints against the ordered native physical room components. No client files, runtime settings, transport destinations, or combat behavior were changed. Reproduce from repository root:

```sh
python3 server/tools/audit_mixed_dungeon_flows.py
```

The machine-readable evidence is `MIXED-NATIVE-TRANSPORT-AUDIT-20261010.json`.

| Dungeon | Exact blocker | Required implementation |
| --- | --- | --- |
| Montaña Conohos (`native:136`, map 1224) | Source 35990 at (-3,-12,0), destination 4794 at (6,-14,-20), directly joins room 1 to room 6. Reverse source 35991 joins room 6 to room 1. The forward link bypasses gates 31408,31409,31410,31411,31412. | An explicit mixed policy must authorize this shortcut only after the relevant frontier, while retaining the literal native endpoints. The current adjacent-room-only transport resolver rejects both links. |
| Hacienda de la Balinería (`native:145`, map 911) | Source 24175 is approached in physical room 2 at (-17,18,-24), but destination 4012 (-62,-96,0) is outside every ordered physical room. Reverse source 24177 (-62,-95,0) is also outside the chain; destination 2078 returns to room 2. | Extract the detached annex component, prove its exact native approach and assignment to room 2, and support intra-room transport without advancing progress. Do not discard the annex or redirect arrival. |
| Neohacienda de la Balinería (`native:211`, map 1458) | Source 35311 is approached in physical room 2 at (52,-43,-24), but destination 4757 (65,-149,0) is outside every ordered physical room. Reverse source 35364 (65,-148,0) is unassigned; destination 4758 returns to room 2. | Same annex and intra-room transport support as Hacienda. Preserve the variant destination criteria; the non-Neo destination is on another map and cannot be treated as a same-instance internal link. |
| Escarantera Abandonada (`native:151`, map 909) | Source 24166 (47,-35,0) is outside every ordered physical room; destination 2073 (42,-34,0) belongs to room 2. | Determine the detached source component and its intended room from native directed reachability; current physical topology cannot identify the source room. |

These are concrete topology/runtime incompatibilities, not a reason to wait for manual playtesting of the already activated dungeons. None of these four is a safe additional activation with the current physical-only configuration. A mixed implementation would need dedicated topology validation, transport authorization, object state publication, and regression tests before activation. The current resolver requires the source and destination rooms to differ by exactly one (`server/wakfu_server/maps/dungeon_doors.py`), and the physical configuration only includes the linear walking chain.
