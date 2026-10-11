# Native initial NPC criterion contracts

The installed client distinguishes definition availability from completion facts.
`IsAchievementObjectiveComplete` is implemented by `eNe`: it obtains `eIo` from
the supplied criterion context or actor `eIp.dtP()`, then calls `eIo.Bd(id)`.
Its native result is zero for completed and minus one for incomplete.

The actual client implementation `bdM.Bd` looks up the objective in `hJa` and
returns `bdS.dew()`. **An unknown objective throws RuntimeException.** Consequently
an unrecognized objective must remain unsupported; missing definitions cannot
be interpreted as an incomplete objective.

The definition catalog is constructed separately. `bdK.deh()` constructs a
`bdM` from native variable and achievement definition maps. Constructor helper
`bdO` clones each achievement and each of its objectives into `bdM.hJa`.
`bdS` stores completion in boolean `hHI`, initially Java's false; `reset()` sets
it false. Serialized account facts are subsequently applied by `bdM.dT(byte[])`:
its completed-objective list calls `fo(true)` for each recognized ID. Unknown
serialized IDs are warned about rather than creating a new objective definition.
This proves an initially incomplete known objective, not arbitrary persistent
quest completion or progression.

Both objectives10595 and10606 are present in installed quest5154's `aJN`
definitions. An offline native oracle verifies the actual `bdS`, `bdM` and `eNe`
contracts for these two IDs:

```sh
javac -proc:none -cp 'client/lib/*' -d .runtime/local/classes sniffer/java/VerifyNpcInitialCriteriaFacts.java
java -cp '.runtime/local/classes:client/lib/*' VerifyNpcInitialCriteriaFacts
```

Observed output: both initially false, explicitly completed true, reset false;
unknown objective throws. The oracle scaffolds the two known definitions in an
isolated manager; it does not represent a full graphical login or inspect the
live account's serialized facts.

## Instance identity

`GetInstanceId` is `eKB.d(...)`. With an actor context it resolves `eGj` and
returns `eGj.arM()`; its additional supported contexts likewise expose `arM`
(or `SN.bhl`). `eGj.arM()` returns its long `aJo` field.

The native POSITION section is `rE`: X and Y int32, Z int16, followed by the
long field named `Vp`, direction and optional following-position data. Its
consumer `eGt.c(...)` passes `rE.Vp` to `eGj.fE(long)`, which assigns `aJo`.
The reverse publication path copies `arM()` back into `rE.Vp`. Thus the criterion
reads the world identity actually published in the actor POSITION section.
Wakemu's `wire.position` currently publishes `character['map_id']` into this
field and explicitly distinguishes private instance ownership. Server-side
criterion evaluation must use that same published identity, not the SQL private
instance identifier. The native oracle additionally confirms eKB reads1385 from
an `fya.arM()` context.

Private disassemblies: `.runtime/local/npc-initial-criteria-native.txt`,
`npc-achievement-bdM.txt`, `npc-achievement-definitions.txt`,
`npc-criteria-bdK.txt`, `npc-criteria-rE.txt` and
`npc-criteria-position-consumer.txt`.

No runtime quest completion, database migration, client asset, service or server
source was changed. Follow-up verification used the actual active catalog default extracted read-only
by Luna in `.runtime/local/verification-fast-20261011/ranch-dispatch/achievements-default.json`:
`001200000005000000000000000000000000000000` (21bytes). Native `oN.aG`
consumes all21bytes: uint16 length18, eighteen fact bytes, final compression flag
false. Native `bdM.dT(oN.Se)` succeeds. An independent fixed-field inspection
confirms version5, zero timed entries, variables, achievements, completed
objectives and tracked entries, with no remaining payload bytes. Known objectives
10595,10606 and10607 remain incomplete. The updated oracle accepts the manifest
path as its optional argument and performs these checks using its exact bytes.
This validates the active catalog default, without asserting any new persisted
quest progression.

Active default blob SHA256: `e2b2666cbfdec684de644df0cdc49438030e88fe67da15e2574343e2ef5447e9`.
