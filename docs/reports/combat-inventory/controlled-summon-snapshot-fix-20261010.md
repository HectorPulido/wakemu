# Controlled summon snapshot and separate hero turn-frame incident

## Evidence and scope

Fight 150 created Tofu actor 234 at 07:11:10 UTC. The client logged its creation at 02:11:11 with `isControlledByAI=true`. Actor refresh opcode 12873 was emitted during creation and again before its turn at 07:11:13. The server's registered-summon format-2 serializer placed the AI flag where the native fight-property component belongs, then wrote a hardcoded AI byte of 1 after the breed. This is the same native layout defect previously corrected for ordinary NPCs.

The serializer now writes the complete live signed property counter population through the shared `fight_property_payload`, then breed, then the actual `native_controlled_by_ai` byte. It does not synthesize a book, controller or abilities. Missing property authority remains an error; test fixtures now provide the real empty or populated snapshot explicitly.

## Native verification

`sniffer/java/ProbeNativeSummonFighterStats.java` now consumes every native format-2 section using the shipped client classes, requires exact EOF, and checks the positive summon ID, property 40, and the actual AI flag. Controlled and AI fixtures both passed. Reproduce with:

```sh
javac -proc:none -cp 'client/lib/*' -d /tmp/osa-property-probe sniffer/java/ProbeNativeSummonFighterStats.java
java -cp '/tmp/osa-property-probe:client/lib/*' ProbeNativeSummonFighterStats /tmp/summon-ai-false.bin false
java -cp '/tmp/osa-property-probe:client/lib/*' ProbeNativeSummonFighterStats /tmp/summon-ai-true.bin true
```

The temporary dumps use `RegisteredSummonStatsTests.fixture`, a native empty characteristic population, property 40 and AI false/true; they contain no user data.

The existing `ExportOwnedCapturedProfiles` ran against the actual shipped assets for profile 4 and passed 20 native `bPD` book checks (four abilities across five levels): 549, 7359, 7360 and 7361. A separate offline actual `bje.dsi()` constructor probe confirmed `dor()` returns a non-null `bPD`. Thus the native creature book is present; this result is independent of the server's Python book assertion.

The expanded independent automated gate passed 195 tests with no failures, errors or skips, including summon snapshots, movement, QI death transitions, retirement and checkpoints.

## Separate hero frame defect and manual result

At 02:11:44, the client logged a null `big.dor().ela()` during opcode 13482, with `cvT.bsm=1`: this is Iop actor 1's turn, not Tofu 234. The native `bje` constructor always owns its final `bPD`, and its `dor()` returns that object. The Iop/hero frame failure must remain a separate incident; the snapshot correction alone does not prove its cause or repair.

Hector subsequently confirmed the Tofu attacks were visible and working, and reported the empty bar appeared related to the hero system. This is manual acceptance of the creature's available book, not evidence that the local snapshot correction was deployed: no service was restarted or deployed in this task. The remaining hero selection/frame issue is tracked separately by the coordinating agent.
