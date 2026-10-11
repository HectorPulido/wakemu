# Milubo: actual four-room mixed native flow

This work replaces the proposed one-encounter Milubo fallback with a reviewed four-encounter candidate. It changes no frozen earlier batch or runtime activation. Configuration version 6 requires the server's general mixed-flow support before any future activation.

## Why the earlier extraction stopped

The native map is 1266. The entry is exactly `[0, 0, 0]`, not the old guide anchor near the boss area. The extraction removed physical gate cells while finding walk components, but the transport-only graph did not add those gate connections back. Consequently it falsely treated the entry component as an isolated arena. Walk components are not encounter rooms: several small disconnected components are transit corridors connected by literal native teleports.

The true ordered graph is:

`entry arena → physical gate 32205 → corridor → teleport 32206 → second arena → teleport 32215 → upper corridor → teleport 32208 → lower corridor → teleport 32209 → third arena → physical gate 32212 → boss arena`.

Every arrow is a native directed walking edge or exact native transport destination. No guessed walk edges, arrival relocation, client changes or combat geometry changes are used. Reverse transports remain available only inside already unlocked stages.

## Four stages

| Stage | Encounter anchor | Literal arrival | Native components | Initial actors | Progression gate |
|---|---|---|---|---:|---|
| 1 | `[5,7,0]` | `[0,0,0]` | Entry component 9 | 6 | Physical 32205 at `[13,1,0]` |
| 2 | `[-10,-89,0]` | `[14,1,-1]` | Corridor 13 plus arena 0 | 7 | Transport 32215/4162 → `[29,-15,-8]` |
| 3 | `[46,122,-2]` | `[29,-15,-8]` | Upper corridor 15, lower corridor 14, arena 16 | 8 | Physical 32212 at `[36,117,0]` |
| 4 | `[6,116,16]` | `[35,117,0]` | Boss arena 6 | 8 | Native exit 32211/4168 → map1264 `[61,-35,0]` |

Component numbers are documentary; the extractor pins components using actual native coordinates, so enumeration changes do not silently reassign rooms.

Native transport bindings:

| Source / destination | Stages | Exact destination |
|---|---|---|
| 32206 / 4160 | 2 → 2 | `[-15,-81,0]` |
| 32214 / 4161 | 2 → 2 | `[18,-11,-8]` |
| 32215 / 4162 | 2 → 3 | `[29,-15,-8]` |
| 32207 / 4163 | 3 → 2 | `[2,-87,0]` |
| 32208 / 4164 | 3 → 3 | `[35,-14,-27]` |
| 32213 / 4165 | 3 → 3 | `[35,-15,-8]` |
| 32209 / 4166 | 3 → 3 | `[46,111,0]` |
| 32210 / 4167 | 3 → 3 | `[25,2,-27]` |

The entry cancellation exit is 32204/4168; the completed boss exit is 32211/4168. Both lead to the same native exterior coordinate. Same-stage native transit must not consume a victory receipt, advance progress or fabricate a new encounter.

## Reviewed initial composition

The root agent visually reviewed the four archived guide screenshots and matched native species identities, role properties and grade bounds. Initial actors:

| Stage | Minilubo 5113 | Milubo 5111 | Miluba 5112 | Luna Gigante 5114 | Native-minimum threat |
|---|---:|---:|---:|---:|---:|
| 1 | 2 | 2 | 2 | 0 | 424 |
| 2 | 2 | 3 | 2 | 0 | 494 |
| 3 | 3 | 3 | 2 | 0 | 562 |
| 4 | 3 | 2 | 2 | 1 | 575 |

No initial summons, dominant actors or archmonsters are added. The actual boss occurs once in the last encounter only. The increasing score is `sum(count * actual_spawn_level)` with native-minimum spawning. Boss combat mechanics remain outside this traversal validation.

## Evidence and validation

- `MILUBO-MIXED-NATIVE-FLOW-20261010.json`: complete topology and directed mixed-path witnesses. Each arena becomes reachable at its own unlock and remains unreachable before the previous victory.
- `MILUBO-FOUR-ARENA-FORMATIONS-20261010.json`: unchanged native combat geometry supports eight monsters plus six players in all four arenas.
- `MILUBO-PHYSICAL-GEOMETRY-REVIEW-20261010.json`: actual native physical gate traversal, layered geometry and closed-gate witnesses.
- `MILUBO-FOUR-ROOM-MIXED-CANDIDATE-20261010.json`: version 6 configuration path, formation, arrivals-to-engagement paths, next-gate/exit paths, all four native state snapshots.
- `MILUBO-NATIVE-GEOMETRY-ANNOTATED-20261010.svg`: annotated native geometry.

The candidate validates formation, literal ingress and engagement for six players, progression closure, exact completed exterior exit, and twelve native hydration packets at every stage. Gate 32205 is visible/closed only at stage 1; gate 32212 remains visible/closed through stage 3. Both hide and clear collision at their unlock stage. The runtime configuration keeps exactly the original native walking geometry. Native transport edges are projected only in the offline reachability validator.

`PYTHONPATH=server:server/tests .runtime/local/verification-venv/bin/python -m unittest test_mixed_native_flow_extraction`: six tests passed. PostgreSQL lifecycle validation is delegated separately and is required before activation. No runtime import, activation, restart or deployment is performed by these tools.
