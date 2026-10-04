# Native combat event IDs: evidence and unresolved semantics

Audit of the installed offline client on 2026-10-03. No official service was contacted.

`OY` is an HMI action. Its constructor allocates incrementing instance IDs; `aYc` is `targetOnly` and `aYd` is `isInstant`. `eVE.rzc..rzg` contain five HMI action lists and `rzh` is their deduplicated union. These IDs must not be interpreted as passive/combat events. `eVl` describes effect flags. `eVi` registers effect classes, not combat events.

Actual passive subscription masks are `PK.aZG/aZH/aZI/aZJ/aZK/aZL`. `PK.aZO` supplies emitted event bits. `Qi` matches masks by intersection; `eZX` schedules removals before applications, and `eZY` sorts applications by priority descending, definition ID ascending, instance ID ascending. `combat_trigger_masks.py` and `ProbeTriggerMasks.java` reproduce the verified routing matrix.

The following special IDs have **no accredited gameplay event names**:

| ID | Exact evidence | Semantics |
| --- | --- | --- |
| 1001, 1002, 1003, 1005, 1028 | `eFl` static BitSet; `eFl.d` tests intersection | Unknown. Their classification participates in `eZX` resetting `Qe.baW` before applications. |
| 1010 | `eZR.bcd` reads this bit from `bbv/aZL` | Unknown. A mask test is not evidence of a turn/death event name. |
| 1046 | `eZk.fRd` calls `fbX.a(1046,caster,target,cell,state)` | Scenario hook when a state is involved; not accredited as a BitSet combat event. |

The offline jar contains no accredited event-bit emitters mapping these IDs to fight start, fighter turn start/end, damage, death or movement. Searches included all class bytecode for `sipush` values1000..1099 in classes referencing BitSet, integer constant-pool values in that range, and auxiliary jars. Missing evidence is not an assertion that the server never emits those IDs. Keep the IDs intact and leave gameplay names unknown until an emitter or native server source establishes them.

Reproduction uses Java22 `javap -classpath 'client/lib/*' -c -p Qi eZX eZY eFl eZR eZk OY eVE`. UI/network action enums such as `fcl.TURN_START` are separate from passive subscription bits and must not be substituted.
