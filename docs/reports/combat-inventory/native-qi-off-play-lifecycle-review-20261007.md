# Native QI lifecycle after an owned death

## Native contract

`ProbeNativeOffPlayQI.java` executes the actual client `fdt` and `QI` classes. An active fighter changes from `IN_PLAY` to `OFF_PLAY` through `fdt.bv`. The actual `baF/baG/baK` guards change, while its QI slot, supplied byte, occupied cell membership, `bcP`, and `bcQ` remain unchanged. Explicit `QI.g` removes the slot and assigns byte `-1`.

The probe reports PASS. Its actor fixture explicitly supplies an active fight association and ordinary visibility; it does not infer either fact from HP. Full fight cleanup ordering is separate bytecode evidence: `fcb.aC` invokes the OFF_PLAY transition; the concrete `buH.B`/`fbX.B` cleanup has no QI removal. `fcb.aD` performs OUT_OF_PLAY cleanup through `H`, whose `aQ` calls `QI.g`.

## Closed server blocker

`combat_qi_fight.current_registry` previously rejected every query after any registered actor reached HP0. It now accepts an actor whose explicit owned status is OFF_PLAY and whose adjacent owned damage/death events prove the transition. It preserves the original byte, footprint, blocking metadata, and per-cell byte-set history. An unproved HP0 snapshot still rejects. An OUT_OF_PLAY actor with a retained slot rejects even when HP is positive: removing that slot requires its actual lifecycle producer.

This distinction allows subsequent queries for another NPC, actor movement, area preflight, summon obstacle registration, and native LOS to use the existing QI collection after a kill. A corpse remains a native obstacle where its actual properties require it.

## Validation scope

`test_combat_qi_death_lifecycle.py` contains nine regressions covering those operations, preserved collection history, positive-HP OUT_OF_PLAY, and rejected fabricated deaths. The casting test exercises native target resolution, the summon test exercises actual obstacle registration, and the LOS test supplies isolated ray results to exercise native obstacle policy. They do not establish complete class spells or all map geometry. Automated execution is delegated to the shared validation worker; no live server was restarted.

Compile and execute the native proof offline:

```sh
javac -proc:none -classpath 'client/lib/*' -d /tmp/wakemu-global-pv-probe sniffer/java/ProbeNativeFightersBreedRange.java sniffer/java/ProbeNativeQIRegistry.java sniffer/java/ProbeNativeOffPlayQI.java
java -classpath '/tmp/wakemu-global-pv-probe:client/lib/*' ProbeNativeOffPlayQI
```

## Remaining producer boundary

The verified percentage-HP maximum handler now records its distinct `percentage_hp_update` immediately before death, including effect class986, running UID, original positive HP, final HP0, maximum and actual caster. That exact producer also registers OFF_PLAY; the corpse verifier accepts its bounded adjacent event contract. The percentage-HP suite adds a source-registration regression. It does not synthesize a damage event. OUT_OF_PLAY slot removal and revival remain separate lifecycle transitions; neither is inferred from HP.
