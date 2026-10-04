# Event1002 producer audit

The native client does not establish an automatic phase6 delivery for Impacto Felino5249. Its effect359836 is a400 listener with aZL=[1002], reverse subscription=true, so its verified receiving channel is60. Registration and manual delivery are supported separately; neither proves that a cast should emit1002.

An exhaustive loaded-definition scan finds exactly four aZO producers, all eYg330:

| Definition | State containing it | Group ancestry | Subscription |
|---|---|---|---|
|196837|89|161466 →196836 →196837|aZL1015/1025|
|289926|6074|289923 →289925 →289926|aZL1015/1025|
|299976|6401|299973 →299975 →299976|aZL1015/1025|
|338934|7479|338931 →338933 →338934|aZL1015/1025|

These are retained for one turn, flag17, and emit aZO1002. No direct spell root references their group ancestry. Metadata is preserved in native-event1002-definition-sources.json. This inventory distinguishes native definition events from other integer namespaces: ffF.d1002 is a client QM timer notification; eVj.cbH1002 labels healing action presentation; ON.d1002 is a message opcode. None is treated as a combat trigger producer.

The bytecode scanner inventories every L(byte), dr(byte[]) and BitSet/source/byte delivery callsite across wakfu-client.jar. Qe.k invokes dr(1,2); Qe.a invokes dr(3,4); Qe.d invokes L1 for nonsubscribed fresh instances and bbJ invokes L2. eXP.c invokes eXt.L1, and eXD emits collision-specific delivery. Qe.L supports6 (caster60 then target6), and eZR.L would add global61, but no scanned caller invokes that lifecycle phase. Existing sender/manager bridges forward their supplied channel and are not proof of its origin.

ProbeNativeEvent1002Lifecycle uses the four actual eVn definitions and native Qe.k/eZR execution, with an explicit manager. It isolates routing by accepting the clone and replacing group child calculation/execution with no-op fixture methods. For each definition the observed lifecycle is exactly[1,2,3,4], never6. Thus ordinary group lifecycle delivery can propagate the actual1002 event on those four phases, but does not activate the phase60 listener.

Reproduction from the workspace root, Java22 and classpath client/lib/*:

- Compile FindNativeEventConstant with `--add-exports java.base/jdk.internal.org.objectweb.asm=ALL-UNNAMED`; run with `client/lib/wakfu-client.jar 1002` to inspect constants and all delivery callsites.
- Compile FindNativeDefinitionEventProducers together with ExportSpellEffectTrees; run with `1002 output.json` to export all loaded sources, metadata and ancestry.
- Compile ProbeNativeEffectUIDs and ProbeNativeEvent1002Lifecycle; run the latter to verify the four native clone traces.

Pending: the authoritative producer of phase6 and the upstream1015/1025 event inputs have not been identified in the installed client. No fincast, turn or healing event is synthesized. A complete common producer must bind the actual lifecycle caller and source identity/actor context to the transaction preview; generic phase3/4 group emission alone is insufficient for this passive. No combat module or server entrypoint was changed during this audit.
