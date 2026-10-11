# Combat 175: turn acknowledgement latency

Incident window: 2026-10-10 23:24–23:28 UTC. Boot `568573d1b9f746db81b9f8cf3ef64ae4`, map 1134. Request `467e2b26aa734ea78377e76981d4c9af` started 23:27:06.811132 and completed 23:27:13.970964: 7159.904 ms. Preserved request events and extracted decision metrics are private under `.runtime/local/diagnostics/combat175-turnack-20261010-2327/`.

## Measured cause

One client ACK synchronously drives four native tactical searches and publications:

| Publication time UTC | Action | Search wall ms | Commit wall ms | Native wait reported by search ms |
| --- | --- | ---: | ---: | ---: |
| 23:27:09.643040 | move | 2497.395 | 19.291 | 2044.900 |
| 23:27:11.469904 | move | 1727.298 | 18.070 | 1463.538 |
| 23:27:12.962451 | cast | 1310.797 | 88.156 | 1037.712 |
| 23:27:13.969731 | end turn | 882.290 | 51.637 | 698.336 |

The stage timings are separate per-action driver timings, while diagnostic `elapsedMs` is cumulative owner turn age. The final 7085.8 ms diagnostic is not an additional seven-second end-turn calculation. Search wall total is 6417.780 ms; commits total 177.154 ms. This reproduction does not show a single multi-second native commit or SQL wait.

Aggregate bridge measurements across the four decisions:

- 41 cast previews: 3132.877 ms wall, 2952.589 ms thread CPU, maximum 417.454 ms.
- 18 movement previews: 1261.423 ms wall, 1189.618 ms thread CPU, maximum 98.597 ms.
- Nested native preview execution: 59 calls, 1661.247 ms wall, 1654.678 ms thread CPU. This is included in preview wrapper timing, not additive.
- Complete source guards: 256 calls, 515.687 ms wall, 512.014 ms thread CPU.
- Repertoire: 21 calls, 240.541 ms wall, 196.495 ms thread CPU. Target envelopes are nested work.
- Transport: 151 requests, approximately 8.68 MB sent, 1666.2 ms request wall time. Some transport work is inside preview publication; do not add it to inclusive preview totals.

Repeated effects 182839/183317/183318/183302 and `no_effect` events occur while native candidate previews execute. Their lack of final damage is not evidence that execution can be skipped: native callbacks, conditions, counters and retained state must remain authoritative.

## Safe optimization boundary

Current `native_turn.run_turn` searches again after each action. In shared combat, `bridge/world_shared.py` additionally creates a fresh copied runtime for each publication, closes the previous generator, and re-encodes shared authority context before the next driver. The selected decision contains a raw action plan but no explicit per-edge authoritative certificates.

Blindly following that plan would validate legality at `oracle.commit` but would not prove tactical parity after random results, damage, retained effects, reactions or authority changes. Full `oracle.state_identity` covers runtime, authorities and flags; it must not be replaced with a reduced HP/AP/position projection to force cache hits. A safe future continuation requires a selected transition chain with exact predecessor identities, unchanged actor/turn/policy/catalog, no pending presentation or ACK, and owner deadline. Any mismatch must re-search without adopting forecast runtime or packets.

The shared metadata and native presentation bookkeeping may make exact forecast/live identities differ even after pure movement. A real native oracle parity probe is being validated separately before any continuation optimization. Existing NPC compiled catalogs are already cached; this audit found no demonstrated missing parse cache to patch safely.

No tactical behavior or search budget was changed for this investigation. The separately identified long generation-2 GC pause is a distinct incident and must not be conflated with this approximately seven-second sequence of native searches.


## Residual user-visible latency

After the separate GC fix, approximately 4–7 seconds of NPC turn calculation can still remain in this reproduction because one acknowledgement drives multiple complete tactical decisions. The GC change does not claim to remove this measured AI cost. Validate the GC fix and preserve a fresh continuous capture during the same move/move/cast/end-turn scenario before choosing the next optimization.
