# La Pischina: four native trigger-cut arenas, version 10

Source-only candidate. No activation, deployment, restart or frozen previous-report mutation was performed. Configuration version10 uses existing authoritative mixed-flow movement, not fake Door packets or altered walking geometry.

## Actual blocking cause

The native map912 contains a continuous walking path through all four main arenas. Its mandatory progression boundaries are native **PositionTrigger** objects, not the native Door objects used by the earlier extractor. A doors-only analysis therefore finds one large908-cell main component plus a254-cell optional annex and falsely concludes that the mandatory gates can be bypassed.

The native shortest entry-to-boss-exit path crosses precisely these literal trigger cells in order:

| Native trigger | Exact native position | Frontier |
|---|---|---|
| 31447 | `[24,15,1]` | Room1 → room2 |
| 31448 | `[33,6,1]` | Room2 → room3 |
| 31449 | `[52,-4,1]` | Room3 → room4, left lane |
| 31450 | `[53,-4,1]` | Room3 → room4, parallel right lane |

Removing those four native cells plus the genuine annex door31487 produces four mandatory arena components of220,183,231 and270cells. The two final parallel trigger cells must be gated together; blocking only one lane would permit bypass.

## Four actual encounter areas

| Room | Native arena cells | Literal arrival | Encounter anchor | Initial count | Native-minimum threat |
|---|---:|---|---|---:|---:|
| 1 | 220 | `[22,38,0]` | `[27,26,0]` | 2 | 226 |
| 2 | 183 | `[24,15,1]` | `[25,6,-5]` | 4 | 456 |
| 3 | 231 | `[33,6,1]` | `[43,4,-9]` | 6 | 686 |
| 4 | 270 | `[52,-4,1]` | `[36,-23,0]` | 8 | 939 |

The initial quantities are explicit user-authorized local family progression, not claimed official guide counts. Native ordinary family members4723,4724,4725 and4726 are eligible. Zespadín Negro4727 has native BOSS43 and occurs once in the last encounter. Leviatún4889 is excluded from invented main groups: documentary evidence identifies its authentic optional fishing encounter; native property102 is not sufficient to treat it as an ordinary initial actor. No dominants, archmonsters or initial summons are inserted in the mandatory composition.

The actual entry cancellation object24196 and final exit24197 both use native destination543, returning to map1208 at`[17,57,-36]`. The final exit is in the boss arena, including its native staircase to the raised exit at`[15,-26,20]`.

## Authoritative frontier without client manipulation

The four trigger cells belong to the destination room in the topology. Existing `native_mixed_victory_policy` rejects every movement step entering a room beyond the committed unlocked frontier. After the preceding room victory, those native steps become valid. All original native walk cells and directed edges remain unchanged.

The documentary `position_trigger_gates` list carries each native ID, position and source/destination stage. These objects are not put in `physical_doors` and receive no fabricated Door visibility/collision packet. Offline sequence validation combines actual physical gates and trigger-derived frontier cuts to prove closure and reachability. Native trigger scripts are not claimed to be reimplemented.

## Optional content remains separate

- Genuine Door31487 at`[54,-3,0]` leads from room3 into a254-cell optional annex. It is not a mandatory progression boundary.
- Native Doors24202/24203/31444/31445 sit on a lower layer with no native walking edges at their literal positions. They are unresolved native positions/footprints, not established decorative objects; the frozen candidate’s descriptive word “decorative” is not evidence of their gameplay role. Their XY footprints subdivide the annex, but this does not establish decoded collision or puzzle authority.
- Documentary lever/mimic mechanics in room3 and the optional fishing encounter remain unresolved optional systems. No mandatory group is placed in that annex.

## Frozen evidence and verification

- Report:`PISCHINA-NATIVE-TRIGGER-CANDIDATE-V10-20261010.json`.
- Configuration:`.runtime/local/pischina-native-trigger-v10-20261010/native_dungeon_143.json`.
- Report SHA256:`3df031062d03b3068b0c919318492f717815509554b8612436eabc8ef3b23564`.
- Configuration SHA256:`ae8bf4391c998cb0c5fd501f79cc1f516f6584e91184f964cb6396435f02e25b`.
- Independent native geometry and formation:`PISCHINA-NATIVE-ARENA-GEOMETRY-20261010.json`.
- Annotated figure:`PISCHINA-NATIVE-GEOMETRY-ANNOTATED-20261010.svg`.

All four formations fit six player slots, and even eight-enemy formations fit independently in all four native arenas. The prepared candidate validates actual native arrivals, engagement approaches avoiding enemy occupancy, increasing composition, unreachability before prior victory, next-frontier approaches, native boss exit and native object-state hydration. No synthetic walk edges are used even in this candidate's offline validation.

Luna received the exact frozen paths and hashes for independent unit tests and isolated PostgreSQL lifecycle validation. Runtime activation remains a separate gate.

## Reusable trigger frontier extraction

`server/tools/extract_native_trigger_frontiers.py` independently derives a unique directed stage order from supplied native trigger objects. It validates exact map/type/position identity, native walkability, connected or disconnected parallel cuts separating the same two regions, absence of ambiguous/cyclic cuts, required encounter count and directed frontier closure. Applied independently to La Pischina, it returns exactly four regions220/183/231/270 and the three frontiers31447,31448,31449+31450. The builder now cross-checks this reusable result without changing the frozen candidate.

## Independent isolated PostgreSQL result

Luna completed the actual V10 lifecycle successfully: six real entry arrivals, all four native trigger movement barriers before and after victory authorization, both parallel final lanes, two bypass probes per frontier, four victories and spawn receipts, and the native completed exit. The stored runtime geometry exactly equals the native export:1173cells and3891directed edges. Evidence:`PISCHINA-NATIVE-TRIGGER-PG-LIFECYCLE-V10-20261010.json`, SHA256`6ddaa9c359d0d2515ce51e53ba561529ad4013f54623df6bafb6969f53a2dcae`. This validates the source candidate, not deployment or native optional puzzle scripts.
