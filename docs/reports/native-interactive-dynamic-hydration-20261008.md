# Native interactive dynamic-state hydration

The installed `native-map-objects.json` payloads describe base fields 0, 1 and 3. They do not contain field 2, the separate runtime update used by the official server. The full bEH base decoder also initializes visibility, usability and state; the bEI dynamic decoder reapplies these through presentation-aware setters. The earlier three-class fix omitted the independent dynamic update for other classes. Threading has not been established as a cause.

Evidence comes from `.runtime/official-dungeon-capture/snapshots/user-complete/decoded/frames.jsonl`, inbound opcode 13984:

| Time (UTC) | Map | Objects | Dynamic payload |
| --- | --- | --- | --- |
| 2026-10-08 05:04:35.724386 | 1134 | Drago 31333; CraftTable 31514, 31515, 31516 | `01020000000602000101010000000000000000` |
| 2026-10-08 05:04:35.724386 | 1134 | Zaap 31316 | `01020000000602000101010000010000000000` |
| 2026-10-08 05:06:12.936451 | 527 | Drago 26865; CraftTable 31674 | `01020000000602000101010000000000000000` |
| 2026-10-08 05:06:12.936451 | 527 | Zaap 26878 | `01020000000602000101010000010000000000` |

`world_static.snapshots()` now retains baseline geometry and parameters, then sends separate field-2 updates for these three evidenced classes. Existing registered dungeon-entrance hydration is preserved. Other classes retain their baseline and their owner-specific dynamic-state handlers; no general unlock of doors or quest objects is introduced. Repeated snapshots repeat dynamic hydration instead of treating it as an optional duplicate.

Validation: `PYTHONPATH=server python3 -m unittest discover -s server/tests -p test_world_static.py`: 6 passed. Tests inspect all installed maps containing the affected classes, preserve the initial baseline batch, validate subsequent dynamic payloads, and verify replay determinism. No service restart or client visual verification was performed by this investigation. Opcode 13984 updates existing client objects; load timing and chunk registration remain separate concerns and require an actual client check after deployment.


## General extraction and replay

The follow-up implementation covers every installed object rather than a class whitelist: 11,987 objects, 48 types, and 624 maps in the current source catalog. `sniffer/java/ExportNativeInteractiveStates.java` constructs each object with its native bEE factory, deserializes its installed payload through the native bEG/bEH decoder, and exports the exact resulting field-2 state. The exporter refuses partial output if any object fails. All objects decoded successfully. The generated `server/protocol/native-interactive-states.json` pins the baseline SHA-256 and records state, visibility, usability, bj/bk/bh flags, Z and additional actions. Startup rejects incomplete or mismatched catalogs.

Map replay now sends the retained complete baseline and then object-specific dynamic states for every object. Hidden, disabled, and non-default states remain intact. This includes ExchangeMachine croupiers. Private dungeon replay sends the same asset state first, followed by the committed run-owned opcode 12344 door overrides; native defaults cannot reopen disabled progression routes. Haven-bag map 9 retains its separate ownership path.

The extraction matches the official Drago, Zaap, CraftTable and dungeon entrance vectors listed above. It is an installed-baseline snapshot, not a substitute for authoritative quest/progression changes owned by other services. Story NPC actors are a separate opcode 12608 registry; no general story-NPC population is claimed by this change.

Follow-up validation: 8 world-static tests passed, covering every map/type/object, exact captured vectors, deterministic repeated hydration, and preserved hidden/disabled/non-default states. 17 static-map dispatch tests passed, including private baseline-before-owned-door ordering. No services were restarted by this investigation.

## Same-map walk and scene partition lifetime

Further native decoder review establishes the missing lifetime boundary. `cdy.a(cdz, acq[])` registers the chunk's raw object definitions in bEC; `cdy.ek(x, y)` removes those IDs when the partition unloads. `bEC.du` delegates to QY, reconstructing the object from its raw installed baseline. `cEX` applies inbound 13984 state and attaches the result through `cdE.l` to a currently loaded partition. An absent registry entry or absent loaded scene partition discards that update. Neither 13984 nor the rendered-object-only 12344 handler retains state for a future partition load.

Native Vc constructs 18-by-18 scene partitions and a 3-by-3 neighborhood; Ve.qb/qc divide by 18 with floor semantics. Opcode 14689 is emitted by bJj's empty value-cache refresh, not by the scene loader, and is not a reliable scene-ready acknowledgment.

The official capture contains a same-map movement request at 05:06:32.659622 UTC followed at 05:06:34.353916 by a 13984 update containing only CraftTable 31675 and dungeon entrance 26842. No intervening outbound request is present. This supports delayed regional replay after accepted movement rather than an invented chunk-ready request or permanent whole-map retransmission.

`world_scene_sync.SceneSync` schedules finite dynamic-only hydration checkpoints for the accepted path's native scene neighborhoods. One-second checkpoints continue through a conservative half-second-per-path-step estimate and a three-second tail. This duration is a scheduling policy, not a claimed native speed measurement. Redirections coalesce retained relevant regions; map or instance changes discard pending state. Per-partition encoded bytes are cached with the current registered entrance IDs. No base geometry is repeatedly replayed on walking. Private dungeon restrictions must be applied after these asset-state updates by the dispatcher.

Validation: 7 scene-sync tests passed, covering negative chunk boundaries, neighborhood filtering, dynamic-only payloads, finite delayed/tail lifetime, route registration, map/instance isolation, redirection coalescing, and maximum accepted-path bounds. No runtime restart was performed by the investigating agent.
