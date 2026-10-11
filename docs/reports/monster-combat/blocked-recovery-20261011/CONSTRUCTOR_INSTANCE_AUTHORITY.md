# Native instance identity during ordinary NPC construction

Four pending ordinary monsters fail while installing initial state7733:
5385Marthos,5386Parraguás,5387Escudacha,5389Martilloseco dominante.
State7733 contains effect345192, class447, parameter14, criterion
`GetInstanceId() == 1376`. Escudacha also has state7703, whose root344676
has no criterion. The failure occurs before the first attack.

`eKB` reads actual `eGj.arM()`, which returns long field`aJo`.
The Java constructor starts that field at0. `eGj.aWs` explicitly resets it
at bytecode offsets28–30; `big.aWs` invokes that reset. Later `fE(long)`
assigns the POSITION identity. The installed native oracle creates an actual
actor subclass, confirms eKB returns0, then sets fE1376 and confirms1376.
The reset is separately confirmed by bytecode; the oracle does not claim to
execute the full reset lifecycle of an initialized monster.

The ordinary initial-state initializer previously reused a conservative
summon constructor authority whose instance field is unknown. A narrow wrapper
now supplies source-proven constructor0 only at this exact fresh, off-play,
pre-team boundary. It rejects already published values, registered actors and
player authority. Registered ordinary actors still use the published POSITION
identity; generic summon authority remains unchanged. There is no fallback to
map, SQL instance, encounter identity, or missing-value zero.

Native oracle: `sniffer/java/ProbeNativeConstructorInstance.java`.
Private source hashes, state receipt and disassemblies:
`.runtime/monster-blocker-recovery-20261011/constructor-instance/`.
NEW tests: `test_combat_ordinary_constructor_instance.py`; existing tests remain
unchanged. Both NEW tests passed under the independent qualified offline harness
(`offline-ordinary-npc-book-constructor-tests.json`). Actual four-monster
replay remains pending. This source fix does not claim those monsters ready to enable.
