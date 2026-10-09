# Official Tainela dynamic-state route evidence

## Source and reproduction

The official capture is `.runtime/official-dungeon-capture/captures/2026-10-08T05-03-33.450475Z-f49754e2/events.jsonl` (October 7 in Bogotá). Its complete decoded snapshot is `.runtime/official-dungeon-capture/snapshots/with-backtracking/decoded/frames.jsonl`. Every decoded frame identifies an `ankama-games.com` remote. The decoded file contains 1,528 frames from 05:03:59.398311 through 05:14:54.512465 UTC; SHA-256 `0410af8f82ee3c8a209efca093d0ebbdaf477be9f35801b1a63d4559f4e381cb`. The raw recording ends at 05:15:13.971021 with `capture_stop`.

Reproduce the ordered analysis with:

```sh
PYTHONPATH=server python3 .runtime/local/reports/official-tainela-route/analyze.py
```

Output: `.runtime/local/reports/official-tainela-route/analysis.json`. It records all selected movement, interactive, transport and actor batches with frame indices, timestamps, decoded positions, native object identities and exact object-state bytes. It does not copy authentication packets.

## Exterior route chronology

| UTC | Direction/opcode | Evidence |
| --- | --- | --- |
| 05:06:12.553505 | out 13686 | Transport request, source 31316, destination 26878. |
| 05:06:12.935710 | in 12608 | Batch of 112 actors. |
| 05:06:12.936451 | in 13984 | Five map-527 objects: Drago 26865, Zaap 26878, generic interactive 12552, CraftTable 31674, Teleporter 24266. |
| 05:06:26.171740 | out 13331 | Running begins at `(-224,-34,0)` toward `(-224,-39,0)`. |
| 05:06:26–44 | out 13331 | Repeated accepted-path redirections progress southward from the transport station toward the Gobball entrance. |
| 05:06:32.659622 | out 13331 | Path `(-227,-51,0)` to `(-231,-59,0)`, 10 steps. |
| 05:06:34.353038 | in 12608 | Regional batch of 18 NPC actors. This actor batch does not itself establish a map transition. |
| 05:06:34.353916 | in 13984 | Exactly CraftTable 31675 and dungeon entrance 26842. |
| 05:06:36.469241 | out 13331 | Next path starts at `(-231,-59,0)` toward `(-235,-67,0)`. |
| 05:06:44.413895 | out 13331 | Final captured approach path `(-239,-80,0)` to `(-245,-87,0)`, 7 steps. |

The 05:06:34 state batch occurs during ordinary same-map running: there is no intervening transport, native teleporter request, or map transition between the 05:06:32 and 05:06:36 movement requests. Its regional NPC batch is consistent with crossing into new visibility coverage. At `(-231,-59)` the native 18-cell partition is `(-13,-4)`; table 31675 is in `(-13,-5)` and entrance 26842 in `(-14,-5)`, both within the native adjacent-partition neighborhood. The exact arrival instant between those two movement requests is not recorded, so 1.694 seconds measures packet spacing, not a fixed server delay contract.

## Backtracking and repeated state

At 05:13:59.176211, the client requests native teleporter 26843 with destination 2505 via opcode 12296. At 05:13:59.562607, the official server repeats the same map-527 table 31675 and entrance 26842 payloads previously sent at 05:06:34. Both records are byte-for-byte identical. This is a fresh exterior snapshot after dungeon backtracking, not optional duplicate data.

The exterior return then records paths `(-245,-89)` to `(-246,-86)` and `(-246,-88)` to `(-249,-86)` at 05:14:03 and 05:14:04, followed by haven-bag entry at 05:14:05.927684. This available recording does **not** contain a subsequent complete exterior walk back to Drago 26865. It establishes station-to-door movement and dungeon-to-exterior repetition; it cannot prove a missing door-to-station return trace.

Exact relevant payloads:

- Drago, CraftTable: `01020000000602000101010000000000000000`.
- Zaap, dungeon entrance 26842: `01020000000602000101010000010000000000`.
- Disabled dungeon Teleporter 26845: initially `01020000000602000100000000000000000000`, later `01020000000602000101010000000000000000` on backtracking.

## All observed interactive types and limits

There are nine inbound 13984 batches containing 70 object records across 13 observed types: Teleporter 31, Stool 19, CraftTable 6, GenericActivableInteractiveElement 3, Drago 2, Zaap 2, and one each of HavenWorldEntrance, RespawnPoint, ExchangeMachine, ArtisansBook, AccountChest, RanchEntrance and DimensionalBagLock. This recording does not cover all 48 installed object classes.

Most observed classes receive field 2 only. **Stool is different:** its official payload combines fields 2 and 3:

`02020000000b030000001802000001010000000000000000030000000000000000`

Consequently, successful native parsing of field-2-only updates for all installed classes does not establish complete equivalence with every official runtime payload. Stool's field-3 occupancy/state remains a separate requirement. Likewise, actor opcode 12608, dynamic object spawn opcode 13664 and interactive-state opcode 13984 are separate object lifecycles and must not be conflated.

No runtime, database, or service changes were made for this investigation.

## Native retained-instance audit

The native scene uses 18 by 18 partitions and a 3 by 3 neighborhood. `Ve.qb/qc` call `GS.B(float)`, which performs mathematical floor, including negative coordinates. Server `math.floor` agrees with this implementation.

`cEX` (13984) calls `bEG.b(id, payload)`. `QY.du` reconstructs a new object from the installed `Rb` baseline and applies the incoming state to that new instance. `cdE.l` then finds its loaded partition and calls `cdz.e`. If that partition already contains the same ID in `lUP`, `cdz.e` logs a duplicate and refuses replacement. Thus repeated 13984 is not an in-place update of an already attached object. Sending full baseline and then dynamic state can retain the first attached instance instead of the later authoritative state. This is a concrete failure mechanism to verify in the live inspector, not proof that it caused every reported disappearance.

The baseline first short sets `bkO` (template/reference), not `aHm` (`Sn`, the object ID), so it does not corrupt the registration ID. Actions are factory-created by `Ni.od`; there is no evidence of shared action-owner corruption.

Official 12344 updates object 26845 twice at 05:10:55.421242/421740 and chest 13261 at 05:14:48.091348. The installed native handler `cEY` resolves `cdE.exN().mL(id)`, applies `bEG.as` and refreshes actions with `aWA`, mutating the attached object in place; this contrasts with 13984 creation. A live diagnosis should record raw registration presence, loaded partition, retained `cdE.mL(id)` identity and state flags, and compare them with the incoming state.

## Confirmed regional-loader message

The earlier selected-message analysis omitted opcode 12318. This omission concealed the decisive regional-loader step. The installed `csV` decoder reads two big-endian integers. `cgN.a(csV)` invokes `cdE.exN().em(x, y)`, moving the interactive partitions with `cdz.KD`, or recreating them for distant movement. This is separate from locally animated terrain/player movement.

The official same-map exterior walk includes these inbound 12318 positions:

| Frame | UTC time | Position |
| --- | --- | --- |
| 198 | 05:06:12.915856 | -224, -34 |
| 340 | 05:06:27.191537 | -224, -37 |
| 391 | 05:06:34.339907 | -231, -55 |
| 411 | 05:06:37.780563 | -235, -63 |
| 427 | 05:06:41.963993 | -237, -73 |

At 05:06:34, the order is 12318 regional-loader movement, then 12608 regional actors, then 13984 interactive states. Server exploration movement was publishing dynamic snapshots without this interactive-region loader message. A live diagnostic showing primary player at -217,-39 while only door-region objects at -245,-90 remain registered is consistent with this missing trigger. The general correction is to publish native 12318 at accepted movement region progression before the corresponding 13984 states, preserving 12344 for updates of retained instances.
